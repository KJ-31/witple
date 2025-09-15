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

    # Connection Pool 설정 (두 시스템 공유)
    min_pool_size: int = 3
    max_pool_size: int = 15  # recommendation2.py(5) + vectorization2.py(10) 통합
    db_timeout: int = 5  # 통일된 타임아웃

    # =============================================================================
    # 🚀 API 설정
    # =============================================================================
    recommendation_timeout: float = 3.0  # API 타임아웃 (통일)
    max_parallel_requests: int = 8  # 병렬 요청 제한 (DB 풀 보호)

    # =============================================================================
    # 🎯 추천 알고리즘 설정
    # =============================================================================
    candidate_limit: int = 500  # 성능 최적화를 위해 2000에서 500으로 감소
    similarity_weight: float = 0.5  # 균등 가중치 (50:50)
    popularity_weight: float = 0.5  # 균등 가중치 (50:50)
    min_similarity_threshold: float = 0.1

    # 액션 가중치
    action_weights: Dict[str, float] = None

    # 선호도 기반 추천 설정
    preference_weights: Dict[str, float] = None
    travel_style_bonuses: Dict[str, Dict[str, float]] = None

    # =============================================================================
    # 📊 성능 및 캐싱 설정
    # =============================================================================
    vector_cache_size: int = 1000
    cache_ttl_seconds: int = 300  # 5분

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
                'region': 0.4,
                'category': 0.3,
                'tag': 0.3,
                'max_tag_score': 10.0,
                'popularity_normalizer': 1000.0  # 인기도 정규화 기준값
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