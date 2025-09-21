"""
데이터베이스 및 검색 관련 기능들
"""
import re
from typing import List, Any, Dict
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from sqlalchemy import text
from database import engine as shared_engine
from core.travel_context import TravelContext, get_travel_context


# 숙소 카테고리 상수화 (보안 개선)
ACCOMMODATION_CATEGORIES = ['숙소', '호텔', '펜션', '모텔', '게스트하우스', '리조트', '한옥', '관광호텔', '유스호스텔']


def is_accommodation(category: str) -> bool:
    """숙소 카테고리 여부 판단"""
    return any(keyword in category for keyword in ACCOMMODATION_CATEGORIES)


def load_db_catalogs() -> Dict[str, List[str]]:
    """데이터베이스에서 지역, 도시, 카테고리 카탈로그 로드"""
    try:
        engine = shared_engine
        catalogs = {
            "regions": [],
            "cities": [],
            "categories": []
        }

        with engine.connect() as conn:
            # 지역 목록 로드
            regions_query = text("""
                SELECT DISTINCT cmetadata->>'region' as region
                FROM langchain_pg_embedding
                WHERE cmetadata->>'region' IS NOT NULL
                AND cmetadata->>'region' != ''
                ORDER BY region
            """)
            regions_result = conn.execute(regions_query).fetchall()
            catalogs["regions"] = [row.region for row in regions_result if row.region]

            # 도시 목록 로드
            cities_query = text("""
                SELECT DISTINCT cmetadata->>'city' as city
                FROM langchain_pg_embedding
                WHERE cmetadata->>'city' IS NOT NULL
                AND cmetadata->>'city' != ''
                ORDER BY city
            """)
            cities_result = conn.execute(cities_query).fetchall()
            catalogs["cities"] = [row.city for row in cities_result if row.city]

            # 카테고리 목록 로드
            categories_query = text("""
                SELECT DISTINCT cmetadata->>'category' as category
                FROM langchain_pg_embedding
                WHERE cmetadata->>'category' IS NOT NULL
                AND cmetadata->>'category' != ''
                ORDER BY category
            """)
            categories_result = conn.execute(categories_query).fetchall()
            catalogs["categories"] = [row.category for row in categories_result if row.category]

        print(f"✅ DB 카탈로그 로드 완료:")
        print(f"   - 지역: {len(catalogs['regions'])}개")
        print(f"   - 도시: {len(catalogs['cities'])}개")
        print(f"   - 카테고리: {len(catalogs['categories'])}개")

        return catalogs

    except Exception as e:
        print(f"❌ DB 카탈로그 로드 실패: {e}")
        return {"regions": [], "cities": [], "categories": []}


def normalize_entities(entities: dict, use_fuzzy: bool = True) -> dict:
    """DB 카탈로그를 기반으로 엔티티 정규화"""
    context = get_travel_context()
    db_catalogs = context.db_catalogs

    if not db_catalogs:
        print("⚠️ DB 카탈로그가 로드되지 않음")
        return entities

    normalized = {
        "regions": [],
        "cities": [],
        "categories": []
    }

    # 지역명 정규화
    for region in entities.get("regions", []):
        for db_region in db_catalogs["regions"]:
            if (region.lower() in db_region.lower() or
                db_region.lower() in region.lower()):
                if db_region not in normalized["regions"]:
                    normalized["regions"].append(db_region)
                break

    # 도시명 정규화
    for city in entities.get("cities", []):
        for db_city in db_catalogs["cities"]:
            if (city.lower() in db_city.lower() or
                db_city.lower() in city.lower()):
                if db_city not in normalized["cities"]:
                    normalized["cities"].append(db_city)
                break

    # 카테고리 정규화
    for category in entities.get("categories", []):
        for db_category in db_catalogs["categories"]:
            if (category.lower() in db_category.lower() or
                db_category.lower() in category.lower()):
                if db_category not in normalized["categories"]:
                    normalized["categories"].append(db_category)
                break

    print(f"🔧 엔티티 정규화 완료:")
    print(f"   원본 → 정규화")
    print(f"   지역: {entities.get('regions', [])} → {normalized['regions']}")
    print(f"   도시: {entities.get('cities', [])} → {normalized['cities']}")
    print(f"   카테고리: {entities.get('categories', [])} → {normalized['categories']}")

    return normalized


