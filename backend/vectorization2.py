# 파일명: vectorization2.py (완전 개선 버전)

import numpy as np
import asyncpg
import logging
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import time

# 통합 설정 파일 사용 (backend 환경 대응)
try:
    from recommendation_config import config as CONFIG
except ImportError:
    try:
        from .recommendation_config import config as CONFIG
    except ImportError:
        # Fallback 설정
        from dataclasses import dataclass
        @dataclass
        class FallbackConfig:
            database_url: str = "postgresql://user:pass@localhost/db"
            min_pool_size: int = 3
            max_pool_size: int = 15
            db_timeout: int = 5
            candidate_limit: int = 2000
            similarity_weight: float = 0.5
            popularity_weight: float = 0.5
            min_similarity_threshold: float = 0.1
            vector_cache_size: int = 1000
            cache_ttl_seconds: int = 300
            action_weights: Dict[str, float] = None
            preference_weights: Dict[str, float] = None
            travel_style_bonuses: Dict[str, Dict[str, float]] = None
            def __post_init__(self):
                if self.action_weights is None:
                    self.action_weights = {'click': 1.0, 'like': 3.0, 'bookmark': 5.0}
                if self.preference_weights is None:
                    self.preference_weights = {'region': 0.4, 'category': 0.3, 'tag': 0.3, 'max_tag_score': 10.0, 'popularity_normalizer': 1000.0}
                if self.travel_style_bonuses is None:
                    self.travel_style_bonuses = {'luxury': {'accommodation': 0.1, 'restaurants': 0.1}}
        CONFIG = FallbackConfig()
        CONFIG.__post_init__()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# 🔧 유틸리티 함수들
# ============================================================================

