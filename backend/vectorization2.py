# 파일명: vectorization2.py (완전 개선 버전)

import numpy as np
import asyncpg
import asyncio
import logging
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import time
import re
# Faiss 선택적 임포트 (Docker 환경 호환성)
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None
    print("⚠️ Faiss not available - ANN features will be disabled")

import pickle
import os
from threading import Lock

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

def safe_cosine_similarity(X: np.ndarray, Y: np.ndarray, use_ann: bool = False, faiss_manager=None) -> np.ndarray:
    """안전한 코사인 유사도 계산 (ANN 지원 버전)"""
    try:
        # ANN 사용 가능하고 요청된 경우 (안전하게 검사)
        if (use_ann and
            faiss_manager is not None and
            hasattr(faiss_manager, 'index') and
            faiss_manager.index is not None and
            hasattr(faiss_manager, 'search')):
            try:
                # Y의 길이 확인
                target_length = len(Y) if hasattr(Y, '__len__') else Y.shape[0] if hasattr(Y, 'shape') else 100
                search_k = min(target_length, 100)

                # ANN 검색 수행 (X는 쿼리 벡터)
                place_ids, scores = faiss_manager.search(X, k=search_k)

                # 결과를 기존 형태로 변환
                similarity_dict = {place_id: score for place_id, score in zip(place_ids, scores)}

                # Y의 길이에 맞춰 점수 배열 생성
                if len(scores) >= target_length:
                    return np.array(scores[:target_length])
                else:
                    # 부족한 경우 0.0으로 패딩
                    padded_scores = scores + [0.0] * (target_length - len(scores))
                    return np.array(padded_scores)

            except Exception as e:
                logger.warning(f"⚠️ ANN search failed, falling back to cosine similarity: {e}")

        # 기존 코사인 유사도 계산 (Fallback)
        # None 값 검증
        if X is None or Y is None:
            return np.array([0.0])

        # 입력을 numpy 배열로 변환 (메모리 효율적)
        X = np.asarray(X, dtype=np.float32)
        Y = np.asarray(Y, dtype=np.float32)

        # 빈 배열 검증
        if X.size == 0 or Y.size == 0:
            return np.array([0.0])

        # 차원 맞추기
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if Y.ndim == 1:
            Y = Y.reshape(1, -1)

        # 차원 일치 확인
        if X.shape[1] != Y.shape[1]:
            logger.warning(f"Vector dimension mismatch: X={X.shape[1]}, Y={Y.shape[1]}")
            return np.zeros(Y.shape[0])

        # 벡터화된 NaN/Inf 처리 (더 빠름)
        X = np.nan_to_num(X, nan=0.0, posinf=1.0, neginf=-1.0)
        Y = np.nan_to_num(Y, nan=0.0, posinf=1.0, neginf=-1.0)

        # L2 norm 계산 (axis=1에서 keepdims=True로 효율적)
        X_norm = np.linalg.norm(X, axis=1, keepdims=True)
        Y_norm = np.linalg.norm(Y, axis=1, keepdims=True)

        # 0 벡터 마스크 생성 (한 번에 처리)
        zero_mask_X = (X_norm == 0).flatten()
        zero_mask_Y = (Y_norm == 0).flatten()

        if np.any(zero_mask_X) or np.any(zero_mask_Y):
            return np.zeros(Y.shape[0])

        # 정규화 (in-place 연산으로 메모리 절약)
        X = X / X_norm
        Y = Y / Y_norm

        # 행렬 곱 (가장 효율적인 방법)
        similarities = np.einsum('ij,kj->ik', X, Y).flatten()

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


def safe_json_dumps(data: Any, **kwargs) -> str:
    """UTF-8 안전 JSON 직렬화"""
    try:
        # 기본 설정
        default_kwargs = {
            'ensure_ascii': False,
            'separators': (',', ':'),
            'default': str
        }
        default_kwargs.update(kwargs)

        # 데이터 정리 - 잘못된 문자 제거
        cleaned_data = _clean_json_data(data)

        return json.dumps(cleaned_data, **default_kwargs)
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        logger.warning(f"⚠️ UTF-8 encoding issue, falling back to ASCII: {e}")
        # ASCII 모드로 폴백
        return json.dumps(data, ensure_ascii=True, default=str, **kwargs)
    except Exception as e:
        logger.error(f"❌ JSON serialization failed: {e}")
        return "{}"


def _clean_json_data(data: Any) -> Any:
    """JSON 데이터에서 문제가 될 수 있는 문자들을 정리"""
    if isinstance(data, str):
        # 잘못된 UTF-8 문자나 surrogate 문자 제거
        try:
            # 유효하지 않은 UTF-8 문자 제거
            cleaned = data.encode('utf-8', errors='ignore').decode('utf-8')
            # 제어 문자 제거 (탭, 줄바꿈은 유지)
            cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
            return cleaned
        except Exception:
            return str(data)
    elif isinstance(data, dict):
        return {k: _clean_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_clean_json_data(item) for item in data]
    else:
        return data


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
# 🔍 ANN (Approximate Nearest Neighbor) 인덱스 관리 클래스
# ============================================================================

