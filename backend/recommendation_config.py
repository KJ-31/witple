# 파일명: recommendation_config.py (통합 설정)

from dataclasses import dataclass
from typing import Dict, List
import os

@dataclass
class UnifiedRecommendationConfig:
    """통합 추천 시스템 설정"""

    # =============================================================================
    # 🗄️ 데이터베이스 설정 (통합)
    # =============================================================================
    database_url: str = None

    # Connection Pool 설정 (고속 처리용 최적화)
    min_pool_size: int = 5   # 초기 연결 수 증가 (대기시간 감소)
    max_pool_size: int = 25  # 최대 연결 수 대폭 증가 (동시 요청 처리)
    db_timeout: int = 3      # 메인 페이지용 빠른 타임아웃

    # 연결 풀 고급 설정
    pool_pre_ping: bool = True          # 연결 상태 사전 확인
    pool_recycle: int = 1800           # 30분마다 연결 재생성
    acquire_timeout: float = 1.0        # 연결 획득 타임아웃 1초

    # =============================================================================
    # 🚀 API 설정 (메인 페이지 최적화)
    # =============================================================================
    recommendation_timeout: float = 2.0  # 메인 페이지 빠른 응답
    detail_timeout: float = 5.0          # 상세 페이지 충분한 시간
    max_parallel_requests: int = 15      # 병렬 요청 수 증가 (풀 확장에 따라)

    # 메인 페이지 전용 설정
    main_page_cache_priority: bool = True  # 메인 페이지 캐시 우선
    fast_mode_default: bool = True         # 대부분의 API에서 fast_mode 기본 사용

    # =============================================================================
    # 🎯 추천 알고리즘 설정
    # =============================================================================
    candidate_limit: int = 500  # 성능 최적화를 위해 2000에서 500으로 감소
    similarity_weight: float = 0.5  # 기본 균등 가중치 (동적으로 조정됨)
    popularity_weight: float = 0.5  # 기본 균등 가중치 (동적으로 조정됨)
    min_similarity_threshold: float = 0.1

    # 액션 가중치
    action_weights: Dict[str, float] = None

    # 선호도 기반 추천 설정
    preference_weights: Dict[str, float] = None
    travel_style_bonuses: Dict[str, Dict[str, float]] = None

    # =============================================================================
    # 🔄 동적 가중치 시스템 설정
    # =============================================================================
    # 신규 가입자: 우선순위 태그 초강력 편향 시스템
    new_user_preference_weight: float = 1.0  # 100% - 우선순위 태그만 사용 (초강력)
    new_user_behavior_weight: float = 0.0    # 0% - 행동 데이터 없음

    # 행동 데이터 있는 사용자: 95:5 비율 (선호도 최우선)
    experienced_user_preference_weight: float = 0.95   # 95% - 우선순위 태그 (거의 절대적)
    experienced_user_behavior_weight: float = 0.05     # 5% - 행동 데이터 (최소한 참고)

    # 행동 데이터 임계값 (이 값 이하면 신규 사용자로 간주)
    behavior_data_threshold: int = 3  # 북마크, 좋아요, 클릭 총합

    # =============================================================================
    # 📊 성능 및 캐싱 설정
    # =============================================================================
    # 계층적 캐싱 설정 (개선)
    vector_cache_size: int = 5000  # 기본 벡터 캐시 크기 대폭 증가
    cache_ttl_seconds: int = 1800  # 30분으로 연장 (추천 패턴 안정화)

    # 전용 캐시 크기
    user_data_cache_size: int = 1000  # 사용자 통합 데이터 캐시
    place_batch_cache_size: int = 500   # 장소 배치 데이터 캐시
    similarity_cache_size: int = 2000   # 유사도 계산 결과 캐시

    # 쿼리 성능 최적화 설정 (개선)
    use_prepared_statements: bool = True  # 준비된 쿼리문 사용
    batch_size: int = 100  # 배치 처리 크기 증가 (더 효율적)
    parallel_query_limit: int = 8  # 병렬 쿼리 제한 증가

    # 배치 처리 최적화
    vector_batch_size: int = 200  # 벡터 배치 처리 크기
    user_batch_size: int = 50     # 사용자 데이터 배치 크기
    similarity_batch_size: int = 100  # 유사도 계산 배치 크기

    # =============================================================================
    # 🌍 지역/카테고리 설정 (하드코딩 제거)
    # =============================================================================
    explore_regions: List[str] = None
    explore_categories: List[str] = None

    def __post_init__(self):
        """기본값 설정"""
        # 기존 시스템의 DB 설정 사용 (안전한 방식)
        if self.database_url is None:
            try:
                from config import settings
                self.database_url = settings.DATABASE_URL
            except Exception:
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                    self.database_url = os.getenv('DATABASE_URL')
                except Exception:
                    pass

            # 최종 폴백
            if not self.database_url:
                self.database_url = 'postgresql://user:pass@localhost/db'

        if self.action_weights is None:
            self.action_weights = {'click': 1.0, 'like': 3.0, 'bookmark': 5.0}

        if self.preference_weights is None:
            self.preference_weights = {
                'region': 0.2,    # 지역 비중 감소
                'category': 0.2,  # 카테고리 비중 감소
                'tag': 0.6,       # 태그 비중 대폭 증가 (30% → 60%)
                'max_tag_score': 15.0,  # 최대 태그 점수 증가
                'tag_boost_multiplier': 2.5,  # 태그 매칭 시 추가 증폭
                'popularity_normalizer': 1000.0
            }

        if self.travel_style_bonuses is None:
            self.travel_style_bonuses = {
                'luxury': {'accommodation': 0.1, 'restaurants': 0.1},
                'budget': {'nature': 0.1, 'culture': 0.1},
                'adventure': {'nature': 0.15, 'activity': 0.1},
                'cultural': {'culture': 0.15, 'restaurants': 0.05},
                'relaxation': {'accommodation': 0.1, 'nature': 0.1}
            }

        if self.explore_regions is None:
            self.explore_regions = [
                "서울특별시", "부산광역시", "제주특별자치도",
                "강원특별자치도", "경기도", "전라남도", "경상남도",
                "인천광역시", "대구광역시", "광주광역시", "대전광역시",
                "울산광역시", "세종특별자치시", "전북특별자치도",
                "경상북도", "충청남도", "충청북도"
            ]

        if self.explore_categories is None:
            self.explore_categories = [
                "restaurants", "accommodation", "nature",
                "shopping", "culture", "activity"
            ]

# 전역 설정 인스턴스
config = UnifiedRecommendationConfig()

# 하위 호환성을 위한 별칭들
EXPLORE_REGIONS = config.explore_regions
EXPLORE_CATEGORIES = config.explore_categories
DATABASE_URL = config.database_url