def safe_cosine_similarity(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """안전한 코사인 유사도 계산 (모든 에지 케이스 처리)"""
    try:
        # None 값 검증
        if X is None or Y is None:
            return np.array([0.0])

        # 입력을 numpy 배열로 변환
        X = np.asarray(X, dtype=np.float32)
        Y = np.asarray(Y, dtype=np.float32)

        # 빈 배열 검증
        if X.size == 0 or Y.size == 0:
            return np.array([0.0])

        # 차원 맞추기
        X = X.reshape(1, -1)
        if Y.ndim == 1:
            Y = Y.reshape(1, -1)

        # 차원 일치 확인
        if X.shape[1] != Y.shape[1]:
            logger.warning(f"Vector dimension mismatch: X={X.shape[1]}, Y={Y.shape[1]}")
            return np.zeros(Y.shape[0])

        # NaN/Inf 값 처리
        X = np.nan_to_num(X, nan=0.0, posinf=1.0, neginf=-1.0)
        Y = np.nan_to_num(Y, nan=0.0, posinf=1.0, neginf=-1.0)

        # 정규화 (0으로 나누기 방지)
        X_norm = np.linalg.norm(X, axis=1, keepdims=True)
        Y_norm = np.linalg.norm(Y, axis=1, keepdims=True)

        # 0 벡터 처리
        if np.any(X_norm == 0) or np.any(Y_norm == 0):
            return np.zeros(Y.shape[0])

        X_normalized = X / X_norm
        Y_normalized = Y / Y_norm

        # 코사인 유사도 계산
        similarities = np.dot(X_normalized, Y_normalized.T).flatten()

        # 최종 NaN/Inf 값 처리
        similarities = np.nan_to_num(similarities, nan=0.0, posinf=1.0, neginf=-1.0)

        # 유사도 범위 클리핑 (-1 ~ 1)
        similarities = np.clip(similarities, -1.0, 1.0)

        return similarities

    except Exception as e:
        logger.error(f"❌ Cosine similarity calculation failed: {e}")
        # 안전한 기본값 반환
        try:
            return np.zeros(Y.shape[0] if hasattr(Y, 'shape') and Y.ndim > 1 else 1)
        except:
            return np.array([0.0])


def calculate_weighted_popularity_score(place_data: Dict[str, int]) -> float:
    """가중치 기반 인기도 점수 계산 (개선된 정규화)"""
    try:
        weighted_score = (
            place_data.get('total_clicks', 0) * CONFIG.action_weights['click'] +
            place_data.get('total_likes', 0) * CONFIG.action_weights['like'] +
            place_data.get('total_bookmarks', 0) * CONFIG.action_weights['bookmark']
        )

        # 동적 정규화 (상위 1% 기준점 사용)
        reference_score = 100  # 기본 기준점, 실제로는 통계 기반으로 동적 계산 가능
        normalized_score = min((weighted_score / reference_score) * 100, 100)

        return round(normalized_score, 2)

    except Exception as e:
        logger.error(f"❌ Popularity score calculation failed: {e}")
        return 0.0


def calculate_engagement_score(place_data: Dict[str, int]) -> float:
    """참여도 점수 계산 (like/bookmark 비율 기반)"""
    try:
        total_interactions = (
            place_data.get('total_clicks', 0) +
            place_data.get('total_likes', 0) +
            place_data.get('total_bookmarks', 0)
        )

        if total_interactions == 0:
            return 0.0

        high_value_actions = place_data.get('total_likes', 0) + place_data.get('total_bookmarks', 0)
        engagement_ratio = high_value_actions / total_interactions

        # 절대값 보정 추가
        min_threshold_bonus = min(high_value_actions * 2, 20)  # 최대 20점 보너스
        final_score = min((engagement_ratio * 100) + min_threshold_bonus, 100)

        return round(final_score, 2)

    except Exception as e:
        logger.error(f"❌ Engagement score calculation failed: {e}")
        return 0.0


def validate_vector_data(vector_data: Any) -> Optional[np.ndarray]:
    """벡터 데이터 검증 및 변환 (PostgreSQL vector 타입 및 ARRAY 타입 지원)"""
    try:
        if vector_data is None:
            return None

        # PostgreSQL ARRAY 타입 처리 (user_behavior_vectors.behavior_vector)
        if isinstance(vector_data, list):
            vector = np.array(vector_data, dtype=np.float32)

        # PostgreSQL vector 타입 문자열 처리 (place_recommendations.vector, posts.image_vector)
        elif isinstance(vector_data, str):
            # vector 타입은 "[1,2,3]" 형태의 문자열
            if vector_data.startswith('[') and vector_data.endswith(']'):
                # PostgreSQL vector 타입 파싱
                vector_str = vector_data.strip('[]')
                if vector_str:
                    vector_list = [float(x.strip()) for x in vector_str.split(',')]
                    vector = np.array(vector_list, dtype=np.float32)
                else:
                    return None
            else:
                # JSON 문자열 시도
                vector_data = json.loads(vector_data)
                vector = np.array(vector_data, dtype=np.float32)

        # 이미 numpy 배열인 경우
        elif isinstance(vector_data, np.ndarray):
            vector = vector_data.astype(np.float32)

        # 기타 숫자 타입
        else:
            vector = np.array(vector_data, dtype=np.float32)

        # 차원 및 유효성 검사
        if vector.size == 0:
            return None

        if np.isnan(vector).any() or np.isinf(vector).any():
            logger.warning("Vector contains NaN or Inf values")
            return None

        return vector

    except Exception as e:
        logger.error(f"❌ Vector validation failed: {e}")
        return None


# ============================================================================
# 🗄️ 데이터베이스 관리 클래스
# ============================================================================

class DatabaseManager:
    """데이터베이스 연결 및 쿼리 관리"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self._initialized = False

    async def initialize(self):
        """Connection Pool 초기화"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=CONFIG.min_pool_size,
                max_size=CONFIG.max_pool_size,
                command_timeout=CONFIG.db_timeout,
                server_settings={
                    'application_name': 'unified_recommendation_engine'
                }
            )
            self._initialized = True
            logger.info(f"✅ Database pool initialized: {CONFIG.min_pool_size}-{CONFIG.max_pool_size} connections")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database pool: {e}")
            raise

    async def close(self):
        """Connection Pool 정리"""
        if self.pool:
            await self.pool.close()
            logger.info("🔌 Database pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """안전한 DB 연결 컨텍스트 매니저"""
        if not self._initialized or not self.pool:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")

        connection = None
        try:
            connection = await self.pool.acquire()
            yield connection
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            raise
        finally:
            if connection:
                await self.pool.release(connection)

    async def execute_query(self, query: str, *args) -> List[Dict]:
        """안전한 쿼리 실행"""
        async with self.get_connection() as conn:
            try:
                result = await conn.fetch(query, *args)
                return [dict(row) for row in result]
            except Exception as e:
                logger.error(f"❌ Query execution failed: {query[:100]}... Error: {e}")
                raise

    async def execute_single_query(self, query: str, *args) -> Optional[Any]:
        """단일 값 쿼리 실행"""
        async with self.get_connection() as conn:
            try:
                return await conn.fetchval(query, *args)
            except Exception as e:
                logger.error(f"❌ Single query execution failed: {query[:100]}... Error: {e}")
                raise


# ============================================================================
# 🎯 통합 추천 엔진 (완전 개선 버전)
# ============================================================================

class UnifiedRecommendationEngine:
    """
    완전히 개선된 통합 추천 엔진
    - Connection Pool 관리
    - 벡터 캐싱
    - 에러 복구
    - 성능 모니터링
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or CONFIG.database_url
        self.db_manager = DatabaseManager(self.database_url)

        # 캐싱 시스템
        self.vector_cache: Dict[str, Dict] = {}
        self.cache_timestamps: Dict[str, float] = {}

        # 성능 통계
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'personalized_requests': 0,
            'popular_requests': 0,
            'avg_response_time': 0.0
        }

        logger.info("🚀 UnifiedRecommendationEngine v2.0 initialized")

    async def initialize(self):
        """엔진 초기화 (애플리케이션 시작 시 호출)"""
        await self.db_manager.initialize()
        logger.info("✅ Recommendation engine fully initialized")

    async def close(self):
        """리소스 정리"""
        await self.db_manager.close()
        self.vector_cache.clear()
        self.cache_timestamps.clear()
        logger.info("🔌 Recommendation engine closed")

    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 검사"""
        if cache_key not in self.cache_timestamps:
            return False

        age = time.time() - self.cache_timestamps[cache_key]
        return age < CONFIG.cache_ttl_seconds

    def _update_cache(self, cache_key: str, data: Any):
        """캐시 업데이트"""
        if len(self.vector_cache) >= CONFIG.vector_cache_size:
            # LRU 방식으로 가장 오래된 항목 제거
            oldest_key = min(self.cache_timestamps.keys(),
                           key=lambda k: self.cache_timestamps[k])
            del self.vector_cache[oldest_key]
            del self.cache_timestamps[oldest_key]

        self.vector_cache[cache_key] = data
        self.cache_timestamps[cache_key] = time.time()

    async def get_recommendations(
        self,
        user_id: Optional[str],
        region: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        메인 추천 API (완전 개선 버전)
        """
        start_time = time.time()
        self.stats['total_requests'] += 1

        try:
            # 파라미터 검증
            limit = max(1, min(limit, 100))  # 1-100 사이로 제한

            user_vector = None
            if user_id:
                user_vector = await self._get_user_behavior_vector_cached(user_id)
                logger.info(f"DEBUG: User {user_id} vector status: {user_vector is not None}")
                if user_vector is not None:
                    logger.info(f"DEBUG: User vector shape: {user_vector.shape if hasattr(user_vector, 'shape') else 'no shape'}")

            if user_vector is not None:
                logger.info(f"🎯 Personalized recommendations for user {user_id}")
                self.stats['personalized_requests'] += 1

                # 북마크 기반 카테고리 선호도 추가 반영
                bookmark_preferences = await self._get_user_bookmark_preferences(user_id)

                # 다중 벡터 기반 추천 (텍스트+이미지 하이브리드)
                result = await self._get_multi_vector_recommendations(
                    user_id, user_vector, bookmark_preferences, region, category, limit
                )
            else:
                # 신규 가입자를 위한 선호도 기반 추천 시도
                if user_id:
                    preferences_result = await self._get_preference_based_recommendations(
                        user_id, region, category, limit
                    )
                    if preferences_result:
                        logger.info(f"🌱 Preference-based recommendations for new user {user_id}")
                        self.stats['preference_requests'] = self.stats.get('preference_requests', 0) + 1
                        result = preferences_result
                    else:
                        logger.info(f"📊 Popular recommendations for user {user_id} (no preferences found)")
                        self.stats['popular_requests'] += 1
                        result = await self._get_popular_recommendations(
                            region, category, limit
                        )
                else:
                    logger.info(f"📊 Popular recommendations (anonymous user)")
                    self.stats['popular_requests'] += 1
                    result = await self._get_popular_recommendations(
                        region, category, limit
                    )

            # 응답 시간 업데이트
            response_time = time.time() - start_time
            self._update_response_time(response_time)

            logger.info(f"✅ Returned {len(result)} recommendations in {response_time:.3f}s")
            return result

        except Exception as e:
            logger.error(f"❌ Recommendation failed: {e}")
            # 빈 결과라도 안전하게 반환
            return []

    async def _get_user_behavior_vector_cached(self, user_id: str) -> Optional[np.ndarray]:
        """캐시를 활용한 사용자 벡터 조회 (PostgreSQL ARRAY 타입 지원)"""
        cache_key = f"user_vector:{user_id}"

        # 캐시 확인
        if self._is_cache_valid(cache_key):
            self.stats['cache_hits'] += 1
            cached_data = self.vector_cache[cache_key]
            if cached_data is not None:
                return np.array(cached_data, dtype=np.float32)
            return None

        # DB에서 조회 (PostgreSQL ARRAY 타입)
        try:
            query = """
                SELECT behavior_vector
                FROM user_behavior_vectors
                WHERE user_id = $1 AND behavior_vector IS NOT NULL
            """
            vector_data = await self.db_manager.execute_single_query(query, user_id)
            logger.info(f"DEBUG: User {user_id} raw vector data from DB: {vector_data is not None}")

            validated_vector = validate_vector_data(vector_data)
            logger.info(f"DEBUG: User {user_id} validated vector: {validated_vector is not None}")

            # 캐시에 저장 (None도 캐시하여 반복 쿼리 방지)
            if validated_vector is not None:
                self._update_cache(cache_key, validated_vector.tolist())
                return validated_vector
            else:
                self._update_cache(cache_key, None)
                return None

        except Exception as e:
            logger.error(f"❌ Failed to get user vector for {user_id}: {e}")
            return None

    async def _get_user_bookmark_preferences(self, user_id: str) -> Dict[str, float]:
        """사용자 북마크 기반 카테고리 선호도 계산"""
        try:
            query = """
                SELECT places
                FROM saved_locations
                WHERE user_id = $1
            """

            bookmarks = await self.db_manager.execute_query(query, user_id)

            if not bookmarks:
                return {}

            # 카테고리별 북마크 수 계산
            category_counts = {}
            total_bookmarks = 0

            for bookmark in bookmarks:
                places_text = bookmark.get('places', '')
                if ':' in places_text:
                    table_name = places_text.split(':', 1)[0]
                    category_counts[table_name] = category_counts.get(table_name, 0) + 1
                    total_bookmarks += 1

            # 선호도 점수 계산 (비율 기반)
            preferences = {}
            for category, count in category_counts.items():
                preferences[category] = count / total_bookmarks if total_bookmarks > 0 else 0

            logger.info(f"📊 User {user_id} bookmark preferences: {preferences}")
            return preferences

        except Exception as e:
            logger.error(f"❌ Failed to get bookmark preferences for {user_id}: {e}")
            return {}

    def _apply_category_quotas(
        self,
        recommendations: List[Dict],
        bookmark_preferences: Dict[str, float],
        limit: int
    ) -> List[Dict]:
        """북마크 선호도를 바탕으로 카테고리별 할당량을 적용한 균형잡힌 추천"""
        try:
            if not bookmark_preferences or not recommendations:
                return recommendations[:limit]

            # 카테고리별로 추천 분류
            category_recommendations = {}
            for rec in recommendations:
                category = rec.get('table_name', 'unknown')
                if category not in category_recommendations:
                    category_recommendations[category] = []
                category_recommendations[category].append(rec)

            # 선호도 기반 할당량 계산
            result = []
            remaining_slots = limit

            # 다양성 보장: 최소 3개 카테고리는 반드시 포함
            min_categories = min(3, len(category_recommendations))
            max_per_category = max(1, limit // min_categories)

            # 1단계: 주요 선호 카테고리부터 할당
            sorted_preferences = sorted(bookmark_preferences.items(), key=lambda x: x[1], reverse=True)

            for category, preference_rate in sorted_preferences:
                if category not in category_recommendations:
                    continue

                # 더 균형잡힌 할당량 시스템 (다양성 강화)
                if preference_rate > 0.7:  # 70% 이상 매우 강한 선호
                    quota = min(max(int(limit * 0.35), 3), max_per_category + 2)  # 35% 또는 기본+2
                elif preference_rate > 0.4:  # 40% 이상 선호 카테고리
                    quota = min(max(int(limit * 0.25), 2), max_per_category + 1)  # 25% 또는 기본+1
                elif preference_rate > 0.2:  # 20% 이상 선호 카테고리
                    quota = min(max(int(limit * 0.15), 1), max_per_category)  # 15% 또는 기본
                elif preference_rate > 0.05:  # 5% 이상 선호 카테고리
                    quota = min(2, max_per_category)  # 최대 2개 또는 기본
                else:  # 나머지 카테고리
                    quota = 1

                # 실제 할당 가능한 수만큼 추가
                available = min(quota, len(category_recommendations[category]), remaining_slots)
                result.extend(category_recommendations[category][:available])
                remaining_slots -= available

                logger.info(f"📊 {category}: {preference_rate:.3f} -> {available}개 할당")

                if remaining_slots <= 0:
                    break

            # 2단계: 남은 슬롯을 점수순으로 채움
            if remaining_slots > 0:
                used_ids = {rec.get('place_id') for rec in result}
                remaining_recs = [rec for rec in recommendations if rec.get('place_id') not in used_ids]
                result.extend(remaining_recs[:remaining_slots])

            return result[:limit]

        except Exception as e:
            logger.error(f"❌ Category quota application failed: {e}")
            return recommendations[:limit]

    def _apply_category_shuffling(self, recommendations: List[Dict]) -> List[Dict]:
        """카테고리가 적절히 섞이도록 인터리빙 방식으로 재배치"""
        try:
            if len(recommendations) <= 3:
                return recommendations

            # 카테고리별로 그룹화
            category_groups = {}
            for rec in recommendations:
                category = rec.get('table_name', 'unknown')
                if category not in category_groups:
                    category_groups[category] = []
                category_groups[category].append(rec)

            # 카테고리가 2개 이하면 셔플링 불필요
            if len(category_groups) <= 2:
                return recommendations

            logger.info(f"🔄 Shuffling {len(category_groups)} categories for better distribution")

            # 인터리빙 방식으로 재배치
            result = []
            category_indices = {cat: 0 for cat in category_groups.keys()}
            categories = list(category_groups.keys())

            # 라운드 로빈 방식으로 카테고리를 순환하며 배치
            for position in range(len(recommendations)):
                # 현재 라운드에서 사용할 카테고리 선택
                category_idx = position % len(categories)
                current_category = categories[category_idx]

                # 해당 카테고리에서 아직 배치되지 않은 아이템이 있는지 확인
                attempts = 0
                while attempts < len(categories):
                    cat_idx = category_indices[current_category]
                    if cat_idx < len(category_groups[current_category]):
                        # 해당 카테고리에서 아이템 추가
                        result.append(category_groups[current_category][cat_idx])
                        category_indices[current_category] += 1
                        break
                    else:
                        # 해당 카테고리가 소진되면 다음 카테고리로
                        category_idx = (category_idx + 1) % len(categories)
                        current_category = categories[category_idx]
                        attempts += 1

                # 모든 카테고리가 소진되면 종료
                if attempts >= len(categories):
                    break

            # 혹시 남은 아이템들 추가
            for category, items in category_groups.items():
                start_idx = category_indices[category]
                result.extend(items[start_idx:])

            logger.info(f"✅ Category shuffling completed: {len(result)} items redistributed")
            return result[:len(recommendations)]

        except Exception as e:
            logger.error(f"❌ Category shuffling failed: {e}")
            return recommendations

    async def _get_place_candidates(
        self,
        region: Optional[str],
        category: Optional[str]
    ) -> List[Dict]:
        """추천 후보 장소 조회 (최적화된 쿼리)"""
        try:
            # place_recommendations 테이블에서 텍스트 벡터 조회 (PostgreSQL vector 타입)
            query = """
                SELECT
                    pr.place_id::text as place_id,
                    pr.table_name,
                    pr.vector as vector,
                    COALESCE(pr.bookmark_cnt, 0) as total_likes,
                    COALESCE(pr.bookmark_cnt, 0) as total_bookmarks,
                    COALESCE(pr.bookmark_cnt, 0) as total_clicks,
                    1 as unique_users,
                    COALESCE(pr.bookmark_cnt, 0)::float as popularity_score,
                    COALESCE(pr.bookmark_cnt, 0)::float as engagement_score,
                    pr.name,
                    pr.region,
                    pr.city,
                    pr.latitude,
                    pr.longitude,
                    pr.overview as description,
                    pr.image_urls,
                    pr.bookmark_cnt
                FROM place_recommendations pr
                WHERE
                    pr.vector IS NOT NULL
                    AND pr.name IS NOT NULL
                    AND pr.bookmark_cnt IS NOT NULL
            """

            params = []
            param_count = 0

            # 지역 필터
            if region:
                param_count += 1
                query += f" AND pr.region = ${param_count}"
                params.append(region)

            # 카테고리 필터
            if category:
                param_count += 1
                query += f" AND pr.table_name = ${param_count}::text"
                params.append(category)

            # 성능을 위한 제한 및 정렬 (북마크 카운트 기준)
            query += " ORDER BY COALESCE(pr.bookmark_cnt, 0) DESC"
            param_count += 1
            query += f" LIMIT ${param_count}"
            params.append(CONFIG.candidate_limit)

            places = await self.db_manager.execute_query(query, *params)

            # 벡터 데이터 검증
            valid_places = []
            for place in places:
                if validate_vector_data(place['vector']) is not None:
                    valid_places.append(place)

            logger.info(f"📋 Retrieved {len(valid_places)} valid place candidates")
            return valid_places

        except Exception as e:
            logger.error(f"❌ Failed to get place candidates: {e}")
            return []

    async def _get_popular_recommendations(
        self,
        region: Optional[str],
        category: Optional[str],
        limit: int
    ) -> List[Dict]:
        """인기 기반 추천 (단순 북마크 카운트 정렬)"""
        places = await self._get_place_candidates(region, category)

        if not places:
            return []

        # 단순 북마크 카운트 기반 정렬
        for place in places:
            try:
                bookmark_count = place.get('bookmark_cnt', 0)

                place['final_score'] = bookmark_count
                place['recommendation_type'] = 'popular'
                place['similarity_score'] = 0.8  # 인기 추천용 기본값

            except Exception as e:
                logger.error(f"❌ Popular score calculation failed for place {place.get('place_id')}: {e}")
                place['final_score'] = 0

        # 북마크 카운트순 정렬 (내림차순)
        places.sort(key=lambda x: x.get('bookmark_cnt', 0), reverse=True)
        
        # numpy 배열을 리스트로 변환 (JSON 직렬화를 위해)
        for place in places[:limit]:
            if 'vector' in place and isinstance(place['vector'], np.ndarray):
                place['vector'] = place['vector'].tolist()
            if 'text_vector' in place and isinstance(place['text_vector'], np.ndarray):
                place['text_vector'] = place['text_vector'].tolist()
            if 'image_vector' in place and isinstance(place['image_vector'], np.ndarray):
                place['image_vector'] = place['image_vector'].tolist()
        
        return places[:limit]

    async def _get_multi_vector_recommendations(
        self,
        user_id: str,
        user_vector: np.ndarray,
        bookmark_preferences: Dict[str, float],
        region: Optional[str],
        category: Optional[str],
        limit: int
    ) -> List[Dict]:
        """
        다중 벡터 기반 추천 시스템
        - 텍스트-텍스트 유사도 (기존 overview 벡터)
        - 이미지-이미지 유사도 (새로운 image 벡터)
        - 크로스 모달 유사도 (텍스트-이미지, 이미지-텍스트)
        - 북마크 기반 선호도 반영
        """
        try:
            # 장소 후보군 조회 (이미지 벡터 포함)
            places = await self._get_place_candidates_with_images(region, category)

            if not places:
                return []

            # 사용자 행동 데이터 조회 (북마크된 장소의 이미지 벡터, 좋아요한 포스트의 이미지 벡터)
            user_image_preferences = await self._get_user_image_preferences(user_id)

            # 독립적인 다중 벡터 유사도 계산
            multi_scores = await self._calculate_independent_similarities(
                user_id, user_vector, user_image_preferences, places
            )

            # 하이브리드 점수 계산 및 결과 생성
            results = []
            for i, place in enumerate(places):
                if i >= len(multi_scores):
                    logger.warning(f"Missing score for place {i}, using defaults")
                    scores = {
                        'behavior_text_similarity': 0.0,
                        'upload_image_similarity': 0.0,
                        'bookmark_text_similarity': 0.0,
                        'bookmark_image_similarity': 0.0,
                        'liked_post_similarity': 0.0,
                        'combined_score': 0.0
                    }
                else:
                    scores = multi_scores[i]

                try:
                    # 인기도 점수
                    place_data = {
                        'total_clicks': place.get('total_clicks', 0),
                        'total_likes': place.get('total_likes', 0),
                        'total_bookmarks': place.get('total_bookmarks', 0)
                    }
                    popularity_score = calculate_weighted_popularity_score(place_data)
                    engagement_score = calculate_engagement_score(place_data)

                    # 북마크 선호도 보너스
                    category_preference = bookmark_preferences.get(place['table_name'], 0)
                    bookmark_bonus = category_preference * 0.5

                    # 다중 벡터 종합 점수 (독립적 벡터 조합)
                    multi_vector_score = scores.get('combined_score', 0.0)

                    # 최종 하이브리드 점수
                    final_score = (
                        multi_vector_score * CONFIG.similarity_weight +
                        (popularity_score / 100.0) * CONFIG.popularity_weight * 0.7 +
                        (engagement_score / 100.0) * CONFIG.popularity_weight * 0.3 +
                        bookmark_bonus
                    )

                    # 점수가 임계값 이상인 경우만 포함
                    if multi_vector_score >= CONFIG.min_similarity_threshold:
                        place['behavior_text_similarity'] = round(scores.get('behavior_text_similarity', 0.0), 4)
                        place['upload_image_similarity'] = round(scores.get('upload_image_similarity', 0.0), 4)
                        place['bookmark_text_similarity'] = round(scores.get('bookmark_text_similarity', 0.0), 4)
                        place['bookmark_image_similarity'] = round(scores.get('bookmark_image_similarity', 0.0), 4)
                        place['liked_post_similarity'] = round(scores.get('liked_post_similarity', 0.0), 4)
                        place['combined_score'] = round(scores.get('combined_score', 0.0), 4)
                        place['multi_vector_score'] = round(multi_vector_score, 4)
                        place['popularity_score'] = popularity_score
                        place['engagement_score'] = engagement_score
                        place['bookmark_bonus'] = round(bookmark_bonus, 4)
                        place['final_score'] = round(final_score, 4)
                        place['recommendation_type'] = 'five_channel_system'

                        results.append(place)

                except Exception as e:
                    logger.error(f"❌ Multi-vector score calculation failed for place {i}: {e}")
                    continue

            # 점수순 정렬
            results.sort(key=lambda x: x['final_score'], reverse=True)

            logger.info(f"🎯 Multi-vector recommendations: {len(results)} candidates")

            # 카테고리 균형 조정 적용
            balanced_results = self._apply_category_quotas(results, bookmark_preferences, limit)
            final_results = self._apply_category_shuffling(balanced_results)
            
            # numpy 배열을 리스트로 변환 (JSON 직렬화를 위해)
            for result in final_results:
                if 'vector' in result and isinstance(result['vector'], np.ndarray):
                    result['vector'] = result['vector'].tolist()
                if 'text_vector' in result and isinstance(result['text_vector'], np.ndarray):
                    result['text_vector'] = result['text_vector'].tolist()
                if 'image_vector' in result and isinstance(result['image_vector'], np.ndarray):
                    result['image_vector'] = result['image_vector'].tolist()

            return final_results

        except Exception as e:
            logger.error(f"❌ Multi-vector recommendation failed: {e}")
            # Fallback to enhanced vector recommendations
            return await self._get_enhanced_vector_recommendations(
                user_vector, bookmark_preferences, region, category, limit
            )

    async def _get_enhanced_vector_recommendations(
        self,
        user_vector: np.ndarray,
        bookmark_preferences: Dict[str, float],
        region: Optional[str],
        category: Optional[str],
        limit: int
    ) -> List[Dict]:
        """북마크 선호도를 반영한 개선된 벡터 기반 추천 (기존 방식 유지)"""
        places = await self._get_place_candidates(region, category)

        if not places:
            return []

        try:
            # 벡터 배치 처리
            place_vectors = []
            valid_places = []

            for place in places:
                vector = validate_vector_data(place['vector'])
                if vector is not None:
                    place_vectors.append(vector)
                    valid_places.append(place)

            if not valid_places:
                logger.warning("⚠️ No valid place vectors found, falling back to popular")
                return await self._get_popular_recommendations(region, category, limit)

            # 벡터화된 유사도 계산
            place_vectors_array = np.array(place_vectors, dtype=np.float32)
            similarities = safe_cosine_similarity(user_vector, place_vectors_array)

            # 북마크 선호도 강화된 하이브리드 점수 계산
            results = []
            for i, place in enumerate(valid_places):
                try:
                    similarity = float(similarities[i])

                    # 최소 유사도 임계값 적용
                    if similarity < CONFIG.min_similarity_threshold:
                        continue

                    # 기본 인기도 점수
                    place_data = {
                        'total_clicks': place.get('total_clicks', 0),
                        'total_likes': place.get('total_likes', 0),
                        'total_bookmarks': place.get('total_bookmarks', 0)
                    }
                    popularity_score = calculate_weighted_popularity_score(place_data)
                    engagement_score = calculate_engagement_score(place_data)

                    # 🔥 북마크 선호도 보너스 추가 (적절한 강화)
                    category_preference = bookmark_preferences.get(place['table_name'], 0)
                    bookmark_bonus = category_preference * 0.5  # 최대 50% 보너스 (균형잡힌 조정)

                    # 개선된 하이브리드 점수
                    hybrid_score = (
                        similarity * CONFIG.similarity_weight +
                        (popularity_score / 100.0) * CONFIG.popularity_weight * 0.7 +
                        (engagement_score / 100.0) * CONFIG.popularity_weight * 0.3 +
                        bookmark_bonus  # 북마크 선호도 보너스
                    )

                    place['similarity_score'] = round(similarity, 4)
                    place['popularity_score'] = popularity_score
                    place['engagement_score'] = engagement_score
                    place['bookmark_bonus'] = round(bookmark_bonus, 4)
                    place['final_score'] = round(hybrid_score, 4)
                    place['recommendation_type'] = 'personalized_enhanced'

                    results.append(place)

                except Exception as e:
                    logger.error(f"❌ Score calculation failed for place {i}: {e}")
                    continue

            # 점수순 정렬
            results.sort(key=lambda x: x['final_score'], reverse=True)

            # 🎯 카테고리별 보장 추천 시스템 적용
            balanced_results = self._apply_category_quotas(results, bookmark_preferences, limit)

            # 🔄 카테고리 분산을 위한 셔플링 적용
            final_results = self._apply_category_shuffling(balanced_results)

            return final_results

        except Exception as e:
            logger.error(f"❌ Enhanced vector-based recommendation failed: {e}")
            # Fallback to popular recommendations
            return await self._get_popular_recommendations(region, category, limit)

    async def _get_vector_based_recommendations(
        self,
        user_vector: np.ndarray,
        region: Optional[str],
        category: Optional[str],
        limit: int
    ) -> List[Dict]:
        """벡터 유사도 기반 개인화 추천 (최적화된 버전)"""
        places = await self._get_place_candidates(region, category)

        if not places:
            return []

        try:
            # 벡터 배치 처리
            place_vectors = []
            valid_places = []

            for place in places:
                vector = validate_vector_data(place['vector'])
                if vector is not None:
                    place_vectors.append(vector)
                    valid_places.append(place)

            if not valid_places:
                logger.warning("⚠️ No valid place vectors found, falling back to popular")
                return await self._get_popular_recommendations(region, category, limit)

            # 벡터화된 유사도 계산
            place_vectors_array = np.array(place_vectors, dtype=np.float32)
            similarities = safe_cosine_similarity(user_vector, place_vectors_array)

            # 하이브리드 점수 계산
            results = []
            for i, place in enumerate(valid_places):
                try:
                    similarity = float(similarities[i])

                    # 최소 유사도 임계값 적용
                    if similarity < CONFIG.min_similarity_threshold:
                        continue

                    # 인기도 점수 계산
                    place_data = {
                        'total_clicks': place.get('total_clicks', 0),
                        'total_likes': place.get('total_likes', 0),
                        'total_bookmarks': place.get('total_bookmarks', 0)
                    }
                    popularity_score = calculate_weighted_popularity_score(place_data)
                    engagement_score = calculate_engagement_score(place_data)

                    # 하이브리드 점수 (개인화 + 인기도 + 참여도)
                    hybrid_score = (
                        similarity * CONFIG.similarity_weight +
                        (popularity_score / 100.0) * CONFIG.popularity_weight * 0.7 +
                        (engagement_score / 100.0) * CONFIG.popularity_weight * 0.3
                    )

                    place['similarity_score'] = round(similarity, 4)
                    place['popularity_score'] = popularity_score
                    place['engagement_score'] = engagement_score
                    place['final_score'] = round(hybrid_score, 4)
                    place['recommendation_type'] = 'personalized'

                    results.append(place)

                except Exception as e:
                    logger.error(f"❌ Score calculation failed for place {i}: {e}")
                    continue

            # 점수순 정렬
            results.sort(key=lambda x: x['final_score'], reverse=True)

            logger.info(f"🎯 Generated {len(results)} personalized recommendations")
            
            # numpy 배열을 리스트로 변환 (JSON 직렬화를 위해)
            for result in results[:limit]:
                if 'vector' in result and isinstance(result['vector'], np.ndarray):
                    result['vector'] = result['vector'].tolist()
                if 'text_vector' in result and isinstance(result['text_vector'], np.ndarray):
                    result['text_vector'] = result['text_vector'].tolist()
                if 'image_vector' in result and isinstance(result['image_vector'], np.ndarray):
                    result['image_vector'] = result['image_vector'].tolist()
            
            return results[:limit]

        except Exception as e:
            logger.error(f"❌ Vector-based recommendation failed: {e}")
            # Fallback to popular recommendations
            return await self._get_popular_recommendations(region, category, limit)

    def _update_response_time(self, response_time: float):
        """응답 시간 통계 업데이트 (이동평균)"""
        alpha = 0.1  # 이동평균 가중치
        if self.stats['avg_response_time'] == 0.0:
            self.stats['avg_response_time'] = response_time
        else:
            self.stats['avg_response_time'] = (
                alpha * response_time +
                (1 - alpha) * self.stats['avg_response_time']
            )

    def get_stats(self) -> Dict:
        """성능 통계 반환"""
        cache_hit_rate = (
            self.stats['cache_hits'] / max(self.stats['total_requests'], 1)
        ) * 100

        return {
            **self.stats,
            'cache_hit_rate': round(cache_hit_rate, 2),
            'cache_size': len(self.vector_cache),
            'personalization_rate': round(
                (self.stats['personalized_requests'] / max(self.stats['total_requests'], 1)) * 100, 2
            )
        }

    async def get_popular_regions_and_categories(self) -> Dict[str, List[str]]:
        """인기도 기반으로 동적 지역/카테고리 순서 결정"""
        try:
            # 지역별 북마크 총합 조회
            region_query = """
                SELECT region, SUM(COALESCE(bookmark_cnt, 0)) as total_bookmarks
                FROM place_recommendations
                WHERE region IS NOT NULL
                GROUP BY region
                ORDER BY total_bookmarks DESC
                LIMIT 10
            """

            # 카테고리별 북마크 총합 조회
            category_query = """
                SELECT table_name as category, SUM(COALESCE(bookmark_cnt, 0)) as total_bookmarks
                FROM place_recommendations
                WHERE table_name IS NOT NULL
                GROUP BY table_name
                ORDER BY total_bookmarks DESC
                LIMIT 10
            """

            regions_data = await self.db_manager.execute_query(region_query)
            categories_data = await self.db_manager.execute_query(category_query)

            regions = [row['region'] for row in regions_data if row['region']]
            categories = [row['category'] for row in categories_data if row['category']]

            logger.info(f"📊 Dynamic ordering: {len(regions)} regions, {len(categories)} categories")

            return {
                'regions': regions,
                'categories': categories
            }

        except Exception as e:
            logger.error(f"❌ Failed to get dynamic regions/categories: {e}")
            # Fallback to config defaults
            return {
                'regions': CONFIG.explore_regions or [],
                'categories': CONFIG.explore_categories or []
            }

    async def health_check(self) -> Dict[str, Any]:
        """엔진 헬스체크"""
        try:
            # 간단한 DB 연결 테스트
            test_result = await self.db_manager.execute_single_query("SELECT 1")
            db_healthy = test_result == 1

            # 캐시 상태 확인
            cache_healthy = len(self.vector_cache) < CONFIG.vector_cache_size

            # 전체 상태 판단
            overall_healthy = db_healthy and cache_healthy

            return {
                'status': 'healthy' if overall_healthy else 'degraded',
                'database': 'connected' if db_healthy else 'disconnected',
                'cache': 'normal' if cache_healthy else 'full',
                'stats': self.get_stats(),
                'config': {
                    'candidate_limit': CONFIG.candidate_limit,
                    'similarity_weight': CONFIG.similarity_weight,
                    'popularity_weight': CONFIG.popularity_weight
                }
            }

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'stats': self.get_stats()
            }

    async def _get_preference_based_recommendations(
        self,
        user_id: str,
        region: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        신규 가입자를 위한 선호도 기반 추천
        user_preferences와 user_preference_tags 테이블을 활용한 여행 선호도 기반 추천
        """
        try:
            # 1. 사용자 선호도 정보 조회
            user_preferences = await self._get_user_preferences(user_id)
            if not user_preferences:
                logger.info(f"No preferences found for user {user_id}")
                return []

            # 2. 선호도 기반 장소 필터링 및 점수 계산
            recommendations = await self._calculate_preference_scores(
                user_preferences, region, category, limit
            )

            logger.info(f"✅ Generated {len(recommendations)} preference-based recommendations for user {user_id}")
            return recommendations

        except Exception as e:
            logger.error(f"❌ Preference-based recommendation failed for user {user_id}: {e}")
            return []

    async def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 정보 조회 (users 테이블에서 직접 조회)"""
        try:
            # users 테이블에서 선호도 정보 조회 (실제 스키마에 맞게 수정)
            preferences_query = """
                SELECT
                    priority,
                    accommodation,
                    exploration,
                    persona
                FROM users
                WHERE user_id = $1
            """

            # user_preference_tags 테이블에서 태그 정보 조회 (현재 스키마)
            tags_query = """
                SELECT
                    tag,
                    weight
                FROM user_preference_tags
                WHERE user_id = $1
                ORDER BY weight DESC
            """

            # 병렬로 두 쿼리 실행
            async with self.db_manager.get_connection() as conn:
                preferences_data = await conn.fetchrow(preferences_query, user_id)
                tags_data = await conn.fetch(tags_query, user_id)

            if not preferences_data and not tags_data:
                return {}

            # 결과 구성 (현재 스키마에 맞게)
            result = {
                'priority': preferences_data.get('priority') if preferences_data else None,
                'accommodation': preferences_data.get('accommodation') if preferences_data else None,
                'exploration': preferences_data.get('exploration') if preferences_data else None,
                'persona': preferences_data.get('persona') if preferences_data else None,
                'preference_tags': {
                    row['tag']: row['weight']
                    for row in tags_data
                }
            }

            return result

        except Exception as e:
            logger.error(f"❌ Failed to get user preferences for {user_id}: {e}")
            return {}

    async def _calculate_preference_scores(
        self,
        user_preferences: Dict[str, Any],
        region: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """선호도 기반 점수 계산 및 추천 생성"""
        try:
            # 장소 후보군 조회
            places_query = """
                SELECT
                    place_id, table_name, region, name,
                    latitude, longitude, overview, image_urls, bookmark_cnt,
                    COALESCE(bookmark_cnt, 0) as popularity_score
                FROM place_recommendations
                WHERE name IS NOT NULL
                    AND ($1::text IS NULL OR region = $1)
                    AND ($2::text IS NULL OR table_name = $2)
                ORDER BY bookmark_cnt DESC
                LIMIT $3
            """

            async with self.db_manager.get_connection() as conn:
                places_data = await conn.fetch(
                    places_query,
                    region,
                    category,
                    CONFIG.candidate_limit
                )

            if not places_data:
                return []

            # 선호도 점수 계산 및 정렬
            scored_places = []
            popularity_normalizer = CONFIG.preference_weights['popularity_normalizer']

            for place in places_data:
                preference_score = self._calculate_place_preference_score(place, user_preferences)

                if preference_score > 0:
                    place_dict = dict(place)
                    popularity_normalized = min(place['popularity_score'] / popularity_normalizer, 1.0)
                    final_score = (preference_score * CONFIG.similarity_weight) + (popularity_normalized * CONFIG.popularity_weight)

                    place_dict['preference_score'] = preference_score
                    place_dict['final_score'] = final_score
                    scored_places.append(place_dict)

            scored_places.sort(key=lambda x: x['final_score'], reverse=True)
            
            # numpy 배열을 리스트로 변환 (JSON 직렬화를 위해)
            for place in scored_places[:limit]:
                if 'vector' in place and isinstance(place['vector'], np.ndarray):
                    place['vector'] = place['vector'].tolist()
                if 'text_vector' in place and isinstance(place['text_vector'], np.ndarray):
                    place['text_vector'] = place['text_vector'].tolist()
                if 'image_vector' in place and isinstance(place['image_vector'], np.ndarray):
                    place['image_vector'] = place['image_vector'].tolist()
            
            return scored_places[:limit]

        except Exception as e:
            logger.error(f"❌ Failed to calculate preference scores: {e}")
            return []

    def _calculate_place_preference_score(
        self,
        place: Dict[str, Any],
        user_preferences: Dict[str, Any]
    ) -> float:
        """개별 장소에 대한 선호도 점수 계산 (현재 스키마에 맞게 수정)"""
        score = 0.0

        try:
            weights = CONFIG.preference_weights

            # 페르소나 기반 카테고리 선호도
            persona = user_preferences.get('persona')
            if persona and place['table_name']:
                # 페르소나별 카테고리 보너스
                persona_bonuses = {
                    'culture_lover': {'humanities': 0.3, 'culture': 0.3},
                    'nature_lover': {'nature': 0.3, 'leisure_sports': 0.2},
                    'foodie': {'restaurants': 0.4},
                    'shopper': {'shopping': 0.3},
                    'luxury_traveler': {'accommodation': 0.2, 'restaurants': 0.2}
                }

                if persona in persona_bonuses:
                    category_bonus = persona_bonuses[persona].get(place['table_name'], 0)
                    score += category_bonus

            # 우선순위 기반 점수
            priority = user_preferences.get('priority')
            if priority:
                # 우선순위에 따른 가중치
                if priority == 'popular' and place.get('bookmark_cnt', 0) > 1000:
                    score += 0.2
                elif priority == 'unique' and place.get('bookmark_cnt', 0) < 500:
                    score += 0.2

            # 태그 매칭 (현재 스키마)
            preference_tags = user_preferences.get('preference_tags', {})
            if preference_tags:
                place_description = (place.get('description', '') or '').lower()
                place_name = (place.get('name', '') or '').lower()
                combined_text = place_description + ' ' + place_name

                tag_score, tag_count = 0.0, 0

                for tag_name, tag_weight in preference_tags.items():
                    tag_lower = tag_name.lower()
                    if tag_lower in combined_text:
                        # weight는 1-10 스케일로 가정, 정규화
                        normalized_weight = min(tag_weight / 10.0, 1.0)
                        tag_score += normalized_weight
                        tag_count += 1

                if tag_count > 0:
                    # 태그 점수 정규화
                    normalized_tag_score = min(tag_score / tag_count, 1.0)
                    score += normalized_tag_score * weights['tag']

            # 탐험 성향 반영
            exploration = user_preferences.get('exploration')
            if exploration == 'adventurous' and place['table_name'] in ['nature', 'leisure_sports']:
                score += 0.1
            elif exploration == 'comfort' and place['table_name'] in ['accommodation', 'restaurants']:
                score += 0.1

            return min(score, 1.0)

        except Exception as e:
            logger.error(f"❌ Failed to calculate preference score for place {place.get('place_id')}: {e}")
            return 0.0

    async def _get_place_candidates_with_images(
        self,
        region: Optional[str],
        category: Optional[str]
    ) -> List[Dict]:
        """이미지 벡터를 포함한 장소 후보군 조회"""
        try:
            query = """
                SELECT
                    pr.place_id::text as place_id,
                    pr.table_name,
                    pr.vector as text_vector,
                    pr.image_vector,
                    COALESCE(pr.bookmark_cnt, 0) as total_likes,
                    COALESCE(pr.bookmark_cnt, 0) as total_bookmarks,
                    COALESCE(pr.bookmark_cnt, 0) as total_clicks,
                    1 as unique_users,
                    COALESCE(pr.bookmark_cnt, 0)::float as popularity_score,
                    COALESCE(pr.bookmark_cnt, 0)::float as engagement_score,
                    pr.name,
                    pr.region,
                    pr.city,
                    pr.latitude,
                    pr.longitude,
                    pr.overview as description,
                    pr.image_urls,
                    pr.bookmark_cnt
                FROM place_recommendations pr
                WHERE
                    pr.vector IS NOT NULL
                    AND pr.name IS NOT NULL
                    AND pr.bookmark_cnt IS NOT NULL
            """

            params = []
            param_count = 0

            if region:
                param_count += 1
                query += f" AND pr.region = ${param_count}"
                params.append(region)

            if category:
                param_count += 1
                query += f" AND pr.table_name = ${param_count}::text"
                params.append(category)

            query += " ORDER BY COALESCE(pr.bookmark_cnt, 0) DESC"
            param_count += 1
            query += f" LIMIT ${param_count}"
            params.append(CONFIG.candidate_limit)

            places = await self.db_manager.execute_query(query, *params)

            # 텍스트 벡터는 필수, 이미지 벡터는 선택적
            valid_places = []
            for place in places:
                text_vector = validate_vector_data(place['text_vector'])
                if text_vector is not None:
                    place['text_vector'] = text_vector

                    # 이미지 벡터는 있으면 추가, 없으면 None
                    image_vector = validate_vector_data(place.get('image_vector'))
                    place['image_vector'] = image_vector

                    valid_places.append(place)

            logger.info(f"📋 Retrieved {len(valid_places)} places with text vectors ({sum(1 for p in valid_places if p['image_vector'] is not None)} with image vectors)")
            return valid_places

        except Exception as e:
            logger.error(f"❌ Failed to get place candidates with images: {e}")
            return []

    async def _get_user_image_preferences(self, user_id: str) -> Dict[str, np.ndarray]:
        """사용자의 이미지 선호도 벡터 수집 (북마크, 좋아요 기반)"""
        try:

            # 1. 북마크한 장소들의 이미지 벡터 수집
            bookmark_query = """
                SELECT pr.image_vector
                FROM saved_locations sl
                JOIN place_recommendations pr ON pr.place_id = CAST(SPLIT_PART(sl.places, ':', 2) AS INTEGER)
                    AND pr.table_name = SPLIT_PART(sl.places, ':', 1)
                WHERE sl.user_id = $1
                    AND pr.image_vector IS NOT NULL
                LIMIT 20
            """

            # 2. 좋아요한 포스트들의 이미지 벡터 수집 (posts.image_vector는 PostgreSQL vector 타입)
            liked_posts_query = """
                SELECT p.image_vector
                FROM user_actions ua
                JOIN posts p ON p.id = CAST(ua.place_id AS INTEGER)
                WHERE ua.user_id = $1
                    AND ua.action_type = 'like'
                    AND ua.place_category = 'posts'
                    AND p.image_vector IS NOT NULL
                LIMIT 20
            """

            # 3. 사용자가 직접 업로드한 포스트들의 이미지 벡터 수집 (자신의 선호도 반영)
            user_posts_query = """
                SELECT image_vector
                FROM posts
                WHERE user_id = $1
                    AND image_vector IS NOT NULL
                LIMIT 30
            """

            bookmark_vectors = await self.db_manager.execute_query(bookmark_query, user_id)
            liked_post_vectors = await self.db_manager.execute_query(liked_posts_query, user_id)
            user_post_vectors = await self.db_manager.execute_query(user_posts_query, user_id)

            # 벡터 수집 및 검증 (분리된 리스트로)
            bookmark_image_vectors = []
            liked_post_image_vectors = []
            user_upload_image_vectors = []

            # 1. 북마크한 장소 이미지 벡터
            for row in bookmark_vectors:
                vector = validate_vector_data(row['image_vector'])
                if vector is not None:
                    bookmark_image_vectors.append(vector)

            # 2. 좋아요한 포스트 이미지 벡터 (독립적으로 수집)
            for row in liked_post_vectors:
                vector = validate_vector_data(row['image_vector'])
                if vector is not None:
                    liked_post_image_vectors.append(vector)

            # 3. 사용자가 업로드한 포스트 이미지 벡터 (독립적으로 수집)
            for row in user_post_vectors:
                vector = validate_vector_data(row['image_vector'])
                if vector is not None:
                    user_upload_image_vectors.append(vector)

            total_vectors = len(bookmark_image_vectors) + len(liked_post_image_vectors) + len(user_upload_image_vectors)

            if total_vectors == 0:
                logger.info(f"No image preferences found for user {user_id}")
                return {}

            logger.info(f"📸 User {user_id} image preferences: {total_vectors} total vectors (북마크: {len(bookmark_image_vectors)}, 좋아요: {len(liked_post_image_vectors)}, 업로드: {len(user_upload_image_vectors)})")

            return {
                'bookmarks': bookmark_image_vectors,       # 북마크 장소 이미지 (채널4 사용)
                'liked_posts': liked_post_image_vectors,   # 좋아요 포스트 이미지 (채널5 사용)
                'user_uploads': user_upload_image_vectors, # 업로드 포스트 이미지 (채널2 사용)
                'source_breakdown': {
                    'bookmarks': len(bookmark_image_vectors),
                    'liked_posts': len(liked_post_image_vectors),
                    'user_posts': len(user_upload_image_vectors)
                }
            }

        except Exception as e:
            logger.error(f"❌ Failed to get user image preferences for {user_id}: {e}")
            return {}

    async def _calculate_independent_similarities(
        self,
        user_id: str,
        user_behavior_vector: np.ndarray,
        user_image_preferences: Dict[str, Any],
        places: List[Dict]
    ) -> List[Dict[str, float]]:
        """
        독립적인 검색 채널 기반 유사도 계산 (5개 채널)
        1. 행동벡터(클릭/북마크) → 장소 텍스트
        2. 사용자 업로드 포스팅 이미지 → 장소 이미지
        3. 북마크 장소 텍스트 → 다른 장소 텍스트
        4. 북마크 장소 이미지 → 다른 장소 이미지
        5. 좋아요한 포스팅 이미지 → 장소 이미지
        """
        results = []

        try:
            # 이미지 선호도 분리 (업로드 vs 좋아요)
            user_upload_images = user_image_preferences.get('user_uploads', [])
            liked_post_images = user_image_preferences.get('liked_posts', [])

            # 평균 벡터 계산 (안전한 처리)
            user_upload_vector = None
            if user_upload_images and len(user_upload_images) > 0:
                try:
                    user_upload_vector = np.mean(user_upload_images, axis=0)
                except Exception as e:
                    logger.warning(f"Failed to calculate user upload vector mean: {e}")

            liked_posts_vector = None
            if liked_post_images and len(liked_post_images) > 0:
                try:
                    liked_posts_vector = np.mean(liked_post_images, axis=0)
                except Exception as e:
                    logger.warning(f"Failed to calculate liked posts vector mean: {e}")

            # 사용자 북마크 장소 기반 선호도 추출
            bookmark_preferences = await self._get_detailed_bookmark_preferences(user_id)

            for place in places:
                scores = {
                    'behavior_text_similarity': 0.0,     # 행동벡터(클릭/북마크) → 장소텍스트
                    'upload_image_similarity': 0.0,      # 업로드 포스팅이미지 → 장소이미지
                    'bookmark_text_similarity': 0.0,     # 북마크장소텍스트 → 장소텍스트
                    'bookmark_image_similarity': 0.0,    # 북마크장소이미지 → 장소이미지
                    'liked_post_similarity': 0.0,        # 좋아요 포스팅이미지 → 장소이미지
                    'combined_score': 0.0
                }

                # 1. 행동 벡터(클릭/북마크) → 장소 텍스트 (384차원)
                place_text_vector = place.get('text_vector')
                if place_text_vector is not None and user_behavior_vector is not None:
                    text_sim = safe_cosine_similarity(user_behavior_vector, place_text_vector)
                    scores['behavior_text_similarity'] = float(text_sim[0]) if len(text_sim) > 0 else 0.0

                # 2. 업로드 포스팅 이미지 → 장소 이미지 (512차원)
                place_image_vector = place.get('image_vector')
                if user_upload_vector is not None and place_image_vector is not None:
                    upload_sim = safe_cosine_similarity(user_upload_vector, place_image_vector)
                    scores['upload_image_similarity'] = float(upload_sim[0]) if len(upload_sim) > 0 else 0.0

                # 3. 북마크 장소 텍스트 → 장소 텍스트 (384차원)
                if bookmark_preferences.get('avg_text_vector') is not None and place_text_vector is not None:
                    bookmark_text_sim = safe_cosine_similarity(
                        bookmark_preferences['avg_text_vector'], place_text_vector
                    )
                    scores['bookmark_text_similarity'] = float(bookmark_text_sim[0]) if len(bookmark_text_sim) > 0 else 0.0

                # 4. 북마크 장소 이미지 → 장소 이미지 (512차원)
                if bookmark_preferences.get('avg_image_vector') is not None and place_image_vector is not None:
                    bookmark_image_sim = safe_cosine_similarity(
                        bookmark_preferences['avg_image_vector'], place_image_vector
                    )
                    scores['bookmark_image_similarity'] = float(bookmark_image_sim[0]) if len(bookmark_image_sim) > 0 else 0.0

                # 5. 좋아요한 포스팅 이미지 → 장소 이미지 (512차원)
                if liked_posts_vector is not None and place_image_vector is not None:
                    liked_sim = safe_cosine_similarity(liked_posts_vector, place_image_vector)
                    scores['liked_post_similarity'] = float(liked_sim[0]) if len(liked_sim) > 0 else 0.0

                # 6. 5개 독립적 채널들의 조합 점수 계산
                channel_scores = [
                    scores['behavior_text_similarity'] * 0.25,     # 행동기반 텍스트
                    scores['upload_image_similarity'] * 0.25,      # 업로드 포스팅 이미지
                    scores['bookmark_text_similarity'] * 0.2,      # 북마크 텍스트
                    scores['bookmark_image_similarity'] * 0.15,    # 북마크 이미지
                    scores['liked_post_similarity'] * 0.15         # 좋아요 포스팅 이미지
                ]

                # 유효한 채널들만 조합
                valid_scores = [score for score in channel_scores if score > 0]
                if valid_scores:
                    scores['combined_score'] = sum(valid_scores) / len(valid_scores)
                    # 다중 채널 보너스
                    if len(valid_scores) > 1:
                        scores['combined_score'] += 0.1 * (len(valid_scores) - 1)
                else:
                    scores['combined_score'] = 0.0

                results.append(scores)

            logger.info(f"🔄 Calculated independent channel similarities for {len(results)} places")
            return results

        except Exception as e:
            logger.error(f"❌ Independent similarity calculation failed: {e}")
            # 빈 점수 반환
            return [{
                'behavior_text_similarity': 0.0,
                'upload_image_similarity': 0.0,
                'bookmark_text_similarity': 0.0,
                'bookmark_image_similarity': 0.0,
                'liked_post_similarity': 0.0,
                'combined_score': 0.0
            } for _ in places]

    async def _get_detailed_bookmark_preferences(self, user_id: str) -> Dict[str, np.ndarray]:
        """북마크한 장소들의 상세 벡터 선호도 추출"""
        try:
            # 북마크한 장소들의 텍스트 및 이미지 벡터 조회
            query = """
                SELECT pr.vector as text_vector, pr.image_vector
                FROM saved_locations sl
                JOIN place_recommendations pr ON pr.place_id = CAST(SPLIT_PART(sl.places, ':', 2) AS INTEGER)
                    AND pr.table_name = SPLIT_PART(sl.places, ':', 1)
                WHERE sl.user_id = $1
                    AND (pr.vector IS NOT NULL OR pr.image_vector IS NOT NULL)
                LIMIT 30
            """

            bookmark_data = await self.db_manager.execute_query(query, user_id)

            text_vectors = []
            image_vectors = []

            for row in bookmark_data:
                # 텍스트 벡터 수집
                if row['text_vector']:
                    text_vector = validate_vector_data(row['text_vector'])
                    if text_vector is not None:
                        text_vectors.append(text_vector)

                # 이미지 벡터 수집
                if row['image_vector']:
                    image_vector = validate_vector_data(row['image_vector'])
                    if image_vector is not None:
                        image_vectors.append(image_vector)

            result = {}

            # 평균 텍스트 벡터 계산 (안전한 처리)
            if text_vectors and len(text_vectors) > 0:
                try:
                    result['avg_text_vector'] = np.mean(text_vectors, axis=0)
                except Exception as e:
                    logger.warning(f"Failed to calculate avg text vector: {e}")

            # 평균 이미지 벡터 계산 (안전한 처리)
            if image_vectors and len(image_vectors) > 0:
                try:
                    result['avg_image_vector'] = np.mean(image_vectors, axis=0)
                except Exception as e:
                    logger.warning(f"Failed to calculate avg image vector: {e}")

            logger.info(f"📚 User {user_id} bookmark preferences: {len(text_vectors)} text, {len(image_vectors)} image vectors")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to get detailed bookmark preferences for {user_id}: {e}")
            return {}


# ============================================================================
# 🚀 전역 엔진 인스턴스 (싱글톤 패턴)
# ============================================================================

_engine_instance: Optional[UnifiedRecommendationEngine] = None

async def get_engine() -> UnifiedRecommendationEngine:
    """전역 엔진 인스턴스 반환 (지연 초기화)"""
    global _engine_instance

    if _engine_instance is None:
        _engine_instance = UnifiedRecommendationEngine()
        await _engine_instance.initialize()

    return _engine_instance

async def close_engine():
    """전역 엔진 인스턴스 정리"""
    global _engine_instance

    if _engine_instance:
        await _engine_instance.close()
        _engine_instance = None