class HybridOptimizedRetriever(BaseRetriever):
    """SQL 필터링 + 벡터 유사도를 결합한 하이브리드 검색기"""

    vectorstore: Any = None
    k: int = 10000  # SQL 필터링으로 축소된 후보군에서 벡터 검색
    score_threshold: float = 0.5
    max_sql_results: int = 5000  # SQL 필터링 최대 결과 수

    def __init__(self, vectorstore, k: int = 10000, score_threshold: float = 0.5, max_sql_results: int = 5000):
        super().__init__()
        self.vectorstore = vectorstore
        self.k = k
        self.score_threshold = score_threshold
        self.max_sql_results = max_sql_results

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """하이브리드 검색: SQL 1차 필터링 + 벡터 2차 검색"""
        try:
            print(f"🔍 하이브리드 검색 쿼리: '{query}'")

            # 1단계: 지역/카테고리 추출
            from utils.entity_extractor import detect_query_entities
            context = get_travel_context()
            entities = detect_query_entities(query, context.llm, context.db_catalogs)
            regions = entities.get('regions', [])
            cities = entities.get('cities', [])
            categories = entities.get('categories', [])

            print(f"   추출된 정보 - 지역: {regions}, 도시: {cities}, 카테고리: {categories}")

            # 2단계: 도시 우선 검색 로직
            candidate_docs = self._city_first_search(query, regions, cities, categories)

            if not candidate_docs:
                print("⚠️ SQL 필터링 결과 없음, 전체 벡터 검색 실행")
                docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=min(500, self.k))
                filtered_docs = []
                for doc, score in docs_with_scores:
                    if score >= self.score_threshold:
                        doc.metadata['similarity_score'] = round(score, 3)
                        doc.metadata['search_method'] = 'pgvector_full'
                        filtered_docs.append(doc)
                print(f"✅ 전체 벡터 검색 완료: {len(filtered_docs)}개 문서")
                return filtered_docs

            print(f"📊 SQL 필터링: {len(candidate_docs)}개 후보 문서 선별")

            # 3단계: 선별된 후보군에 대해 벡터 유사도 계산
            final_docs = self._vector_search_on_candidates(query, candidate_docs)

            print(f"✅ 최종 결과: {len(final_docs)}개 문서 (임계값 ≥{self.score_threshold})")
            return final_docs

        except Exception as e:
            print(f"❌ HybridOptimizedRetriever 오류: {e}")
            return []

    def _city_first_search(self, query: str, regions: List[str], cities: List[str], categories: List[str]) -> List[Document]:
        """도시 우선 검색 - 도시만으로 먼저 검색하고, 결과 부족시 지역으로 확대"""
        try:
            MIN_CITY_RESULTS = 10  # 도시 검색 최소 결과 수

            # 1단계: 도시만으로 검색
            if cities:
                print(f"🎯 1단계: 도시 우선 검색 - {cities}")
                city_docs = self._sql_filter_candidates(query, [], cities, categories)
                print(f"   도시 검색 결과: {len(city_docs)}개")

                if len(city_docs) >= MIN_CITY_RESULTS:
                    print(f"✅ 도시 검색으로 충분한 결과({len(city_docs)}개) 확보, 지역 확장 없이 진행")
                    return city_docs
                else:
                    print(f"⚠️ 도시 검색 결과 부족({len(city_docs)}개 < {MIN_CITY_RESULTS}개), 지역으로 확대 검색")

            # 2단계: 지역으로 확대 검색 (기존 로직)
            if regions or cities:
                print(f"🌐 2단계: 지역 확대 검색 - 지역: {regions}, 도시: {cities}")
                expanded_docs = self._sql_filter_candidates(query, regions, cities, categories)
                print(f"   확대 검색 결과: {len(expanded_docs)}개")
                return expanded_docs

            # 3단계: 모든 조건이 없으면 기존 로직
            return self._sql_filter_candidates(query, regions, cities, categories)

        except Exception as e:
            print(f"❌ 도시 우선 검색 오류: {e}")
            return []

    def _sql_filter_candidates(self, query: str, regions: List[str], cities: List[str], categories: List[str]) -> List[Document]:
        """SQL 쿼리로 후보 문서들을 먼저 필터링"""
        try:
            engine = shared_engine

            # 조건이 없으면 전체 검색 실행
            if not regions and not cities and not categories:
                print("🔍 지역/카테고리 정보 없음, 전체 텍스트 검색 실행")
                sql_query = text("""
                    SELECT document, cmetadata
                    FROM langchain_pg_embedding
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'place_recommendations')
                    ORDER BY RANDOM()
                    LIMIT :limit
                """)

                with engine.connect() as conn:
                    results = conn.execute(sql_query, {"limit": min(self.max_sql_results, 1000)}).fetchall()

                docs = []
                for row in results:
                    metadata = row.cmetadata or {}
                    metadata['search_method'] = 'sql_random'
                    docs.append(Document(page_content=row.document, metadata=metadata))

                print(f"📊 전체 텍스트 검색: {len(docs)}개 문서 반환")
                return docs

            # SQL 조건 구성
            conditions = []

            # SQL 조건과 파라미터 구성
            params = {}
            param_counter = 0

            if regions:
                region_conditions = []
                for region in regions:
                    # 서울특별시 -> 서울로 변환하여 검색
                    region_simple = region.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '')
                    param_name = f"region_{param_counter}"
                    region_conditions.append(f"cmetadata->>'region' ILIKE :{param_name}")
                    params[param_name] = f'%{region_simple}%'
                    param_counter += 1
                conditions.append(f"({' OR '.join(region_conditions)})")

            if cities:
                city_conditions = []
                for city in cities:
                    # city 필드와 region 필드 모두에서 검색 (서울의 경우)
                    city_simple = city.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '')

                    # city 필드 검색
                    city_param = f"city_{param_counter}"
                    city_conditions.append(f"cmetadata->>'city' ILIKE :{city_param}")
                    params[city_param] = f'%{city_simple}%'
                    param_counter += 1

                    # region 필드 검색
                    region_param = f"city_region_{param_counter}"
                    city_conditions.append(f"cmetadata->>'region' ILIKE :{region_param}")
                    params[region_param] = f'%{city_simple}%'
                    param_counter += 1

                conditions.append(f"({' OR '.join(city_conditions)})")

            if categories:
                category_conditions = []
                for category in categories:
                    param_name = f"category_{param_counter}"
                    category_conditions.append(f"cmetadata->>'category' ILIKE :{param_name}")
                    params[param_name] = f'%{category}%'
                    param_counter += 1
                conditions.append(f"({' OR '.join(category_conditions)})")

            where_clause = " OR ".join(conditions)

            # 숙소 필터링을 위한 파라미터 추가
            for i, accommodation in enumerate(ACCOMMODATION_CATEGORIES):
                param_name = f"exclude_accommodation_{i}"
                params[param_name] = f'%{accommodation}%'

            # 숙소 제외 조건 구성
            accommodation_excludes = " AND ".join([
                f"cmetadata->>'category' NOT ILIKE :exclude_accommodation_{i}"
                for i in range(len(ACCOMMODATION_CATEGORIES))
            ])

            params['max_results'] = self.max_sql_results

            sql_query = f"""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding
                WHERE ({where_clause})
                AND {accommodation_excludes}
                LIMIT :max_results
            """

            print(f"🗄️ SQL 필터링 실행 (파라미터 바인딩)...")

            with engine.connect() as conn:
                result = conn.execute(text(sql_query), params)
                rows = result.fetchall()

                docs = []
                for row in rows:
                    doc = Document(
                        page_content=row.document,
                        metadata=row.cmetadata or {}
                    )
                    # 임베딩 정보도 저장 (벡터 검색용)
                    if row.embedding:
                        doc.metadata['_embedding'] = row.embedding
                    docs.append(doc)

                return docs

        except Exception as e:
            print(f"❌ SQL 필터링 오류: {e}")
            return []

    def _vector_search_on_candidates(self, query: str, candidate_docs: List[Document]) -> List[Document]:
        """PGVector를 사용한 벡터 유사도 계산"""
        try:
            # PGVector 벡터 검색
            print("🔄 PGVector 벡터 검색")
            all_docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=self.k)

            # 후보 문서의 내용으로 매칭
            candidate_contents = {doc.page_content for doc in candidate_docs}

            filtered_docs = []
            for doc, score in all_docs_with_scores:
                # 숙소 카테고리 필터링
                category = doc.metadata.get('category', '')
                accommodation_keywords = ['숙소', '호텔', '펜션', '모텔', '게스트하우스', '리조트', '한옥', '관광호텔', '유스호스텔', '텔', '레지던스']
                is_accommodation = any(keyword in category for keyword in accommodation_keywords)

                if is_accommodation:
                    print(f"🚫 PGVector 숙소 필터링: {category} - {doc.page_content[:30]}...")
                    continue

                if doc.page_content in candidate_contents and score >= self.score_threshold:
                    # 유사도 점수를 metadata에 추가
                    doc.metadata['similarity_score'] = round(score, 3)
                    doc.metadata['search_method'] = 'pgvector_hybrid'
                    filtered_docs.append(doc)

                    # 충분한 결과를 얻으면 중단 (성능 최적화)
                    if len(filtered_docs) >= 50:
                        break

            print(f"✅ PGVector 검색 완료: {len(filtered_docs)}개 문서")
            return filtered_docs

        except Exception as e:
            print(f"❌ 벡터 유사도 계산 오류: {e}")
            return []