class FaissIndexManager:
    """Faiss 기반 ANN 인덱스 관리 클래스 (선택적 사용)"""

    def __init__(self, vector_dim: int = 768, index_type: str = "IVF"):
        self.vector_dim = vector_dim
        self.index_type = index_type
        self.index = None
        self.place_ids = []  # 인덱스의 벡터와 매핑되는 place_id 목록
        self.is_trained = False
        self.lock = Lock()
        self.index_file_path = "faiss_index.bin"
        self.metadata_file_path = "faiss_metadata.pkl"
        self.available = FAISS_AVAILABLE

    def _create_index(self, n_vectors: int) -> faiss.Index:
        """벡터 개수에 따른 최적 인덱스 생성"""
        if n_vectors < 1000:
            # 작은 데이터셋: Flat (정확)
            return faiss.IndexFlatIP(self.vector_dim)
        elif n_vectors < 10000:
            # 중간 데이터셋: IVF
            nlist = min(int(np.sqrt(n_vectors)), 100)
            quantizer = faiss.IndexFlatIP(self.vector_dim)
            return faiss.IndexIVFFlat(quantizer, self.vector_dim, nlist)
        else:
            # 대용량 데이터셋: IVF + PQ
            nlist = min(int(np.sqrt(n_vectors)), 1000)
            quantizer = faiss.IndexFlatIP(self.vector_dim)
            m = 64  # PQ segments
            return faiss.IndexIVFPQ(quantizer, self.vector_dim, nlist, m, 8)

    def build_index(self, vectors: np.ndarray, place_ids: List[int]):
        """벡터 데이터로 인덱스 구축"""
        if not self.available:
            logger.warning("⚠️ Faiss not available, skipping index build")
            return

        with self.lock:
            try:
                n_vectors = len(vectors)
                logger.info(f"🔨 Building Faiss index for {n_vectors} vectors")

                # 벡터 정규화 (내적 -> 코사인 유사도)
                faiss.normalize_L2(vectors)

                # 인덱스 생성
                self.index = self._create_index(n_vectors)
                self.place_ids = place_ids.copy()

                # 훈련 필요한 인덱스 처리
                if hasattr(self.index, 'train'):
                    logger.info("🎯 Training index...")
                    self.index.train(vectors)
                    self.is_trained = True

                # 벡터 추가
                self.index.add(vectors)
                logger.info(f"✅ Index built successfully: {self.index.ntotal} vectors")

                # 인덱스 저장
                self.save_index()

            except Exception as e:
                logger.error(f"❌ Failed to build index: {e}")
                raise

    def search(self, query_vector: np.ndarray, k: int = 50) -> tuple:
        """ANN 검색 수행"""
        if not self.available:
            return [], []

        with self.lock:
            if self.index is None:
                return [], []

            try:
                # 쿼리 벡터 정규화
                query_vector = query_vector.reshape(1, -1).astype(np.float32)
                faiss.normalize_L2(query_vector)

                # 검색 수행
                scores, indices = self.index.search(query_vector, k)

                # 결과 필터링 (유효한 인덱스만)
                valid_mask = indices[0] != -1
                valid_indices = indices[0][valid_mask]
                valid_scores = scores[0][valid_mask]

                # place_id 매핑
                place_ids = [self.place_ids[idx] for idx in valid_indices]

                return place_ids, valid_scores.tolist()

            except Exception as e:
                logger.error(f"❌ ANN search failed: {e}")
                return [], []

    def save_index(self):
        """인덱스를 파일에 저장"""
        try:
            if self.index is not None:
                faiss.write_index(self.index, self.index_file_path)

                # 메타데이터 저장
                metadata = {
                    'place_ids': self.place_ids,
                    'vector_dim': self.vector_dim,
                    'index_type': self.index_type,
                    'is_trained': self.is_trained
                }
                with open(self.metadata_file_path, 'wb') as f:
                    pickle.dump(metadata, f)

                logger.info("💾 Index saved to disk")
        except Exception as e:
            logger.error(f"❌ Failed to save index: {e}")

    def load_index(self) -> bool:
        """저장된 인덱스 로드"""
        if not self.available:
            return False

        try:
            if os.path.exists(self.index_file_path) and os.path.exists(self.metadata_file_path):
                # 인덱스 로드
                self.index = faiss.read_index(self.index_file_path)

                # 메타데이터 로드
                with open(self.metadata_file_path, 'rb') as f:
                    metadata = pickle.load(f)

                self.place_ids = metadata['place_ids']
                self.vector_dim = metadata['vector_dim']
                self.index_type = metadata['index_type']
                self.is_trained = metadata['is_trained']

                logger.info(f"📂 Index loaded: {self.index.ntotal} vectors")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to load index: {e}")

        return False

    def update_index(self, new_vectors: np.ndarray, new_place_ids: List[int]):
        """인덱스에 새 벡터 추가 (간단한 재구축 방식)"""
        with self.lock:
            try:
                # 기존 벡터 추출 (Faiss에서 직접 추출은 복잡하므로 재구축)
                all_place_ids = self.place_ids + new_place_ids

                # 새 벡터 정규화
                faiss.normalize_L2(new_vectors)

                # 기존 인덱스가 있다면 새 벡터만 추가
                if self.index is not None and hasattr(self.index, 'add'):
                    self.index.add(new_vectors)
                    self.place_ids.extend(new_place_ids)
                    logger.info(f"➕ Added {len(new_vectors)} vectors to index")
                else:
                    logger.warning("Index type doesn't support incremental updates. Consider rebuilding.")

            except Exception as e:
                logger.error(f"❌ Failed to update index: {e}")
                raise


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
                    'application_name': 'unified_recommendation_engine',
                    'tcp_keepalives_idle': '60',    # TCP keepalive 설정
                    'tcp_keepalives_interval': '30',
                    'tcp_keepalives_count': '3'
                },
                # 고급 최적화 설정
                setup=self._setup_connection if hasattr(CONFIG, 'pool_pre_ping') and CONFIG.pool_pre_ping else None
            )
            self._initialized = True
            logger.info(f"✅ Database pool initialized: {CONFIG.min_pool_size}-{CONFIG.max_pool_size} connections")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database pool: {e}")
            raise

    async def _setup_connection(self, connection):
        """연결 초기 설정 (성능 최적화)"""
        try:
            await connection.execute("SET work_mem = '64MB'")  # 작업 메모리 증가
            await connection.execute("SET random_page_cost = 1.1")  # SSD 최적화
            await connection.execute("SET effective_cache_size = '512MB'")  # 캐시 크기
        except Exception as e:
            logger.warning(f"Connection setup optimization failed: {e}")

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

        # ANN 인덱스 매니저 추가
        self.faiss_manager = FaissIndexManager(vector_dim=768)
        self.ann_enabled = False

        # 계층적 캐싱 시스템 (개선)
        self.vector_cache: Dict[str, Dict] = {}  # 기본 벡터 캐시
        self.cache_timestamps: Dict[str, float] = {}

        # 전용 캐시들 (메모리 효율적)
        self.user_data_cache: Dict[str, Dict] = {}  # 사용자 통합 데이터
        self.user_data_timestamps: Dict[str, float] = {}

        self.place_batch_cache: Dict[str, List[Dict]] = {}  # 장소 배치 데이터
        self.place_batch_timestamps: Dict[str, float] = {}

        self.similarity_cache: Dict[str, np.ndarray] = {}  # 유사도 결과
        self.similarity_timestamps: Dict[str, float] = {}

        # 성능 통계
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'personalized_requests': 0,
            'popular_requests': 0,
            'avg_response_time': 0.0,
            'ann_searches': 0,
            'cosine_searches': 0
        }

    def _convert_s3_urls_to_https(self, place: Dict) -> Dict:
        """이미지 URL을 파이썬 리스트로 변환 (DB의 다양한 형태 처리)"""
        if not place.get('image_urls'):
            return place

        try:
            image_urls = place['image_urls']

            # 1. JSON 배열 문자열 형태: ["url1", "url2"]
            if isinstance(image_urls, str) and image_urls.startswith('['):
                import json
                urls_list = json.loads(image_urls)
                place['image_urls'] = urls_list
                logger.info(f"🖼️ 이미지 URL 변환 완료 - 장소: {place.get('name')}, URLs: {len(urls_list)}개")

            # 2. PostgreSQL 배열 형태: {url1,url2,url3}
            elif isinstance(image_urls, str) and image_urls.startswith('{'):
                urls_str = image_urls.strip('{}')
                if urls_str:
                    urls = [url.strip().strip('"') for url in urls_str.split(',')]
                    https_urls = []
                    for url in urls:
                        if url.startswith('s3://'):
                            # S3 URL을 HTTPS로 변환
                            bucket = url.split('/')[2]
                            key = '/'.join(url.split('/')[3:])
                            https_url = f"https://{bucket}.s3.ap-northeast-2.amazonaws.com/{key}"
                            https_urls.append(https_url)
                        else:
                            https_urls.append(url)
                    place['image_urls'] = https_urls
                else:
                    place['image_urls'] = []

            # 3. 이미 리스트인 경우
            elif isinstance(image_urls, list):
                https_urls = []
                for url in image_urls:
                    if url and url.startswith('s3://'):
                        bucket = url.split('/')[2]
                        key = '/'.join(url.split('/')[3:])
                        https_url = f"https://{bucket}.s3.ap-northeast-2.amazonaws.com/{key}"
                        https_urls.append(https_url)
                    else:
                        https_urls.append(url)
                place['image_urls'] = https_urls

            # 4. 단일 문자열인 경우 (배열이 아닌)
            elif isinstance(image_urls, str) and (image_urls.startswith('http') or image_urls.startswith('s3://')):
                if image_urls.startswith('s3://'):
                    bucket = image_urls.split('/')[2]
                    key = '/'.join(image_urls.split('/')[3:])
                    https_url = f"https://{bucket}.s3.ap-northeast-2.amazonaws.com/{key}"
                    place['image_urls'] = [https_url]
                else:
                    place['image_urls'] = [image_urls]
            else:
                # 알 수 없는 형태
                logger.warning(f"Unknown image_urls format for place {place.get('place_id')}: {type(image_urls)} - {str(image_urls)[:100]}")
                place['image_urls'] = []

        except Exception as e:
            logger.error(f"이미지 URL 변환 실패 for place {place.get('place_id')}: {e}")
            place['image_urls'] = []

        return place

        logger.info("🚀 UnifiedRecommendationEngine v2.0 initialized")

    async def initialize(self):
        """엔진 초기화 (애플리케이션 시작 시 호출)"""
        await self.db_manager.initialize()

        # ANN 인덱스 로드 시도 (Faiss 가용성에 따라)
        if FAISS_AVAILABLE:
            try:
                if self.faiss_manager.load_index():
                    self.ann_enabled = True
                    logger.info("✅ ANN index loaded successfully")
                else:
                    logger.info("📝 ANN index not found. Will build when needed.")
            except Exception as e:
                logger.warning(f"⚠️ ANN index loading failed, disabling ANN: {e}")
                self.ann_enabled = False
        else:
            logger.info("⚠️ Faiss not available - ANN features disabled")
            self.ann_enabled = False

        logger.info("✅ Recommendation engine fully initialized")

    async def build_ann_index(self):
        """모든 장소 벡터로 ANN 인덱스 구축"""
        try:
            logger.info("🔨 Building ANN index from database...")

            # 모든 장소의 벡터 데이터 가져오기
            query = """
                SELECT id, embedding_vector
                FROM locations
                WHERE embedding_vector IS NOT NULL
                ORDER BY id
            """

            results = await self.db_manager.execute_query(query)

            if not results:
                logger.warning("❌ No vector data found for ANN index")
                return False

            # 벡터 데이터 준비
            vectors = []
            place_ids = []

            for row in results:
                vector = validate_vector_data(row['embedding_vector'])
                if vector is not None:
                    vectors.append(vector)
                    place_ids.append(row['id'])

            if len(vectors) == 0:
                logger.warning("❌ No valid vectors found for ANN index")
                return False

            # numpy 배열로 변환
            vectors_array = np.vstack(vectors).astype(np.float32)

            # 인덱스 구축
            self.faiss_manager.build_index(vectors_array, place_ids)
            self.ann_enabled = True

            logger.info(f"✅ ANN index built successfully with {len(vectors)} vectors")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to build ANN index: {e}")
            self.ann_enabled = False
            return False

    async def close(self):
        """리소스 정리"""
        await self.db_manager.close()
        self.vector_cache.clear()
        self.cache_timestamps.clear()

        # ANN 인덱스 저장
        if self.ann_enabled and self.faiss_manager.index is not None:
            self.faiss_manager.save_index()

        logger.info("🔌 Recommendation engine closed")

    def get_performance_stats(self) -> Dict:
        """성능 통계 반환"""
        total_searches = self.stats['ann_searches'] + self.stats['cosine_searches']
        ann_ratio = self.stats['ann_searches'] / total_searches if total_searches > 0 else 0

        return {
            **self.stats,
            'total_searches': total_searches,
            'ann_usage_ratio': ann_ratio,
            'ann_enabled': self.ann_enabled,
            'index_size': self.faiss_manager.index.ntotal if self.faiss_manager.index else 0
        }

    def _is_cache_valid(self, cache_key: str, cache_type: str = 'vector') -> bool:
        """계층적 캐시 유효성 검사"""
        timestamps = {
            'vector': self.cache_timestamps,
            'user_data': self.user_data_timestamps,
            'place_batch': self.place_batch_timestamps,
            'similarity': self.similarity_timestamps
        }

        if cache_key not in timestamps.get(cache_type, {}):
            return False

        age = time.time() - timestamps[cache_type][cache_key]
        return age < CONFIG.cache_ttl_seconds

    def _update_cache(self, cache_key: str, data: Any, cache_type: str = 'vector'):
        """계층적 캐시 업데이트 (LRU 전략)"""
        cache_configs = {
            'vector': (self.vector_cache, self.cache_timestamps, CONFIG.vector_cache_size),
            'user_data': (self.user_data_cache, self.user_data_timestamps, CONFIG.user_data_cache_size),
            'place_batch': (self.place_batch_cache, self.place_batch_timestamps, CONFIG.place_batch_cache_size),
            'similarity': (self.similarity_cache, self.similarity_timestamps, CONFIG.similarity_cache_size)
        }

        cache, timestamps, max_size = cache_configs.get(cache_type, cache_configs['vector'])

        # LRU 제거
        if len(cache) >= max_size:
            oldest_key = min(timestamps.keys(), key=lambda k: timestamps[k])
            del cache[oldest_key]
            del timestamps[oldest_key]

        cache[cache_key] = data
        timestamps[cache_key] = time.time()

    async def get_recommendations(
        self,
        user_id: Optional[str],
        region: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
        fast_mode: bool = False  # 메인 페이지용 고속 모드
    ) -> List[Dict]:
        """
        메인 추천 API (동적 가중치 시스템 적용)
        - 신규 가입자: 우선순위 선호도 태그 100%
        - 행동 데이터 있는 사용자: 우선순위 70%, 행동 데이터 30%
        """
        start_time = time.time()
        self.stats['total_requests'] += 1

        try:
            # 파라미터 검증
            limit = max(1, min(limit, 100))  # 1-100 사이로 제한

            if not user_id:
                # 비로그인 사용자: 인기 추천만
                logger.info("🌟 Popular recommendations for anonymous user")
                self.stats['popular_requests'] += 1
                return await self._get_popular_recommendations(region, category, limit, fast_mode)

            # 모든 로그인 사용자에게 지역별 선호도 추천 적용
            logger.info(f"🌍 Regional preference recommendations for user {user_id}")

            # 지역 지정 여부에 따라 분기
            if region:
                # 특정 지역 지정시: 우선순위 + 다양한 카테고리 통합 추천
                logger.info(f"🎯 Regional diverse recommendations for user {user_id} in {region}")
                result = await self._get_regional_diverse_recommendations(user_id, region, category, limit)
                if not result:
                    # 다양한 추천 실패시 기존 우선순위 기반으로 폴백
                    logger.info(f"📊 Fallback to priority-based recommendations for user {user_id}")
                    result = await self._get_preference_based_recommendations(user_id, region, category, limit)
                    if not result:
                        # 선호도 데이터가 없으면 인기 추천으로 폴백
                        logger.info(f"📊 Fallback to popular recommendations for user {user_id}")
                        result = await self._get_popular_recommendations(region, category, limit, fast_mode)
            else:
                # 지역 지정 없을 때: 사용자 맞춤 추천 (전체 지역 대상)
                logger.info(f"👤 User personalized recommendations for user {user_id}")
                result = await self._get_user_personalized_recommendations(user_id, limit)
                if not result:
                    # 선호도 데이터가 없으면 인기 추천으로 폴백
                    logger.info(f"📊 Fallback to popular recommendations for user {user_id}")
                    result = await self._get_popular_recommendations(region, category, limit, fast_mode)

            # 응답 시간 업데이트
            response_time = time.time() - start_time
            self._update_response_time(response_time)

            logger.info(f"✅ Returned {len(result)} recommendations in {response_time:.3f}s")
            return result

        except Exception as e:
            logger.error(f"❌ Recommendation failed: {e}")
            # 빈 결과라도 안전하게 반환
            return []

    async def _get_comprehensive_user_data_cached(self, user_id: str) -> Dict[str, Any]:
        """캐시된 사용자 통합 데이터 조회 (DB 호출 최소화)"""
        cache_key = f"user_comprehensive:{user_id}"

        # 캐시 확인
        if self._is_cache_valid(cache_key, 'user_data'):
            self.stats['cache_hits'] += 1
            return self.user_data_cache[cache_key]

        # 캐시 미스 시 DB에서 조회
        comprehensive_data = await self._get_comprehensive_user_data(user_id)
        self._update_cache(cache_key, comprehensive_data, 'user_data')
        return comprehensive_data

    async def _get_comprehensive_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        통합 사용자 데이터 조회 (DB 호출 최소화)
        - 행동 점수
        - 선호도 정보
        - 북마크 데이터
        - 벡터 데이터
        모든 것을 한 번에 조회
        """
        try:
            # 단일 트랜잭션으로 모든 사용자 데이터 조회
            async with self.db_manager.get_connection() as conn:
                # 1. 행동 점수 조회 (user_behavior_vectors 테이블 구조에 맞춤)
                behavior_query = """
                    SELECT COALESCE(
                        total_bookmarks + total_likes + total_clicks, 0
                    ) as behavior_score
                    FROM user_behavior_vectors
                    WHERE user_id = $1
                """

                # 2. 사용자 선호도 조회 (user_preferences 테이블에서)
                preferences_query = """
                    SELECT priority, accommodation, exploration, persona
                    FROM user_preferences
                    WHERE user_id = $1
                """

                # 3. 선호도 태그 조회
                tags_query = """
                    SELECT tag, weight
                    FROM user_preference_tags
                    WHERE user_id = $1
                    ORDER BY weight DESC
                """

                # 4. 행동 벡터 조회
                vector_query = """
                    SELECT behavior_vector
                    FROM user_behavior_vectors
                    WHERE user_id = $1 AND behavior_vector IS NOT NULL
                """

                # 5. 북마크 데이터 조회
                bookmarks_query = """
                    SELECT places
                    FROM saved_locations
                    WHERE user_id = $1
                """

                # 순차 쿼리 실행 (안전한 방식)
                try:
                    behavior_score = await conn.fetchval(behavior_query, user_id) or 0
                except Exception as e:
                    logger.error(f"Behavior query failed: {e}")
                    behavior_score = 0

                try:
                    preferences_data = await conn.fetchrow(preferences_query, user_id)
                except Exception as e:
                    logger.error(f"Preferences query failed: {e}")
                    preferences_data = None

                try:
                    tags_data = await conn.fetch(tags_query, user_id)
                except Exception as e:
                    logger.error(f"Tags query failed: {e}")
                    tags_data = []

                try:
                    vector_data = await conn.fetchval(vector_query, user_id)
                except Exception as e:
                    logger.error(f"Vector query failed: {e}")
                    vector_data = None

                try:
                    bookmarks_data = await conn.fetch(bookmarks_query, user_id)
                except Exception as e:
                    logger.error(f"Bookmarks query failed: {e}")
                    bookmarks_data = []

                # 결과 통합
                result = {
                    'behavior_score': behavior_score,
                    'user_preferences': {
                        'priority': preferences_data['priority'] if preferences_data else None,
                        'accommodation': preferences_data['accommodation'] if preferences_data else None,
                        'exploration': preferences_data['exploration'] if preferences_data else None,
                        'persona': preferences_data['persona'] if preferences_data else None
                    },
                    'preference_tags': {
                        row['tag']: row['weight'] for row in tags_data
                    },
                    'behavior_vector': validate_vector_data(vector_data),
                    'bookmarks': [dict(row) for row in bookmarks_data]
                }

                return result

        except Exception as e:
            logger.error(f"❌ Failed to get comprehensive user data for {user_id}: {e}")
            return {
                'behavior_score': 0,
                'preferences': {'preference_tags': {}},
                'behavior_vector': None,
                'bookmarks': []
            }

    async def _get_user_behavior_score(self, user_id: str) -> int:
        """사용자 행동 점수 (캐시된 데이터 활용)"""
        cache_key = f"user_comprehensive:{user_id}"
        if self._is_cache_valid(cache_key):
            cached_data = self.vector_cache.get(cache_key)
            return cached_data.get('behavior_score', 0)

        # 캐시가 없으면 통합 데이터 조회
        comprehensive_data = await self._get_comprehensive_user_data(user_id)
        self._update_cache(cache_key, comprehensive_data)
        return comprehensive_data.get('behavior_score', 0)

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
            logger.info(f"🔍 [Vector] User {user_id} raw vector data from DB: {vector_data is not None}")
            if vector_data is not None:
                logger.info(f"🔍 [Vector] User {user_id} vector type: {type(vector_data)}, length: {len(vector_data) if hasattr(vector_data, '__len__') else 'N/A'}")

            validated_vector = validate_vector_data(vector_data)
            logger.info(f"🔍 [Vector] User {user_id} validated vector: {validated_vector is not None}")

            if validated_vector is not None:
                logger.info(f"🔍 [Vector] User {user_id} validated vector shape: {validated_vector.shape}, non-zero: {np.count_nonzero(validated_vector)}")

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

                # 초강력 선호도 편향 시스템 (더 공격적 할당)
                if preference_rate > 0.6:  # 60% 이상 강한 선호 (기준 낮춤)
                    quota = min(max(int(limit * 0.5), 4), max_per_category + 3)  # 50% 또는 기본+3 (더 공격적)
                elif preference_rate > 0.3:  # 30% 이상 선호 카테고리 (기준 낮춤)
                    quota = min(max(int(limit * 0.35), 3), max_per_category + 2)  # 35% 또는 기본+2
                elif preference_rate > 0.1:  # 10% 이상 선호 카테고리 (기준 낮춤)
                    quota = min(max(int(limit * 0.2), 2), max_per_category + 1)  # 20% 또는 기본+1
                else:  # 낮은 선호도 카테고리
                    quota = max(1, int(limit * 0.05))  # 최소 5% 할당

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
                    # S3 이미지 URL을 HTTPS로 변환
                    place = self._convert_s3_urls_to_https(place)
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
        limit: int,
        fast_mode: bool = False
    ) -> List[Dict]:
        """인기 기반 추천 (단순 북마크 카운트 정렬)"""
        # fast_mode에 따라 다른 후보 조회
        if fast_mode:
            places = await self._get_fast_place_candidates(region, category, limit * 2)
        else:
            places = await self._get_place_candidates(region, category)

        if not places:
            return []

        # 단순 북마크 카운트 기반 정렬
        for place in places:
            try:
                bookmark_count = place.get('bookmark_cnt', 0)
                place['final_score'] = bookmark_count
                place['recommendation_type'] = 'popular_fast' if fast_mode else 'popular'
                place['source'] = 'popular'  # 소스 태그 추가
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
        다중 벡터 기반 추천 시스템 (동적 가중치 적용)
        - 기존 사용자: 우선순위 선호도 70% + 행동 데이터 30%
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

            # 병렬 처리로 성능 최적화: 사용자 데이터를 동시에 조회
            user_data_tasks = [
                self._get_user_preferences(user_id),
                self._get_user_image_preferences(user_id)
            ]

            # 비동기 병렬 실행
            user_preferences, user_image_preferences = await asyncio.gather(
                *user_data_tasks, return_exceptions=True
            )

            # 예외 처리
            if isinstance(user_preferences, Exception):
                user_preferences = {}
                logger.error(f"Failed to get user preferences: {user_preferences}")

            if isinstance(user_image_preferences, Exception):
                user_image_preferences = {}
                logger.error(f"Failed to get user image preferences: {user_image_preferences}")

            # 이미지 선호도가 준비되면 다중 벡터 유사도 재계산
            multi_scores = await self._calculate_independent_similarities(
                user_id, user_vector, user_image_preferences, places
            )

            # 배치 처리를 위한 인기도 점수 미리 계산
            popularity_scores = {}
            engagement_scores = {}
            for place in places:
                place_data = {
                    'total_clicks': place.get('total_clicks', 0),
                    'total_likes': place.get('total_likes', 0),
                    'total_bookmarks': place.get('total_bookmarks', 0)
                }
                place_id = place.get('place_id')
                popularity_scores[place_id] = calculate_weighted_popularity_score(place_data)
                engagement_scores[place_id] = calculate_engagement_score(place_data)

            # 배치 선호도 점수 계산
            preference_scores = {}
            for place in places:
                place_id = place.get('place_id')
                preference_scores[place_id] = self._calculate_place_preference_score(place, user_preferences)

            # 하이브리드 점수 계산 및 결과 생성
            results = []
            for i, place in enumerate(places):
                place_id = place.get('place_id')

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
                    # 미리 계산된 점수들 사용
                    popularity_score = popularity_scores.get(place_id, 0.0)
                    engagement_score = engagement_scores.get(place_id, 0.0)
                    preference_score = preference_scores.get(place_id, 0.0)

                    # 북마크 선호도 보너스
                    category_preference = bookmark_preferences.get(place['table_name'], 0)
                    bookmark_bonus = category_preference * 0.5

                    # 다중 벡터 종합 점수 (행동 데이터 기반)
                    behavior_score = scores.get('combined_score', 0.0)

                    # 동적 가중치 적용 (기존 사용자: 선호도 70% + 행동 데이터 30%)
                    weighted_preference_score = preference_score * CONFIG.experienced_user_preference_weight
                    weighted_behavior_score = behavior_score * CONFIG.experienced_user_behavior_weight

                    # 최종 하이브리드 점수 (동적 가중치 반영)
                    final_score = (
                        weighted_preference_score +
                        weighted_behavior_score +
                        (popularity_score / 100.0) * 0.1 +  # 인기도 약간 반영
                        bookmark_bonus * 0.1  # 북마크 보너스 약간 반영
                    )

                    # 점수가 임계값 이상인 경우만 포함
                    if behavior_score >= CONFIG.min_similarity_threshold:
                        place['behavior_text_similarity'] = round(scores.get('behavior_text_similarity', 0.0), 4)
                        place['upload_image_similarity'] = round(scores.get('upload_image_similarity', 0.0), 4)
                        place['bookmark_text_similarity'] = round(scores.get('bookmark_text_similarity', 0.0), 4)
                        place['bookmark_image_similarity'] = round(scores.get('bookmark_image_similarity', 0.0), 4)
                        place['liked_post_similarity'] = round(scores.get('liked_post_similarity', 0.0), 4)
                        place['combined_score'] = round(scores.get('combined_score', 0.0), 4)
                        place['multi_vector_score'] = round(behavior_score, 4)
                        place['preference_score'] = round(preference_score, 4)
                        place['weighted_preference_score'] = round(weighted_preference_score, 4)
                        place['weighted_behavior_score'] = round(weighted_behavior_score, 4)
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
            similarities = safe_cosine_similarity(
                user_vector,
                place_vectors_array,
                use_ann=self.ann_enabled,
                faiss_manager=self.faiss_manager
            )

            # 통계 업데이트
            if self.ann_enabled:
                self.stats['ann_searches'] += 1
            else:
                self.stats['cosine_searches'] += 1

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
            similarities = safe_cosine_similarity(
                user_vector,
                place_vectors_array,
                use_ann=self.ann_enabled,
                faiss_manager=self.faiss_manager
            )

            # 통계 업데이트
            if self.ann_enabled:
                self.stats['ann_searches'] += 1
            else:
                self.stats['cosine_searches'] += 1

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
        우선순위 태그 기반 추천 (behavior_vector 통합)
        user_preferences, user_preference_tags 테이블과 user_behavior_vectors의 behavior_vector를 활용
        """
        try:
            # 1. 사용자 선호도 정보 조회
            logger.info(f"🔍 Getting user preferences for user {user_id}")
            user_preferences = await self._get_user_preferences(user_id)
            if not user_preferences:
                logger.info(f"❌ No preferences found for user {user_id}")
                return []

            logger.info(f"✅ Found user preferences for user {user_id}: {list(user_preferences.keys())}")

            # 2. 사용자 행동 벡터 조회 (북마크 패턴 분석용)
            logger.info(f"🧠 Getting user behavior vector for user {user_id}")
            user_behavior_vector = await self._get_user_behavior_vector_cached(user_id)
            if user_behavior_vector is not None:
                logger.info(f"✅ Found behavior vector for user {user_id}: shape {user_behavior_vector.shape}")
            else:
                logger.info(f"❌ No behavior vector found for user {user_id}")

            # 3. 우선순위 태그 내에서 behavior_vector 통합된 점수 계산
            recommendations = await self._calculate_priority_enhanced_scores(
                user_preferences, user_behavior_vector, region, category, limit
            )

            logger.info(f"✅ Generated {len(recommendations)} priority-enhanced recommendations for user {user_id}")
            return recommendations

        except Exception as e:
            logger.error(f"❌ Priority-enhanced recommendation failed for user {user_id}: {e}")
            return []

    async def _get_regional_diverse_recommendations(
        self,
        user_id: str,
        region: str,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        특정 지역 내에서 우선순위 + 다양한 카테고리 통합 추천
        - 우선순위 태그: 50%
        - 다양한 카테고리: 30%
        - 유사한 장소: 20%
        """
        try:
            # 1. 사용자 선호도 및 행동 벡터 조회
            logger.info(f"🔍 [Regional Diverse] Getting user data for {user_id} in {region}")
            user_preferences = await self._get_user_preferences(user_id)
            if not user_preferences:
                logger.info(f"❌ [Regional Diverse] No preferences found for user {user_id}")
                return []

            user_behavior_vector = await self._get_user_behavior_vector_cached(user_id)
            logger.info(f"🧠 [Regional Diverse] Behavior vector: {'Found' if user_behavior_vector is not None else 'Not found'}")

            # 2. 특정 지역 추천: 다양한 소스 조합 (사용자별 추천과 구별)
            recommendations = []

            if user_behavior_vector is not None:
                logger.info(f"🧠 [Regional Diverse] Mixed recommendations for region {region} (behavior + priority)")

                # 행동 벡터 기반 + 우선순위 기반 조합 (50:50)
                behavior_limit = max(1, int(limit * 0.5))
                priority_limit = limit - behavior_limit

                # 행동 벡터 기반 추천 (50%)
                behavior_recommendations = await self._get_similar_places_in_region(
                    user_behavior_vector, region, behavior_limit
                )

                # 우선순위 기반 추천 (50%)
                priority_recommendations = await self._calculate_preference_scores(
                    user_preferences, region, category, priority_limit
                )

                # 두 추천 결과 병합
                recommendations.extend(behavior_recommendations)
                recommendations.extend(priority_recommendations)

                # 중복 제거
                seen_places = set()
                unique_recommendations = []
                for rec in recommendations:
                    place_id = rec.get('place_id')
                    if place_id not in seen_places:
                        seen_places.add(place_id)
                        unique_recommendations.append(rec)

                recommendations = unique_recommendations[:limit]
                logger.info(f"✅ [Regional Diverse] Mixed completed: {len(recommendations)} items (behavior+priority)")
                return recommendations
            else:
                logger.info(f"❌ [Regional Diverse] No behavior vector, using priority-based only")
                # 행동 벡터가 없으면 선호도 기반으로만
                recommendations = await self._calculate_preference_scores(
                    user_preferences, region, category, limit
                )
                return recommendations

            # 3. 카테고리 필터가 없는 경우 다양한 소스 조합
            recommendations = []

            # 우선순위 카테고리 추천 (80% - 더 많이 가져오기)
            priority_limit = max(10, int(limit * 0.8))  # 최소 10개, 80%로 증가
            logger.info(f"🎯 [Regional Diverse] Getting {priority_limit} priority recommendations")
            priority_recommendations = await self._calculate_priority_enhanced_scores(
                user_preferences, user_behavior_vector, region, None, priority_limit
            )

            # 다양한 카테고리 추천 (15%)
            diverse_limit = max(3, int(limit * 0.15))  # 최소 3개, 15%로 감소
            logger.info(f"🌈 [Regional Diverse] Getting {diverse_limit} diverse category recommendations")
            user_priority = user_preferences.get('priority')
            diverse_recommendations = await self._get_diverse_category_recommendations(
                user_behavior_vector, region, diverse_limit, exclude_priority=user_priority
            )

            # 유사한 장소 추천 (5%)
            similar_limit = max(1, limit - priority_limit - diverse_limit)
            logger.info(f"🔍 [Regional Diverse] Getting {similar_limit} similar place recommendations")
            similar_recommendations = []
            if user_behavior_vector is not None:
                similar_recommendations = await self._get_similar_places_in_region(
                    user_behavior_vector, region, similar_limit
                )

            # 4. 추천 병합 (중복 제거)
            final_recommendations = self._merge_diverse_recommendations(
                priority_recommendations, diverse_recommendations, similar_recommendations, limit
            )

            # 5. 소스 태그 추가
            for rec in final_recommendations:
                if 'source' not in rec:
                    rec['source'] = 'diverse_regional'

            logger.info(f"🎉 [Regional Diverse] Generated {len(final_recommendations)} diverse recommendations "
                       f"(priority: {len(priority_recommendations)}, diverse: {len(diverse_recommendations)}, "
                       f"similar: {len(similar_recommendations)})")

            return final_recommendations

        except Exception as e:
            logger.error(f"❌ Regional diverse recommendation failed for user {user_id}: {e}")
            return []

    async def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 정보 조회 (user_preferences 테이블에서 조회)"""
        try:
            # user_preferences 테이블에서 선호도 정보 조회 (올바른 스키마)
            preferences_query = """
                SELECT
                    priority,
                    accommodation,
                    exploration,
                    persona
                FROM user_preferences
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
                'user_id': user_id,  # user_id 추가
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

    async def _calculate_priority_enhanced_scores(
        self,
        user_preferences: Dict[str, Any],
        user_behavior_vector: Optional[np.ndarray],
        region: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        🎯 우선순위 태그 내에서 behavior_vector를 활용한 향상된 점수 계산
        1. 우선순위 태그로 카테고리 필터링
        2. 해당 카테고리 내에서 behavior_vector로 개인화
        3. 선호도 태그와 행동 패턴을 종합한 점수 산출
        """
        try:
            priority = user_preferences.get('priority')

            # 체험 우선순위는 특별 처리 필요
            if priority == 'experience':
                logger.info(f"🎯 Experience priority: collecting from nature, humanities, leisure_sports")

                # 체험 우선순위는 3개 카테고리에서 모두 수집
                experience_categories = ['nature', 'humanities', 'leisure_sports']
                all_places_data = []

                async with self.db_manager.get_connection() as conn:
                    for exp_category in experience_categories:
                        places_query = """
                            SELECT
                                place_id, table_name, region, name,
                                latitude, longitude, overview, image_urls, bookmark_cnt,
                                vector as text_vector,
                                COALESCE(bookmark_cnt, 0) as popularity_score
                            FROM place_recommendations
                            WHERE name IS NOT NULL
                                AND ($1::text IS NULL OR region = $1)
                                AND table_name = $2
                            ORDER BY bookmark_cnt DESC
                            LIMIT $3
                        """

                        category_places = await conn.fetch(
                            places_query,
                            region,
                            exp_category,
                            CONFIG.candidate_limit // 3  # 각 카테고리에서 1/3씩
                        )
                        all_places_data.extend(category_places)
                        logger.info(f"🎯 Found {len(category_places)} places for experience->{exp_category}")

                places_data = all_places_data
            else:
                # 다른 우선순위는 기존 방식
                target_category = category if category else priority
                logger.info(f"🎯 Priority filtering: {priority} → target_category: {target_category}")

                places_query = """
                    SELECT
                        place_id, table_name, region, name,
                        latitude, longitude, overview, image_urls, bookmark_cnt,
                        vector as text_vector,
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
                        target_category,
                        CONFIG.candidate_limit
                    )

            if not places_data:
                if priority == 'experience':
                    logger.warning(f"No places found for experience priority in region: {region}")
                else:
                    logger.warning(f"No places found for priority: {priority}, region: {region}, category: {target_category}")
                return []

            # 우선순위 태그 내에서 behavior_vector 기반 점수 계산
            scored_places = []
            popularity_normalizer = CONFIG.preference_weights['popularity_normalizer']

            for place in places_data:
                # 1. 기본 선호도 점수 (우선순위 태그 매칭)
                preference_score = self._calculate_place_preference_score(place, user_preferences)

                # 2. behavior_vector 기반 개인화 점수 (우선순위 카테고리 내에서)
                behavior_score = 0.0
                if user_behavior_vector is not None and place.get('text_vector'):
                    place_text_vector = validate_vector_data(place['text_vector'])
                    if place_text_vector is not None:
                        similarity = safe_cosine_similarity(user_behavior_vector, place_text_vector, use_ann=False)
                        behavior_score = float(similarity[0]) if len(similarity) > 0 else 0.0
                        logger.info(f"🧠 {place['name']}: behavior_score={behavior_score:.4f}")
                    else:
                        logger.info(f"⚠️ {place['name']}: invalid text_vector")
                else:
                    if user_behavior_vector is None:
                        logger.info(f"❌ {place['name']}: no behavior_vector for user")
                    else:
                        logger.info(f"❌ {place['name']}: no text_vector for place")

                # 3. 우선순위 태그 내 종합 점수 계산
                if preference_score > 0 or behavior_score > 0:
                    place_dict = dict(place)
                    popularity_normalized = min(place['popularity_score'] / popularity_normalizer, 1.0)

                    # 🎯 행동 데이터 유무에 따른 가중치 차별화
                    if user_behavior_vector is not None:
                        # 행동 데이터 있는 사용자: 개인화 중심 (인기도 제외)
                        priority_weight = 0.7   # 우선순위 태그 기반 선호도
                        behavior_weight = 0.3   # 북마크 행동 패턴 (강화)
                        popularity_weight = 0.0 # 인기도 제외
                    else:
                        # 행동 데이터 없는 사용자: 인기도 참고
                        priority_weight = 0.8   # 우선순위 태그 기반 선호도 (강화)
                        behavior_weight = 0.0   # 행동 패턴 없음
                        popularity_weight = 0.2 # 인기도 참고

                    final_score = (
                        preference_score * priority_weight +
                        behavior_score * behavior_weight +
                        popularity_normalized * popularity_weight
                    )

                    # 상세 점수 로깅 (behavior_score 높은 장소만)
                    if behavior_score > 0.1:
                        logger.info(f"🎯 HIGH BEHAVIOR: {place['name']}: pref={preference_score:.3f}, behav={behavior_score:.4f}, pop={popularity_normalized:.3f} → final={final_score:.4f}")

                    place_dict['preference_score'] = preference_score
                    place_dict['behavior_score'] = behavior_score
                    place_dict['final_score'] = final_score
                    place_dict['source'] = 'priority_enhanced'
                    scored_places.append(place_dict)

            # 점수 기준 정렬
            logger.info(f"🔄 [Priority] Sorting {len(scored_places)} scored places...")
            scored_places.sort(key=lambda x: x['final_score'], reverse=True)
            logger.info(f"✅ [Priority] Sorting completed")

            # numpy 배열을 리스트로 변환 (JSON 직렬화를 위해)
            logger.info(f"🔄 [Priority] Converting numpy arrays for {len(scored_places[:limit])} places...")
            result_places = scored_places[:limit]
            for i, place in enumerate(result_places):
                logger.info(f"🔄 [Priority] Processing place {i+1}/{len(result_places)}: {place.get('name', 'Unknown')}")
                if 'text_vector' in place and isinstance(place['text_vector'], np.ndarray):
                    place['text_vector'] = place['text_vector'].tolist()
                if 'image_vector' in place and isinstance(place['image_vector'], np.ndarray):
                    place['image_vector'] = place['image_vector'].tolist()
            logger.info(f"✅ [Priority] Numpy conversion completed")

            behavior_used = user_behavior_vector is not None
            logger.info(f"🚀 Priority-enhanced scoring completed: {len(scored_places)} total, {len(result_places)} results, behavior_vector: {'✅' if behavior_used else '❌'}")

            return result_places

        except Exception as e:
            logger.error(f"❌ Failed to calculate priority-enhanced scores: {e}")
            return []

    async def get_user_priority_tag(self, user_id: str) -> Optional[str]:
        """사용자의 여행 우선순위 태그 조회"""
        try:
            async with self.db_manager.get_connection() as conn:
                query = """
                    SELECT priority
                    FROM user_preferences
                    WHERE user_id = $1
                """
                result = await conn.fetchval(query, user_id)
                return result
        except Exception as e:
            logger.error(f"❌ Failed to get user priority tag for {user_id}: {e}")
            return None

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

            # 우선순위 기반 점수 (카테고리 우선순위 지원)
            priority = user_preferences.get('priority')
            if priority:
                # 카테고리 우선순위 처리 (초강력 편향)
                if priority == place['table_name']:
                    score += 10.0  # 카테고리 정확히 일치 시 매우 강력한 보너스
                    logger.info(f"🎯 CATEGORY MATCH BOOST: {place.get('name', 'Unknown')} gets +10.0 for matching {priority} priority")

                # 카테고리 매핑을 통한 추가 매칭
                priority_category_map = {
                    'accommodation': ['accommodation'],
                    'restaurants': ['restaurants'],
                    'shopping': ['shopping'],
                    'nature': ['nature'],
                    'culture': ['humanities'],
                    'leisure': ['leisure_sports']
                }

                if priority in priority_category_map:
                    if place['table_name'] in priority_category_map[priority]:
                        score += 10.0  # 매핑된 카테고리 일치 시에도 강력한 보너스
                        logger.info(f"🎯 MAPPED CATEGORY BOOST: {place.get('name', 'Unknown')} gets +10.0 for {priority} -> {place['table_name']} mapping")

                # 기존 popular/unique 처리 (기본 보너스)
                if priority == 'popular' and place.get('bookmark_cnt', 0) > 1000:
                    score += 0.5
                elif priority == 'unique' and place.get('bookmark_cnt', 0) < 500:
                    score += 0.5

            # 초강력 태그 매칭 시스템 (공격적 편향)
            preference_tags = user_preferences.get('preference_tags', {})
            if preference_tags:
                place_description = (place.get('description', '') or '').lower()
                place_name = (place.get('name', '') or '').lower()
                combined_text = place_description + ' ' + place_name

                tag_score, tag_count, max_weight = 0.0, 0, 0

                for tag_name, tag_weight in preference_tags.items():
                    tag_lower = tag_name.lower()

                    # 다양한 매칭 전략 (더 공격적)
                    match_found = False
                    match_strength = 0.0

                    # 1. 완전 일치 (100% 매칭)
                    if tag_lower in combined_text:
                        match_strength = 1.0
                        match_found = True

                    # 2. 부분 매칭 (어근 매칭 70%)
                    elif any(word in combined_text for word in tag_lower.split()):
                        match_strength = 0.7
                        match_found = True

                    # 3. 유사 단어 매칭 (바이어스 60%)
                    else:
                        # 기본 유사 연결 사전
                        similar_words = {
                            '자연': ['산', '바다', '호수', '공원', '숲', '하이킹', '트레킹'],
                            '문화': ['박물관', '미술관', '절', '궁궐', '전통', '역사', '화가'],
                            '맛집': ['음식', '레스토랑', '카페', '밥집', '한식', '양식'],
                            '쇼핑': ['마트', '백화점', '아울렛', '시장', '상가'],
                            '체험': ['액티비티', '레저', '놀이', '축제', '공연']
                        }

                        for similar_key, similar_list in similar_words.items():
                            if tag_lower == similar_key and any(word in combined_text for word in similar_list):
                                match_strength = 0.6
                                match_found = True
                                break

                    if match_found:
                        # 가중치 반영: 1-10 스케일을 더 공격적으로 활용
                        raw_weight = tag_weight / 10.0  # 0.1 ~ 1.0

                        # 초강력 가중치 시스템
                        if tag_weight >= 8:  # 최고 우선순위 (80% 이상)
                            boosted_weight = raw_weight * 3.0 * match_strength  # 3배 부스트
                        elif tag_weight >= 6:  # 높은 우선순위 (60% 이상)
                            boosted_weight = raw_weight * 2.5 * match_strength  # 2.5배 부스트
                        elif tag_weight >= 4:  # 중간 우선순위 (40% 이상)
                            boosted_weight = raw_weight * 2.0 * match_strength  # 2배 부스트
                        else:
                            boosted_weight = raw_weight * match_strength  # 기본 가중치

                        tag_score += boosted_weight
                        tag_count += 1
                        max_weight = max(max_weight, boosted_weight)

                if tag_count > 0:
                    # 초강력 태그 점수 적용
                    # 1. 기본 점수: 평균 대신 최대값 사용 (더 공격적)
                    primary_score = min(max_weight, 2.0)  # 최대 2.0점

                    # 2. 다중 매칭 보너스 (여러 태그 매칭 시 추가 점수)
                    multi_match_bonus = min((tag_count - 1) * 0.3, 1.0)  # 최대 1.0점 보너스

                    # 3. 최종 태그 점수
                    final_tag_score = (primary_score + multi_match_bonus) * weights['tag']

                    # 4. 추가 부스트 (CONFIG에서 설정한 매개변수)
                    if 'tag_boost_multiplier' in weights:
                        final_tag_score *= weights['tag_boost_multiplier']

                    score += final_tag_score

                    # 디버깅 로그
                    logger.debug(f"태그 매칭 - 장소: {place.get('name')}, 매칭수: {tag_count}, 최대가중치: {max_weight:.3f}, 최종점수: {final_tag_score:.3f}")

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

                    # S3 이미지 URL을 HTTPS로 변환
                    place = self._convert_s3_urls_to_https(place)
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
                    text_sim = safe_cosine_similarity(user_behavior_vector, place_text_vector, use_ann=False)
                    scores['behavior_text_similarity'] = float(text_sim[0]) if len(text_sim) > 0 else 0.0

                # 2. 업로드 포스팅 이미지 → 장소 이미지 (512차원)
                place_image_vector = place.get('image_vector')
                if user_upload_vector is not None and place_image_vector is not None:
                    upload_sim = safe_cosine_similarity(user_upload_vector, place_image_vector, use_ann=False)
                    scores['upload_image_similarity'] = float(upload_sim[0]) if len(upload_sim) > 0 else 0.0

                # 3. 북마크 장소 텍스트 → 장소 텍스트 (384차원)
                if bookmark_preferences.get('avg_text_vector') is not None and place_text_vector is not None:
                    bookmark_text_sim = safe_cosine_similarity(
                        bookmark_preferences['avg_text_vector'], place_text_vector, use_ann=False
                    )
                    scores['bookmark_text_similarity'] = float(bookmark_text_sim[0]) if len(bookmark_text_sim) > 0 else 0.0

                # 4. 북마크 장소 이미지 → 장소 이미지 (512차원)
                if bookmark_preferences.get('avg_image_vector') is not None and place_image_vector is not None:
                    bookmark_image_sim = safe_cosine_similarity(
                        bookmark_preferences['avg_image_vector'], place_image_vector, use_ann=False
                    )
                    scores['bookmark_image_similarity'] = float(bookmark_image_sim[0]) if len(bookmark_image_sim) > 0 else 0.0

                # 5. 좋아요한 포스팅 이미지 → 장소 이미지 (512차원)
                if liked_posts_vector is not None and place_image_vector is not None:
                    liked_sim = safe_cosine_similarity(liked_posts_vector, place_image_vector, use_ann=False)
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

    async def _get_fast_place_candidates(
        self,
        region: Optional[str],
        category: Optional[str],
        limit: int = 50
    ) -> List[Dict]:
        """메인 페이지용 고속 장소 후보 조회 (최소 컬럼만)"""
        try:
            # 캐시 키 생성
            cache_key = f"fast_places:{region or 'all'}:{category or 'all'}:{limit}"

            # 캐시 확인
            if self._is_cache_valid(cache_key, 'place_batch'):
                self.stats['cache_hits'] += 1
                return self.place_batch_cache[cache_key]

            # DB에서 핵심 컬럼 조회 (이미지 벡터는 제외하되 이미지 URL은 포함)
            query = """
                SELECT
                    pr.place_id::text as place_id,
                    pr.table_name,
                    pr.vector as vector,
                    pr.name,
                    pr.region,
                    pr.city,
                    pr.latitude,
                    pr.longitude,
                    pr.bookmark_cnt,
                    pr.image_urls,  -- 메인 페이지 이미지 표시용
                    pr.overview,    -- 간단한 설명
                    COALESCE(pr.bookmark_cnt, 0) as total_likes,
                    COALESCE(pr.bookmark_cnt, 0) as total_bookmarks,
                    COALESCE(pr.bookmark_cnt, 0) as total_clicks,
                    COALESCE(pr.bookmark_cnt, 0)::float as popularity_score,
                    COALESCE(pr.bookmark_cnt, 0)::float as engagement_score
                FROM place_recommendations pr
                WHERE
                    pr.vector IS NOT NULL
                    AND pr.name IS NOT NULL
                    AND pr.bookmark_cnt IS NOT NULL
                    AND pr.bookmark_cnt > 0
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

            # 성능 최적화: 북마크 기준 정렬로 상위만 조회
            query += " ORDER BY COALESCE(pr.bookmark_cnt, 0) DESC"
            param_count += 1
            query += f" LIMIT ${param_count}"
            params.append(limit)

            places = await self.db_manager.execute_query(query, *params)

            # 벡터 검증 및 이미지 URL 변환
            valid_places = []
            for place in places:
                if place['vector'] is not None:  # 간단한 null 체크만
                    # S3 이미지 URL을 HTTPS로 변환 (공통 함수 사용)
                    place = self._convert_s3_urls_to_https(place)
                    valid_places.append(place)

            # 캐시에 저장
            self._update_cache(cache_key, valid_places, 'place_batch')

            logger.info(f"📋 Fast retrieval: {len(valid_places)} places for {region or 'all'}/{category or 'all'}")
            return valid_places

        except Exception as e:
            logger.error(f"❌ Failed to get fast place candidates: {e}")
            return []

    async def _get_fast_vector_recommendations(
        self,
        user_id: str,
        user_vector: np.ndarray,
        region: Optional[str],
        category: Optional[str],
        limit: int
    ) -> List[Dict]:
        """메인 페이지용 고속 벡터 기반 추천 (단일 채널만)"""
        try:
            # 캐시된 유사도 결과 확인
            similarity_cache_key = f"similarity:{user_id}:{region or 'all'}:{category or 'all'}:{limit}"
            if self._is_cache_valid(similarity_cache_key, 'similarity'):
                logger.info(f"⚡ Using cached similarities for user {user_id}")
                cached_results = self.similarity_cache[similarity_cache_key]
                return cached_results[:limit]

            # 고속 장소 후보 조회 (제한된 수)
            places = await self._get_fast_place_candidates(region, category, min(limit * 3, 150))

            if not places:
                logger.warning("⚠️ No fast candidates found, falling back to popular")
                return await self._get_popular_recommendations(region, category, limit, fast_mode=True)

            # 벡터 배치 처리 (최적화)
            place_vectors = []
            valid_places = []

            for place in places:
                vector = validate_vector_data(place['vector'])
                if vector is not None:
                    place_vectors.append(vector)
                    # S3 이미지 URL을 HTTPS로 변환
                    place = self._convert_s3_urls_to_https(place)
                    valid_places.append(place)

            if not valid_places:
                return await self._get_popular_recommendations(region, category, limit, fast_mode=True)

            # 벡터화된 유사도 계산 (단일 채널)
            place_vectors_array = np.array(place_vectors, dtype=np.float32)
            similarities = safe_cosine_similarity(
                user_vector,
                place_vectors_array,
                use_ann=self.ann_enabled,
                faiss_manager=self.faiss_manager
            )

            # 통계 업데이트
            if self.ann_enabled:
                self.stats['ann_searches'] += 1
            else:
                self.stats['cosine_searches'] += 1

            # 간소화된 점수 계산 (복잡한 가중치 없음)
            results = []
            for i, place in enumerate(valid_places):
                try:
                    similarity = float(similarities[i])

                    # 임계값 적용
                    if similarity < CONFIG.min_similarity_threshold:
                        continue

                    # 간단한 하이브리드 점수 (빠른 계산)
                    bookmark_count = place.get('bookmark_cnt', 0)
                    popularity_factor = min(bookmark_count / 100.0, 1.0)  # 간단한 정규화

                    final_score = similarity * 0.7 + popularity_factor * 0.3

                    place['similarity_score'] = round(similarity, 4)
                    place['final_score'] = round(final_score, 4)
                    place['recommendation_type'] = 'fast_personalized'

                    results.append(place)

                except Exception as e:
                    logger.error(f"❌ Fast score calculation failed for place {i}: {e}")
                    continue

            # 점수순 정렬
            results.sort(key=lambda x: x['final_score'], reverse=True)
            final_results = results[:limit]

            # 유사도 결과 캐시
            self._update_cache(similarity_cache_key, final_results, 'similarity')

            logger.info(f"⚡ Fast recommendations: {len(final_results)} results for user {user_id}")

            # 이미지 URL 포함 여부 디버깅
            image_count = sum(1 for place in final_results if place.get('image_urls'))
            logger.info(f"📸 이미지 포함 장소: {image_count}/{len(final_results)}개")

            # 첫 번째 결과의 이미지 URL 로깅
            if final_results and final_results[0].get('image_urls'):
                first_place = final_results[0]
                logger.info(f"🖼️ 첫 번째 장소 '{first_place.get('name')}' 이미지: {first_place.get('image_urls')}")

            return final_results

        except Exception as e:
            logger.error(f"❌ Fast vector recommendation failed: {e}")
            return await self._get_popular_recommendations(region, category, limit, fast_mode=True)


    async def _get_hybrid_fast_recommendations(
        self,
        user_id: str,
        user_priority: str,
        region: Optional[str],
        category: Optional[str],
        limit: int
    ) -> List[Dict]:
        """Fast mode용 하이브리드 추천 (95% 선호도 + 5% 행동 데이터)"""
        try:
            # 더 많은 결과를 가져와서 혼합
            extended_limit = min(limit * 4, 100)

            # 1. 선호도 기반 추천 (95%)
            preference_results = await self._get_preference_based_recommendations(
                user_id, region, category, extended_limit
            )

            # 2. 행동 벡터 기반 추천 (5%)
            user_vector = await self._get_user_behavior_vector_cached(user_id)
            behavior_results = []
            if user_vector is not None:
                behavior_results = await self._get_fast_vector_recommendations(
                    user_id, user_vector, region, category, extended_limit
                )

            # 3. 결과 혼합 (95:5 비율) - 하드코딩으로 임시 해결
            preference_weight = 0.95  # experienced_user_preference_weight
            behavior_weight = 0.05    # experienced_user_behavior_weight

            # 점수 재계산 및 혼합
            combined_results = {}

            # 선호도 결과 추가 (95% 가중치)
            for place in preference_results:
                place_id = place.get('place_id') or place.get('id')
                if place_id:
                    adjusted_score = place.get('final_score', 0) * preference_weight
                    place_copy = place.copy()
                    place_copy['final_score'] = adjusted_score
                    place_copy['source'] = 'preference'
                    combined_results[place_id] = place_copy

            # 행동 데이터 결과 추가 (5% 가중치, 중복 시 점수 합산)
            for place in behavior_results:
                place_id = place.get('place_id') or place.get('id')
                if place_id:
                    adjusted_score = place.get('final_score', 0) * behavior_weight

                    if place_id in combined_results:
                        # 기존 선호도 점수에 행동 점수 추가
                        combined_results[place_id]['final_score'] += adjusted_score
                        combined_results[place_id]['source'] = 'hybrid'
                    else:
                        # 새로운 행동 기반 결과
                        place_copy = place.copy()
                        place_copy['final_score'] = adjusted_score
                        place_copy['source'] = 'behavior'
                        combined_results[place_id] = place_copy

            # 최종 결과 정렬 및 제한
            final_results = list(combined_results.values())
            final_results.sort(key=lambda x: x['final_score'], reverse=True)
            final_results = final_results[:limit]

            # 통계 로깅
            preference_count = sum(1 for r in final_results if r.get('source') in ['preference', 'hybrid'])
            behavior_count = sum(1 for r in final_results if r.get('source') == 'behavior')
            hybrid_count = sum(1 for r in final_results if r.get('source') == 'hybrid')

            logger.info(f"🔄 Hybrid results: {len(final_results)} total "
                      f"(preference: {preference_count-hybrid_count}, behavior: {behavior_count}, hybrid: {hybrid_count})")

            return final_results

        except Exception as e:
            logger.error(f"❌ Hybrid fast recommendation failed: {e}")
            # 실패 시 선호도 기반으로 폴백
            return await self._get_preference_based_recommendations(user_id, region, category, limit)

    async def _get_user_personalized_recommendations(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        사용자 맞춤 추천 (전체 지역 대상)
        - 행동 벡터가 있으면: 모든 지역에서 행동 벡터 기반 유사도 순 추천
        - 행동 벡터가 없으면: 모든 지역에서 선호도 기반 점수 순 추천
        - 중복 제거 후 유사도/점수 순으로 정렬하여 반환
        """
        try:
            # 1. 사용자 선호도 정보 조회
            logger.info(f"🔍 [Personalized] Getting user preferences for user {user_id}")
            user_preferences = await self._get_user_preferences(user_id)
            if not user_preferences:
                logger.info(f"❌ [Personalized] No preferences found for user {user_id}")
                return []

            user_priority = user_preferences.get('priority')
            if not user_priority:
                logger.info(f"❌ [Personalized] No priority found for user {user_id}")
                return []

            logger.info(f"✅ [Personalized] Found user preferences for user {user_id}: priority={user_priority}")

            # 2. 사용자 행동 벡터 조회 (북마크 패턴 분석용)
            logger.info(f"🧠 [Personalized] Getting user behavior vector for user {user_id}")
            user_behavior_vector = await self._get_user_behavior_vector_cached(user_id)
            if user_behavior_vector is not None:
                logger.info(f"✅ [Personalized] Found behavior vector for user {user_id}: shape {user_behavior_vector.shape}")
                logger.info(f"🔍 [Personalized] Behavior vector type: {type(user_behavior_vector)}, non-zero elements: {np.count_nonzero(user_behavior_vector)}")
            else:
                logger.info(f"❌ [Personalized] No behavior vector found for user {user_id}")
                # 추가 디버깅: user_behavior_vectors 테이블 직접 확인
                try:
                    async with self.db_manager.get_connection() as conn:
                        debug_result = await conn.fetchrow(
                            "SELECT user_id, behavior_vector IS NOT NULL as has_vector FROM user_behavior_vectors WHERE user_id = $1",
                            user_id
                        )
                        if debug_result:
                            logger.info(f"🔍 [Personalized] DEBUG: user_behavior_vectors table has user {user_id}, has_vector: {debug_result['has_vector']}")
                        else:
                            logger.info(f"🔍 [Personalized] DEBUG: user {user_id} not found in user_behavior_vectors table")
                except Exception as debug_e:
                    logger.warning(f"⚠️ [Personalized] DEBUG query failed: {debug_e}")

            # 2. 모든 지역 목록 가져오기 (점수 계산 없이)
            regions_query = """
                SELECT DISTINCT region
                FROM place_recommendations
                WHERE region IS NOT NULL
                ORDER BY region
            """

            all_regions = []
            async with self.db_manager.get_connection() as conn:
                regions_data = await conn.fetch(regions_query)
                all_regions = [row['region'] for row in regions_data]

            logger.info(f"📍 Found {len(all_regions)} regions: {all_regions}")

            # 3. 모든 지역의 추천을 수집하고 유사도 순으로 정렬
            all_recommendations = []
            logger.info(f"🔥 [DEBUG] Starting to collect recommendations from {len(all_regions)} regions")

            for region in all_regions:
                # 해당 지역의 추천 생성
                logger.info(f"🎯 [Personalized] Generating recommendations for region {region}")

                # behavior_vector가 있는 사용자는 행동 벡터 기반 유사한 장소만 추천 (우선순위 카테고리 무관)
                if user_behavior_vector is not None:
                    logger.info(f"🧠 [Personalized] Using behavior vector based recommendations for region {region}")

                    # 행동 벡터 기반 유사한 장소 추천만 사용 (우선순위 카테고리 상관없이)
                    try:
                        region_recommendations = await self._get_similar_places_in_region(
                            user_behavior_vector, region, 5  # 각 지역에서 5개씩만 가져오기
                        )
                        logger.info(f"🔍 [Personalized] Found {len(region_recommendations)} behavior-based recommendations for {region}")
                    except Exception as e:
                        logger.warning(f"⚠️ Similar places search failed for {region}, using fallback: {e}")
                        # 폴백으로 간단한 지역 기반 추천 사용
                        region_recommendations = await self._get_simple_regional_recommendations(region, 5)
                else:
                    logger.info(f"🎯 [Personalized] Using priority-based recommendations for region {region}")

                    # 기존 방식: 우선순위 태그 기반 추천만 - 더 많은 데이터 가져오기
                    region_recommendations = await self._calculate_priority_enhanced_scores(
                        user_preferences, user_behavior_vector, region, None, 15  # 각 지역에서 15개씩 가져오기 (5->15로 증가)
                    )

                if region_recommendations:
                    # 지역 정보 메타데이터 추가
                    for rec in region_recommendations:
                        rec['source_region'] = region

                    all_recommendations.extend(region_recommendations)
                    logger.info(f"🔥 [DEBUG] Added {len(region_recommendations)} recommendations from {region}")
                else:
                    logger.info(f"🔥 [DEBUG] No recommendations from {region}")

            # 디버깅: 지역별 추천 분포 확인
            region_distribution = {}
            for rec in all_recommendations:
                region = rec.get('source_region', 'unknown')
                region_distribution[region] = region_distribution.get(region, 0) + 1

            logger.info(f"🗺️ [DEBUG] Regional distribution BEFORE sorting: {region_distribution}")
            logger.info(f"🔢 [DEBUG] Total recommendations collected: {len(all_recommendations)}")
            logger.info(f"🔥 [DEBUG] About to sort recommendations")

            # 5. 모든 추천을 유사도/점수 순으로 정렬
            if user_behavior_vector is not None:
                # 행동 벡터가 있는 경우: similarity_score 또는 final_score로 정렬
                all_recommendations.sort(key=lambda x: x.get('similarity_score', x.get('final_score', 0)), reverse=True)
                logger.info(f"🎯 [Personalized] Sorted all recommendations by similarity_score for behavior vector user")
            else:
                # 행동 벡터가 없는 경우: final_score로 정렬
                all_recommendations.sort(key=lambda x: x.get('final_score', 0), reverse=True)
                logger.info(f"🎯 [Personalized] Sorted all recommendations by final_score for preference-based user")

            # 중복 제거 (place_id 기준)
            seen_places = set()
            final_recommendations = []
            for rec in all_recommendations:
                place_id = rec.get('place_id')
                if place_id not in seen_places:
                    seen_places.add(place_id)
                    final_recommendations.append(rec)

                if len(final_recommendations) >= limit:
                    break

            # 디버깅: 최종 결과의 지역별 분포 확인
            final_region_distribution = {}
            for rec in final_recommendations:
                region = rec.get('source_region', 'unknown')
                final_region_distribution[region] = final_region_distribution.get(region, 0) + 1

            logger.info(f"🏁 [DEBUG] Final regional distribution: {final_region_distribution}")
            logger.info(f"📋 [DEBUG] Sample recommendations (first 3): {[{'name': r.get('name'), 'region': r.get('source_region'), 'score': r.get('similarity_score', r.get('final_score', 0))} for r in final_recommendations[:3]]}")

            logger.info(f"✅ Generated {len(final_recommendations)} user personalized recommendations for user {user_id}")
            logger.info(f"🔥 [DEBUG] Returning {min(len(final_recommendations), limit)} recommendations")
            return final_recommendations[:limit]

        except Exception as e:
            logger.error(f"❌ User personalized recommendation failed for user {user_id}: {e}")
            logger.error(f"🔥 [DEBUG] Exception traceback: ", exc_info=True)
            return []

    async def _calculate_regional_recommendation_scores(
        self,
        user_preferences: Dict[str, Any],
        user_behavior_vector: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """
        각 지역별 사용자 선호 태그 + 행동 벡터 기반 추천 수량 점수 계산
        """
        try:
            regional_scores = {}

            # 지역별 장소 데이터와 사용자 선호도 매칭 점수 계산
            regions_query = """
                SELECT DISTINCT region, COUNT(*) as place_count
                FROM place_recommendations
                WHERE region IS NOT NULL
                GROUP BY region
                ORDER BY place_count DESC
            """

            async with self.db_manager.pool.acquire() as conn:
                regions_data = await conn.fetch(regions_query)

                for region_row in regions_data:
                    region = region_row['region']
                    place_count = region_row['place_count']

                    # 해당 지역의 사용자 선호도 기반 점수 계산
                    region_score = await self._calculate_region_preference_score(
                        user_preferences, region, conn
                    )

                    # 행동 벡터 기반 지역 선호도 점수 계산 (안전한 fallback)
                    behavior_score = 0.0
                    if user_behavior_vector is not None:
                        try:
                            behavior_score = await self._calculate_region_behavior_score(
                                user_behavior_vector, region, conn
                            )
                            logger.info(f"🧠 [Regional] Region {region} behavior score: {behavior_score:.4f}")
                        except Exception as e:
                            logger.warning(f"⚠️ Behavior score calculation failed for {region}: {e}")
                            behavior_score = 0.0

                    # 태그 선호도 + 행동 벡터 + 장소 수를 결합한 최종 점수
                    combined_score = (region_score * 0.6) + (behavior_score * 0.4)  # 태그:행동 = 6:4 비율
                    final_score = combined_score * (1 + place_count / 1000)  # 장소 수 가중치 적용
                    regional_scores[region] = final_score

            return regional_scores

        except Exception as e:
            logger.error(f"❌ Regional scores calculation failed: {e}")
            return {}

    async def _calculate_region_preference_score(
        self,
        user_preferences: Dict[str, Any],
        region: str,
        conn
    ) -> float:
        """
        특정 지역에 대한 사용자 우선순위 카테고리 기반 점수 계산
        오직 우선순위 카테고리의 장소 수만 계산
        """
        try:
            preference_score = 0.0
            user_priority = user_preferences.get('priority')

            # 우선순위 카테고리의 장소 수만 계산
            if user_priority:
                # experience 태그인 경우 nature, humanities, leisure_sports 포함
                if user_priority == 'experience':
                    experience_categories = ['nature', 'humanities', 'leisure_sports']
                    priority_query = """
                        SELECT COUNT(*) as count
                        FROM place_recommendations
                        WHERE region = $1 AND table_name = ANY($2)
                    """
                    priority_result = await conn.fetchrow(priority_query, region, experience_categories)
                else:
                    # 일반 카테고리 (accommodation, restaurants, shopping)
                    priority_query = """
                        SELECT COUNT(*) as count
                        FROM place_recommendations
                        WHERE region = $1 AND table_name = $2
                    """
                    priority_result = await conn.fetchrow(priority_query, region, user_priority)

                if priority_result:
                    preference_score = float(priority_result['count'])

            return preference_score

        except Exception as e:
            logger.error(f"❌ Region preference score calculation failed for {region}: {e}")
            return 0.0

    async def _calculate_region_behavior_score(
        self,
        user_behavior_vector: np.ndarray,
        region: str,
        conn
    ) -> float:
        """
        특정 지역에 대한 사용자 행동 벡터 기반 유사도 점수 계산
        """
        try:
            # 해당 지역의 장소들의 벡터를 가져와서 유사도 계산
            region_vectors_query = """
                SELECT pr.place_id, l.embedding_vector
                FROM place_recommendations pr
                JOIN locations l ON pr.place_id = l.id
                WHERE pr.region = $1
                AND l.embedding_vector IS NOT NULL
                AND array_length(l.embedding_vector, 1) > 0
                LIMIT 100
            """

            region_places = await conn.fetch(region_vectors_query, region)

            if not region_places:
                return 0.0

            # 벡터 유효성 검사 및 수집
            valid_vectors = []
            for place in region_places:
                vector = validate_vector_data(place['embedding_vector'])
                if vector is not None:
                    valid_vectors.append(vector)

            if not valid_vectors:
                return 0.0

            # 지역 장소들의 평균 벡터 계산
            region_vectors_array = np.array(valid_vectors, dtype=np.float32)
            region_avg_vector = np.mean(region_vectors_array, axis=0)

            # 사용자 행동 벡터와 지역 평균 벡터 간 유사도 계산 (ANN 지원)
            similarities = safe_cosine_similarity(
                user_behavior_vector,
                region_avg_vector.reshape(1, -1),
                use_ann=self.ann_enabled,
                faiss_manager=self.faiss_manager
            )

            # 통계 업데이트
            if self.ann_enabled:
                self.stats['ann_searches'] += 1
            else:
                self.stats['cosine_searches'] += 1

            similarity_score = float(similarities[0]) if len(similarities) > 0 else 0.0

            # 0-1 범위로 정규화하고 가중치 적용
            normalized_score = max(0.0, similarity_score)

            logger.info(f"🧠 [Regional] Region {region}: {len(valid_vectors)} places, similarity={similarity_score:.4f}")

            return normalized_score

        except Exception as e:
            logger.error(f"❌ Region behavior score calculation failed for {region}: {e}")
            return 0.0

    async def _get_similar_places_in_region(
        self,
        user_behavior_vector: np.ndarray,
        region: str,
        limit: int = 10,
        category_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        특정 지역에서 사용자 행동 벡터와 유사한 장소들을 ANN으로 찾기
        """
        try:
            logger.info(f"🔍 [Similar] Finding similar places in region {region} using ANN")

            # ANN이 활성화된 경우, 빠른 유사도 검색 수행
            if self.ann_enabled and self.faiss_manager.index is not None:
                # ANN으로 유사한 장소 ID들 찾기
                similar_place_ids, scores = self.faiss_manager.search(user_behavior_vector, k=limit * 3)

                if not similar_place_ids:
                    return []

                # 해당 지역의 장소들만 필터링
                if category_filter:
                    region_query = """
                        SELECT
                            pr.place_id, pr.table_name, pr.region, pr.name,
                            pr.latitude, pr.longitude, pr.overview, pr.image_urls,
                            pr.bookmark_cnt, pr.vector as text_vector,
                            pr.vector as embedding_vector
                        FROM place_recommendations pr
                        WHERE pr.region = $1
                        AND pr.place_id = ANY($2)
                        AND pr.table_name = $3
                        AND pr.name IS NOT NULL
                        ORDER BY pr.bookmark_cnt DESC
                    """
                else:
                    region_query = """
                        SELECT
                            pr.place_id, pr.table_name, pr.region, pr.name,
                            pr.latitude, pr.longitude, pr.overview, pr.image_urls,
                            pr.bookmark_cnt, pr.vector as text_vector,
                            pr.vector as embedding_vector
                        FROM place_recommendations pr
                        WHERE pr.region = $1
                        AND pr.place_id = ANY($2)
                        AND pr.name IS NOT NULL
                        ORDER BY pr.bookmark_cnt DESC
                    """

                async with self.db_manager.get_connection() as conn:
                    if category_filter:
                        places_data = await conn.fetch(region_query, region, similar_place_ids, category_filter)
                    else:
                        places_data = await conn.fetch(region_query, region, similar_place_ids)

                # 실제 유사도 점수로 정렬
                scored_places = []
                place_id_to_score = {pid: score for pid, score in zip(similar_place_ids, scores)}

                for place in places_data:
                    place_dict = dict(place)
                    ann_score = place_id_to_score.get(place['place_id'], 0.0)

                    # 유사도 점수와 인기도를 결합한 최종 점수
                    popularity_score = min(place['bookmark_cnt'] / 100.0, 1.0) if place['bookmark_cnt'] else 0.0
                    final_score = (ann_score * 0.8) + (popularity_score * 0.2)

                    place_dict['similarity_score'] = ann_score
                    place_dict['final_score'] = final_score
                    place_dict['recommendation_type'] = 'similar_places_ann'
                    place_dict['source'] = 'behavior_based'

                    scored_places.append(place_dict)

                # 최종 점수로 정렬
                scored_places.sort(key=lambda x: x['final_score'], reverse=True)

                self.stats['ann_searches'] += 1
                logger.info(f"✅ [Similar] Found {len(scored_places)} similar places in {region} using ANN")

                return scored_places[:limit]

            else:
                # ANN이 비활성화된 경우, 전통적인 코사인 유사도 사용
                return await self._get_similar_places_fallback(user_behavior_vector, region, limit, category_filter)

        except Exception as e:
            logger.error(f"❌ Similar places search failed for region {region}: {e}")
            return []

    async def _get_similar_places_fallback(
        self,
        user_behavior_vector: np.ndarray,
        region: str,
        limit: int = 10,
        category_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        전통적인 코사인 유사도를 사용한 유사한 장소 검색 (Fallback)
        """
        try:
            # 해당 지역의 모든 장소 벡터 조회
            if category_filter:
                region_query = """
                    SELECT
                        pr.place_id, pr.table_name, pr.region, pr.name,
                        pr.latitude, pr.longitude, pr.overview, pr.image_urls,
                        pr.bookmark_cnt, pr.vector as text_vector,
                        pr.vector as embedding_vector
                    FROM place_recommendations pr
                    WHERE pr.region = $1
                    AND pr.table_name = $2
                    AND pr.vector IS NOT NULL
                    AND pr.name IS NOT NULL
                    LIMIT 200
                """
            else:
                region_query = """
                    SELECT
                        pr.place_id, pr.table_name, pr.region, pr.name,
                        pr.latitude, pr.longitude, pr.overview, pr.image_urls,
                        pr.bookmark_cnt, pr.vector as text_vector,
                        pr.vector as embedding_vector
                    FROM place_recommendations pr
                    WHERE pr.region = $1
                    AND pr.vector IS NOT NULL
                    AND pr.name IS NOT NULL
                    LIMIT 200
                """

            async with self.db_manager.get_connection() as conn:
                if category_filter:
                    places_data = await conn.fetch(region_query, region, category_filter)
                else:
                    places_data = await conn.fetch(region_query, region)

            if not places_data:
                return []

            # 벡터 유효성 검사 및 유사도 계산
            valid_places = []
            place_vectors = []

            for place in places_data:
                vector = validate_vector_data(place['embedding_vector'])
                if vector is not None:
                    valid_places.append(dict(place))
                    place_vectors.append(vector)

            if not valid_places:
                return []

            # 벡터화된 유사도 계산
            place_vectors_array = np.array(place_vectors, dtype=np.float32)
            similarities = safe_cosine_similarity(user_behavior_vector, place_vectors_array, use_ann=False)

            # 점수화 및 정렬
            scored_places = []
            for i, place in enumerate(valid_places):
                similarity_score = float(similarities[i])
                popularity_score = min(place['bookmark_cnt'] / 100.0, 1.0) if place['bookmark_cnt'] else 0.0
                final_score = (similarity_score * 0.8) + (popularity_score * 0.2)

                place['similarity_score'] = similarity_score
                place['final_score'] = final_score
                place['recommendation_type'] = 'similar_places_cosine'
                place['source'] = 'behavior_based'

                scored_places.append(place)

            # 최종 점수로 정렬
            scored_places.sort(key=lambda x: x['final_score'], reverse=True)

            self.stats['cosine_searches'] += 1
            logger.info(f"✅ [Similar] Found {len(scored_places)} similar places in {region} using cosine similarity")

            return scored_places[:limit]

        except Exception as e:
            logger.error(f"❌ Similar places fallback search failed for region {region}: {e}")
            return []

    def _merge_recommendations(
        self,
        priority_recommendations: List[Dict],
        similar_recommendations: List[Dict],
        target_limit: int
    ) -> List[Dict]:
        """
        우선순위 추천과 유사한 장소 추천을 병합 (중복 제거)
        """
        try:
            # place_id를 기준으로 중복 제거
            seen_place_ids = set()
            merged_recommendations = []

            # 1. 우선순위 추천을 먼저 추가
            for rec in priority_recommendations:
                place_id = rec.get('place_id')
                if place_id and place_id not in seen_place_ids:
                    rec['merge_source'] = 'priority'
                    merged_recommendations.append(rec)
                    seen_place_ids.add(place_id)

            # 2. 유사한 장소 추천 추가 (중복되지 않는 것만)
            for rec in similar_recommendations:
                place_id = rec.get('place_id')
                if place_id and place_id not in seen_place_ids:
                    rec['merge_source'] = 'similar'
                    merged_recommendations.append(rec)
                    seen_place_ids.add(place_id)

            # 3. 목표 개수에 맞춰 자르기
            final_recommendations = merged_recommendations[:target_limit]

            logger.info(f"🔄 [Merge] Combined {len(priority_recommendations)} priority + {len(similar_recommendations)} similar → {len(final_recommendations)} final")

            return final_recommendations

        except Exception as e:
            logger.error(f"❌ Recommendation merge failed: {e}")
            return priority_recommendations[:target_limit]  # Fallback to priority only

    async def _get_diverse_category_recommendations(
        self,
        user_behavior_vector: np.ndarray,
        region: str,
        limit: int,
        exclude_priority: Optional[str] = None
    ) -> List[Dict]:
        """
        행동 벡터를 기반으로 다양한 카테고리에서 추천 생성
        우선순위 카테고리는 제외하고 다른 카테고리들에서 추천
        """
        try:
            logger.info(f"🌈 [Diverse] STARTED - Getting diverse category recommendations for region {region}, limit={limit}, excluding {exclude_priority}")
            logger.info(f"🌈 [Diverse] Input validation - user_behavior_vector: {user_behavior_vector is not None}, region: {region}, limit: {limit}")

            # 모든 카테고리 목록 (우선순위 카테고리 제외)
            all_categories = ['nature', 'humanities', 'leisure_sports', 'accommodation', 'dining', 'shopping']

            # experience는 특별 처리 - nature, humanities, leisure_sports 포함하므로 이들은 제외
            if exclude_priority == 'experience':
                diverse_categories = ['accommodation', 'dining', 'shopping']
            elif exclude_priority in all_categories:
                diverse_categories = [cat for cat in all_categories if cat != exclude_priority]
            else:
                diverse_categories = all_categories

            logger.info(f"🎯 [Diverse] Target categories: {diverse_categories}")

            diverse_recommendations = []
            items_per_category = max(1, limit // len(diverse_categories)) if diverse_categories else 0

            for category in diverse_categories:
                try:
                    # 해당 카테고리에서 행동 벡터 기반 추천 생성
                    category_places = await self._get_category_places_with_vectors(region, category)

                    if not category_places:
                        logger.info(f"⚠️ [Diverse] No places found for category {category} in region {region}")
                        continue

                    # 행동 벡터와의 유사도 계산
                    category_recommendations = []
                    for place in category_places:
                        try:
                            place_vector = validate_vector_data(place.get('text_vector'))
                            if place_vector is not None:
                                similarity = safe_cosine_similarity(
                                    user_behavior_vector.reshape(1, -1),
                                    place_vector.reshape(1, -1)
                                )[0]

                                place_dict = dict(place)
                                place_dict['similarity_score'] = float(similarity)
                                place_dict['recommendation_category'] = category
                                place_dict['recommendation_source'] = 'diverse_category'
                                category_recommendations.append(place_dict)
                        except Exception as place_e:
                            logger.warning(f"⚠️ [Diverse] Failed to process place {place.get('place_id', 'unknown')}: {place_e}")
                            continue

                    # 유사도 순으로 정렬
                    category_recommendations.sort(key=lambda x: x['similarity_score'], reverse=True)
                    selected_recommendations = category_recommendations[:items_per_category]

                    if selected_recommendations:
                        logger.info(f"✅ [Diverse] Added {len(selected_recommendations)} recommendations from {category}")
                        diverse_recommendations.extend(selected_recommendations)

                except Exception as cat_e:
                    logger.warning(f"⚠️ [Diverse] Failed to get recommendations for category {category}: {cat_e}")
                    continue

            logger.info(f"🌈 [Diverse] Generated {len(diverse_recommendations)} diverse category recommendations")
            return diverse_recommendations[:limit]

        except Exception as e:
            logger.error(f"❌ [Diverse] Diverse category recommendations failed: {e}")
            return []

    async def _get_category_places_with_vectors(self, region: str, category: str) -> List[Dict]:
        """특정 지역과 카테고리의 장소들과 벡터 데이터 조회"""
        try:
            places_query = """
                SELECT
                    place_id, table_name, region, name,
                    latitude, longitude, overview, image_urls, bookmark_cnt,
                    vector as text_vector
                FROM place_recommendations
                WHERE name IS NOT NULL
                    AND region = $1
                    AND table_name = $2
                    AND vector IS NOT NULL
                ORDER BY bookmark_cnt DESC
                LIMIT 100
            """

            async with self.db_manager.get_connection() as conn:
                places_data = await conn.fetch(places_query, region, category)
                return [dict(row) for row in places_data]

        except Exception as e:
            logger.error(f"❌ Failed to get places for region {region}, category {category}: {e}")
            return []

    def _merge_diverse_recommendations(
        self,
        priority_recommendations: List[Dict],
        diverse_recommendations: List[Dict],
        similar_recommendations: List[Dict],
        target_limit: int
    ) -> List[Dict]:
        """
        우선순위, 다양한 카테고리, 유사한 장소 추천을 병합 (중복 제거)
        """
        try:
            seen_place_ids = set()
            merged_recommendations = []

            # 1. 우선순위 추천을 먼저 추가
            for rec in priority_recommendations:
                place_id = rec.get('place_id')
                if place_id and place_id not in seen_place_ids:
                    rec['merge_source'] = 'priority'
                    merged_recommendations.append(rec)
                    seen_place_ids.add(place_id)

            # 2. 다양한 카테고리 추천 추가
            for rec in diverse_recommendations:
                place_id = rec.get('place_id')
                if place_id and place_id not in seen_place_ids:
                    rec['merge_source'] = 'diverse_category'
                    merged_recommendations.append(rec)
                    seen_place_ids.add(place_id)

            # 3. 유사한 장소 추천 추가 (중복되지 않는 것만)
            for rec in similar_recommendations:
                place_id = rec.get('place_id')
                if place_id and place_id not in seen_place_ids:
                    rec['merge_source'] = 'similar'
                    merged_recommendations.append(rec)
                    seen_place_ids.add(place_id)

            # 4. 목표 개수에 맞춰 자르기
            final_recommendations = merged_recommendations[:target_limit]

            logger.info(f"🔄 [Diverse Merge] Combined {len(priority_recommendations)} priority + {len(diverse_recommendations)} diverse + {len(similar_recommendations)} similar → {len(final_recommendations)} final")

            return final_recommendations

        except Exception as e:
            logger.error(f"❌ Diverse recommendation merge failed: {e}")
            return priority_recommendations[:target_limit]  # Fallback to priority only

    async def _get_priority_ordered_recommendations(
        self,
        user_preferences: Dict[str, Any],
        region: str,
        user_priority: str,
        limit: int
    ) -> List[Dict]:
        """
        지역 내에서 사용자 우선순위 카테고리만 추천 생성
        """
        try:
            recommendations = []

            # experience 태그인 경우 nature, humanities, leisure_sports만 추천
            if user_priority == 'experience':
                experience_categories = ['nature', 'humanities', 'leisure_sports']
                for category in experience_categories:
                    category_recommendations = await self._calculate_preference_scores(
                        user_preferences, region, category, limit // len(experience_categories) + 1
                    )

                    if category_recommendations:
                        for rec in category_recommendations:
                            rec['category_priority'] = 'high'
                            rec['recommendation_reason'] = f'체험 우선순위: {category}'
                        recommendations.extend(category_recommendations)
            else:
                # 일반 카테고리는 해당 카테고리만 추천
                priority_recommendations = await self._calculate_preference_scores(
                    user_preferences, region, user_priority, limit
                )

                if priority_recommendations:
                    for rec in priority_recommendations:
                        rec['category_priority'] = 'high'
                        rec['recommendation_reason'] = f'사용자 우선순위: {user_priority}'
                    recommendations.extend(priority_recommendations)

            logger.info(f"🎯 Generated {len(recommendations)} priority-only recommendations for {region} ({user_priority})")
            return recommendations[:limit]

        except Exception as e:
            logger.error(f"❌ Priority ordered recommendations failed for {region}: {e}")
            return []

    async def _get_simple_regional_recommendations(
        self,
        region: str,
        limit: int
    ) -> List[Dict]:
        """
        간단한 지역 기반 추천 (폴백용)
        """
        try:
            query = """
                SELECT
                    pr.place_id, pr.table_name, pr.region, pr.name,
                    pr.latitude, pr.longitude, pr.overview, pr.image_urls,
                    pr.bookmark_cnt, pr.vector as text_vector,
                    pr.vector as embedding_vector
                FROM place_recommendations pr
                WHERE pr.region = $1
                AND pr.name IS NOT NULL
                ORDER BY pr.bookmark_cnt DESC
                LIMIT $2
            """

            async with self.db_manager.get_connection() as conn:
                places_data = await conn.fetch(query, region, limit)

            recommendations = []
            for place in places_data:
                place_dict = dict(place)
                place_dict['recommendation_type'] = 'simple_regional'
                place_dict['source'] = 'regional_fallback'
                recommendations.append(place_dict)

            logger.info(f"📍 Generated {len(recommendations)} simple regional recommendations for {region}")
            return recommendations

        except Exception as e:
            logger.error(f"❌ Simple regional recommendations failed for {region}: {e}")
            return []


# ============================================================================
# 🚀 전역 엔진 인스턴스 (싱글톤 패턴)
# ============================================================================

_engine_instance: Optional[UnifiedRecommendationEngine] = None

async def get_engine() -> UnifiedRecommendationEngine:
    """전역 엔진 인스턴스 반환 (지연 초기화)"""
    global _engine_instance

    if _engine_instance is None:
        try:
            _engine_instance = UnifiedRecommendationEngine()
            await _engine_instance.initialize()
            logger.info("✅ Global recommendation engine initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize recommendation engine: {e}")
            # 실패 시에도 기본 엔진은 반환 (부분 기능 사용)
            if _engine_instance is None:
                _engine_instance = UnifiedRecommendationEngine()
                # 초기화 실패해도 기본 DB 연결만이라도 시도
                try:
                    await _engine_instance.db_manager.initialize()
                except Exception as db_e:
                    logger.error(f"❌ DB connection also failed: {db_e}")

    return _engine_instance

async def close_engine():
    """전역 엔진 인스턴스 정리"""
    global _engine_instance

    if _engine_instance:
        await _engine_instance.close()
        _engine_instance = None


