"""
최적화된 데이터베이스 쿼리 성능 시스템
"""
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from contextlib import asynccontextmanager
import time
import hashlib
from cachetools import TTLCache, LRUCache
from sqlalchemy import text, create_engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from langchain_core.documents import Document
import json


@dataclass
class QueryMetrics:
    """쿼리 성능 메트릭"""
    query_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    total_response_time: float = 0.0
    slow_queries: List[Dict] = None

    def __post_init__(self):
        if self.slow_queries is None:
            self.slow_queries = []


class OptimizedDatabaseManager:
    """최적화된 데이터베이스 관리자"""

    def __init__(self, database_url: str, **kwargs):
        # 연결 풀 설정
        pool_config = {
            'poolclass': QueuePool,
            'pool_size': kwargs.get('pool_size', 20),
            'max_overflow': kwargs.get('max_overflow', 30),
            'pool_pre_ping': True,
            'pool_recycle': kwargs.get('pool_recycle', 3600),  # 1시간
            'pool_timeout': kwargs.get('pool_timeout', 30)
        }

        # 동기 엔진 (기존 호환성)
        self.sync_engine = create_engine(database_url, **pool_config)

        # 비동기 엔진 (성능 최적화용)
        async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        self.async_engine = create_async_engine(async_url, **pool_config)

        # 캐시 설정
        self.query_cache = TTLCache(
            maxsize=kwargs.get('cache_size', 1000),
            ttl=kwargs.get('cache_ttl', 3600)  # 1시간
        )

        self.metadata_cache = LRUCache(maxsize=500)

        # 성능 메트릭
        self.metrics = QueryMetrics()

        # 미리 컴파일된 쿼리들
        self._compiled_queries = {}
        self._prepare_compiled_queries()

        print("✅ 최적화된 데이터베이스 관리자 초기화 완료")

    def _prepare_compiled_queries(self):
        """자주 사용되는 쿼리 미리 컴파일"""
        self._compiled_queries = {
            'regions_catalog': text("""
                SELECT DISTINCT cmetadata->>'region' as region
                FROM langchain_pg_embedding
                WHERE cmetadata->>'region' IS NOT NULL
                AND cmetadata->>'region' != ''
                ORDER BY region
            """),

            'cities_catalog': text("""
                SELECT DISTINCT cmetadata->>'city' as city
                FROM langchain_pg_embedding
                WHERE cmetadata->>'city' IS NOT NULL
                AND cmetadata->>'city' != ''
                ORDER BY city
            """),

            'categories_catalog': text("""
                SELECT DISTINCT cmetadata->>'category' as category
                FROM langchain_pg_embedding
                WHERE cmetadata->>'category' IS NOT NULL
                AND cmetadata->>'category' != ''
                ORDER BY category
            """),

            'collection_uuid': text("""
                SELECT uuid FROM langchain_pg_collection
                WHERE name = :collection_name
            """),

            'place_by_regions': text("""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding
                WHERE collection_id = :collection_id
                AND (cmetadata->>'region' ILIKE ANY(:regions))
                AND NOT (cmetadata->>'category' ILIKE ANY(:exclude_categories))
                ORDER BY cmetadata->>'similarity_score' DESC NULLS LAST
                LIMIT :limit_count
            """),

            'place_by_cities': text("""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding
                WHERE collection_id = :collection_id
                AND (
                    cmetadata->>'city' ILIKE ANY(:cities) OR
                    cmetadata->>'region' ILIKE ANY(:cities)
                )
                AND NOT (cmetadata->>'category' ILIKE ANY(:exclude_categories))
                ORDER BY cmetadata->>'similarity_score' DESC NULLS LAST
                LIMIT :limit_count
            """),

            'place_by_categories': text("""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding
                WHERE collection_id = :collection_id
                AND (cmetadata->>'category' ILIKE ANY(:categories))
                ORDER BY cmetadata->>'similarity_score' DESC NULLS LAST
                LIMIT :limit_count
            """),

            'place_random_sample': text("""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding
                WHERE collection_id = :collection_id
                AND NOT (cmetadata->>'category' ILIKE ANY(:exclude_categories))
                ORDER BY RANDOM()
                LIMIT :limit_count
            """)
        }

    def _generate_cache_key(self, query_type: str, **params) -> str:
        """캐시 키 생성"""
        # 파라미터를 정렬하여 일관된 키 생성
        sorted_params = sorted(params.items())
        params_str = json.dumps(sorted_params, sort_keys=True)
        key_data = f"{query_type}:{params_str}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get_db_catalogs_optimized(self) -> Dict[str, List[str]]:
        """최적화된 DB 카탈로그 로드"""
        cache_key = self._generate_cache_key("catalogs")

        # 캐시에서 조회
        if cache_key in self.metadata_cache:
            print("🎯 카탈로그 캐시 히트")
            return self.metadata_cache[cache_key]

        start_time = time.time()

        try:
            # 비동기로 모든 카탈로그 동시 로드
            async with self.async_engine.connect() as conn:
                regions_task = conn.execute(self._compiled_queries['regions_catalog'])
                cities_task = conn.execute(self._compiled_queries['cities_catalog'])
                categories_task = conn.execute(self._compiled_queries['categories_catalog'])

                # 동시 실행
                regions_result, cities_result, categories_result = await asyncio.gather(
                    regions_task, cities_task, categories_task
                )

                catalogs = {
                    "regions": [row.region for row in regions_result.fetchall() if row.region],
                    "cities": [row.city for row in cities_result.fetchall() if row.city],
                    "categories": [row.category for row in categories_result.fetchall() if row.category]
                }

            # 캐시에 저장
            self.metadata_cache[cache_key] = catalogs

            query_time = time.time() - start_time
            print(f"✅ DB 카탈로그 로드 완료 ({query_time:.3f}초):")
            print(f"   - 지역: {len(catalogs['regions'])}개")
            print(f"   - 도시: {len(catalogs['cities'])}개")
            print(f"   - 카테고리: {len(catalogs['categories'])}개")

            return catalogs

        except Exception as e:
            print(f"❌ DB 카탈로그 로드 실패: {e}")
            return {"regions": [], "cities": [], "categories": []}

    async def search_places_optimized(
        self,
        query: str,
        regions: List[str] = None,
        cities: List[str] = None,
        categories: List[str] = None,
        limit: int = 1000,
        collection_name: str = 'place_recommendations'
    ) -> List[Document]:
        """최적화된 장소 검색"""
        start_time = time.time()
        self.metrics.query_count += 1

        # 캐시 키 생성
        cache_key = self._generate_cache_key(
            "search_places",
            query=query,
            regions=regions or [],
            cities=cities or [],
            categories=categories or [],
            limit=limit
        )

        # 캐시 조회
        if cache_key in self.query_cache:
            self.metrics.cache_hits += 1
            print(f"🎯 검색 캐시 히트: '{query}'")
            return self.query_cache[cache_key]

        self.metrics.cache_misses += 1

        try:
            # 컬렉션 UUID 조회 (캐싱됨)
            collection_id = await self._get_collection_id(collection_name)
            if not collection_id:
                return []

            # 제외할 카테고리 (숙소)
            exclude_categories = [
                '%숙소%', '%호텔%', '%펜션%', '%모텔%', '%게스트하우스%',
                '%리조트%', '%한옥%', '%관광호텔%', '%유스호스텔%'
            ]

            docs = await self._execute_optimized_search(
                collection_id, regions, cities, categories, exclude_categories, limit
            )

            # 결과 캐싱
            self.query_cache[cache_key] = docs

            query_time = time.time() - start_time
            self._update_metrics(query_time, len(docs))

            print(f"✅ 최적화된 검색 완료: {len(docs)}개 문서 ({query_time:.3f}초)")

            return docs

        except Exception as e:
            query_time = time.time() - start_time
            self._update_metrics(query_time, 0, error=str(e))
            print(f"❌ 최적화된 검색 오류: {e}")
            return []

    async def _get_collection_id(self, collection_name: str) -> Optional[str]:
        """컬렉션 ID 조회 (캐싱됨)"""
        cache_key = f"collection_id:{collection_name}"

        if cache_key in self.metadata_cache:
            return self.metadata_cache[cache_key]

        try:
            async with self.async_engine.connect() as conn:
                result = await conn.execute(
                    self._compiled_queries['collection_uuid'],
                    {"collection_name": collection_name}
                )
                row = result.fetchone()

                if row:
                    collection_id = str(row.uuid)
                    self.metadata_cache[cache_key] = collection_id
                    return collection_id

        except Exception as e:
            print(f"❌ 컬렉션 ID 조회 오류: {e}")

        return None

    async def _execute_optimized_search(
        self,
        collection_id: str,
        regions: List[str],
        cities: List[str],
        categories: List[str],
        exclude_categories: List[str],
        limit: int
    ) -> List[Document]:
        """최적화된 검색 실행"""
        async with self.async_engine.connect() as conn:
            # 우선순위: 도시 > 지역 > 카테고리 > 랜덤
            if cities:
                # PostgreSQL 배열 형태로 변환
                cities_patterns = [f'%{city.replace("특별시", "").replace("광역시", "")}%' for city in cities]

                result = await conn.execute(
                    self._compiled_queries['place_by_cities'],
                    {
                        "collection_id": collection_id,
                        "cities": cities_patterns,
                        "exclude_categories": exclude_categories,
                        "limit_count": limit
                    }
                )

            elif regions:
                regions_patterns = [f'%{region.replace("도", "").replace("특별자치도", "")}%' for region in regions]

                result = await conn.execute(
                    self._compiled_queries['place_by_regions'],
                    {
                        "collection_id": collection_id,
                        "regions": regions_patterns,
                        "exclude_categories": exclude_categories,
                        "limit_count": limit
                    }
                )

            elif categories:
                categories_patterns = [f'%{cat}%' for cat in categories]

                result = await conn.execute(
                    self._compiled_queries['place_by_categories'],
                    {
                        "collection_id": collection_id,
                        "categories": categories_patterns,
                        "limit_count": limit
                    }
                )

            else:
                # 랜덤 샘플링
                result = await conn.execute(
                    self._compiled_queries['place_random_sample'],
                    {
                        "collection_id": collection_id,
                        "exclude_categories": exclude_categories,
                        "limit_count": min(limit, 500)  # 랜덤은 제한
                    }
                )

            # Document 객체로 변환
            docs = []
            for row in result.fetchall():
                metadata = row.cmetadata or {}
                metadata['search_method'] = 'optimized_sql'

                if row.embedding:
                    metadata['_embedding'] = row.embedding

                docs.append(Document(
                    page_content=row.document,
                    metadata=metadata
                ))

            return docs

    def _update_metrics(self, query_time: float, result_count: int, error: str = None):
        """메트릭 업데이트"""
        self.metrics.total_response_time += query_time
        self.metrics.avg_response_time = (
            self.metrics.total_response_time / self.metrics.query_count
        )

        # 느린 쿼리 기록 (1초 이상)
        if query_time > 1.0:
            self.metrics.slow_queries.append({
                'timestamp': time.time(),
                'duration': query_time,
                'result_count': result_count,
                'error': error
            })

            # 최근 50개만 유지
            if len(self.metrics.slow_queries) > 50:
                self.metrics.slow_queries = self.metrics.slow_queries[-50:]

    async def batch_search_places(
        self,
        queries: List[Dict[str, Any]],
        collection_name: str = 'place_recommendations'
    ) -> Dict[str, List[Document]]:
        """배치 장소 검색 (동시 실행으로 성능 최적화)"""
        print(f"🔄 배치 검색 시작: {len(queries)}개 쿼리")

        # 컬렉션 ID 미리 조회
        collection_id = await self._get_collection_id(collection_name)
        if not collection_id:
            return {}

        # 모든 검색을 동시에 실행
        tasks = []
        for i, query_params in enumerate(queries):
            task = self._single_search_task(i, query_params, collection_id)
            tasks.append(task)

        # 동시 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 취합
        batch_results = {}
        for i, result in enumerate(results):
            query_key = f"query_{i}"
            if isinstance(result, Exception):
                print(f"❌ 배치 검색 {i} 실패: {result}")
                batch_results[query_key] = []
            else:
                batch_results[query_key] = result

        print(f"✅ 배치 검색 완료: {len(batch_results)}개 결과")
        return batch_results

    async def _single_search_task(
        self,
        task_id: int,
        query_params: Dict[str, Any],
        collection_id: str
    ) -> List[Document]:
        """단일 검색 태스크"""
        try:
            return await self.search_places_optimized(
                query=query_params.get('query', ''),
                regions=query_params.get('regions', []),
                cities=query_params.get('cities', []),
                categories=query_params.get('categories', []),
                limit=query_params.get('limit', 1000)
            )
        except Exception as e:
            print(f"❌ 배치 검색 태스크 {task_id} 오류: {e}")
            return []

    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        cache_hit_rate = (
            self.metrics.cache_hits / max(self.metrics.cache_hits + self.metrics.cache_misses, 1)
        )

        return {
            "query_count": self.metrics.query_count,
            "cache_hit_rate": cache_hit_rate,
            "avg_response_time": self.metrics.avg_response_time,
            "cache_size": len(self.query_cache),
            "metadata_cache_size": len(self.metadata_cache),
            "slow_queries_count": len(self.metrics.slow_queries),
            "pool_status": {
                "pool_size": self.sync_engine.pool.size(),
                "checked_in": self.sync_engine.pool.checkedin(),
                "checked_out": self.sync_engine.pool.checkedout(),
                "overflow": self.sync_engine.pool.overflow()
            }
        }

    def clear_cache(self):
        """캐시 초기화"""
        self.query_cache.clear()
        self.metadata_cache.clear()
        print("🧹 데이터베이스 캐시 초기화 완료")

    async def warm_up_cache(self, common_queries: List[Dict]):
        """캐시 예열"""
        print(f"🔥 데이터베이스 캐시 예열 시작: {len(common_queries)}개 쿼리")

        # 카탈로그 먼저 로드
        await self.get_db_catalogs_optimized()

        # 일반적인 검색 쿼리들 예열
        for query_params in common_queries:
            await self.search_places_optimized(**query_params)

        print(f"✅ 캐시 예열 완료: {len(self.query_cache)}개 쿼리, {len(self.metadata_cache)}개 메타데이터")

    async def close(self):
        """리소스 정리"""
        await self.async_engine.dispose()
        self.sync_engine.dispose()
        print("✅ 데이터베이스 연결 정리 완료")