def search_places(query, target_categories=None):
    """기본 장소 검색 함수"""
    context = get_travel_context()
    if not context.retriever:
        return []

    try:
        if target_categories:
            # 카테고리별 검색 로직
            docs = context.retriever._city_first_search_with_categories(
                query, [], [], target_categories
            )
        else:
            # 일반 검색
            docs = context.retriever._get_relevant_documents(query)

        return docs

    except Exception as e:
        print(f"❌ 장소 검색 오류: {e}")
        return []


def search_places_by_type(query, regions, cities):
    """타입별 장소 검색"""
    context = get_travel_context()
    if not context.retriever:
        return []

    try:
        # 여행지와 음식점 분리 검색
        travel_docs = search_places_with_filter(query, regions, cities, ["관광지", "자연", "역사"])
        food_docs = search_places_with_filter(query, regions, cities, ["맛집", "카페", "음식"])

        # 결합 및 중복 제거
        all_docs = travel_docs + food_docs
        unique_docs = []
        seen_contents = set()

        for doc in all_docs:
            if doc.page_content not in seen_contents:
                seen_contents.add(doc.page_content)
                unique_docs.append(doc)

        return unique_docs[:50]  # 상위 50개 제한

    except Exception as e:
        print(f"❌ 타입별 장소 검색 오류: {e}")
        return []


def search_places_with_filter(query, regions, cities, target_categories):
    """필터를 적용한 장소 검색"""
    context = get_travel_context()
    if not context.retriever:
        return []

    try:
        docs = context.retriever._sql_filter_candidates(query, regions, cities, target_categories)
        return docs[:30]  # 상위 30개 제한

    except Exception as e:
        print(f"❌ 필터 장소 검색 오류: {e}")
        return []


def initialize_retriever(vectorstore):
    """Retriever 초기화 및 컨텍스트에 설정"""
    retriever = HybridOptimizedRetriever(
        vectorstore=vectorstore,
        k=10000,
        score_threshold=0.5,
        max_sql_results=5000
    )

    # 컨텍스트에 retriever 설정
    context = get_travel_context()
    context.retriever = retriever
    context.vectorstore = vectorstore

    # DB 카탈로그 로드
    db_catalogs = load_db_catalogs()
    context.db_catalogs = db_catalogs

    print("✅ 데이터베이스 및 검색 시스템 초기화 완료")
    return retriever