class DatabaseConnectionPool:
    """데이터베이스 연결 풀 관리자"""

    def __init__(self, database_url: str, **pool_config):
        self.database_url = database_url
        self.pool_config = pool_config
        self._manager: Optional[OptimizedDatabaseManager] = None

    async def get_manager(self) -> OptimizedDatabaseManager:
        """데이터베이스 매니저 조회 (싱글톤)"""
        if self._manager is None:
            self._manager = OptimizedDatabaseManager(self.database_url, **self.pool_config)
            # 캐시 예열
            common_queries = [
                {"query": "서울 여행", "cities": ["서울"], "limit": 100},
                {"query": "부산 여행", "cities": ["부산"], "limit": 100},
                {"query": "제주 여행", "cities": ["제주"], "limit": 100},
                {"query": "맛집", "categories": ["음식", "맛집"], "limit": 50},
                {"query": "관광지", "categories": ["관광", "문화"], "limit": 50}
            ]
            await self._manager.warm_up_cache(common_queries)

        return self._manager

    async def close(self):
        """연결 풀 종료"""
        if self._manager:
            await self._manager.close()
            self._manager = None


# 전역 연결 풀 인스턴스
_global_pool: Optional[DatabaseConnectionPool] = None


def get_database_pool() -> DatabaseConnectionPool:
    """전역 데이터베이스 풀 조회"""
    global _global_pool
    if _global_pool is None:
        # 환경 변수에서 데이터베이스 URL 읽기
        import os
        database_url = os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/db')

        _global_pool = DatabaseConnectionPool(
            database_url=database_url,
            pool_size=20,
            max_overflow=30,
            pool_recycle=3600,
            cache_size=1000,
            cache_ttl=3600
        )

    return _global_pool


async def get_optimized_database() -> OptimizedDatabaseManager:
    """최적화된 데이터베이스 매니저 조회"""
    pool = get_database_pool()
    return await pool.get_manager()


# 편의 함수들
async def search_places_fast(
    query: str,
    regions: List[str] = None,
    cities: List[str] = None,
    categories: List[str] = None,
    limit: int = 1000
) -> List[Document]:
    """빠른 장소 검색"""
    db = await get_optimized_database()
    return await db.search_places_optimized(
        query=query,
        regions=regions,
        cities=cities,
        categories=categories,
        limit=limit
    )


async def get_catalogs_fast() -> Dict[str, List[str]]:
    """빠른 카탈로그 조회"""
    db = await get_optimized_database()
    return await db.get_db_catalogs_optimized()