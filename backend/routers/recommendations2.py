# 파일명: recommendation2.py (완성된 개선 버전)

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
import asyncio
import logging
from asyncio import Semaphore

# 통합된 임포트 (backend 환경에 맞게 수정)
try:
    # backend 환경에서의 임포트
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

    from vectorization2 import get_engine, close_engine
    from auth_utils import get_current_user_optional
    from recommendation_config import EXPLORE_REGIONS, EXPLORE_CATEGORIES, config
except ImportError:
    try:
        # 상대 임포트 시도
        from ..vectorization2 import get_engine, close_engine
        from ..auth_utils import get_current_user_optional
        from ..recommendation_config import EXPLORE_REGIONS, EXPLORE_CATEGORIES, config
    except ImportError:
        # 개발용 Mock
        async def get_engine():
            return None
        async def close_engine():
            pass
        def get_current_user_optional():
            return None
        EXPLORE_REGIONS = ["서울특별시", "부산광역시"]
        EXPLORE_CATEGORIES = ["restaurants", "accommodation"]
        config = None

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)

# 리소스 제한 설정 (통합 설정 사용)
MAX_PARALLEL_REQUESTS = config.max_parallel_requests if config else 8
RECOMMENDATION_TIMEOUT = config.recommendation_timeout if config else 3.0

# 병렬 요청 제한 (벡터화 엔진의 DB 풀 보호)
REQUEST_SEMAPHORE = Semaphore(MAX_PARALLEL_REQUESTS)


# ============================================================================
# 🔧 안전한 추천 데이터 조회 유틸리티 함수들
# ============================================================================

async def fetch_recommendations_with_fallback(
    user_id: Optional[str],
    region: Optional[str],
    category: Optional[str],
    limit: int,
    fast_mode: bool = False  # 메인 페이지용 고속 모드
) -> List[Dict[str, Any]]:
    """
    안전한 추천 데이터 조회 (통합 엔진 사용)
    """
    async with REQUEST_SEMAPHORE:
        try:
            # 통합 엔진 인스턴스 획득
            engine = await get_engine()

            # 타임아웃과 함께 추천 조회
            result = await asyncio.wait_for(
                engine.get_recommendations(
                    user_id=user_id,
                    region=region,
                    category=category,
                    limit=limit,
                    fast_mode=fast_mode  # fast_mode 전달
                ),
                timeout=RECOMMENDATION_TIMEOUT
            )
            return result if result else []

        except asyncio.TimeoutError:
            logger.warning(f"Timeout for recommendations: user={user_id}, region={region}, category={category}")
            return []
        except Exception as e:
            logger.error(f"Failed to get recommendations: user={user_id}, region={region}, category={category}, error={e}")
            return []


async def fetch_explore_data_parallel(
    user_id: Optional[str],
    regions: List[str],
    categories: List[str],
    fast_mode: bool = True  # explore는 기본적으로 fast_mode
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    탐색 데이터를 병렬로 안전하게 조회
    """
    # 작업 정의 (키-값 매핑으로 순서 보장)
    tasks = {
        f"{region}:{category}": fetch_recommendations_with_fallback(
            user_id=user_id,
            region=region,
            category=category,
            limit=5,  # 성능 개선을 위해 감소
            fast_mode=fast_mode  # fast_mode 전달
        )
        for region in regions
        for category in categories
    }

    logger.info(f"Starting {len(tasks)} parallel recommendation requests")

    # 모든 작업을 병렬 실행 (부분 실패 허용)
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    # 결과를 구조화된 데이터로 변환
    explore_data = {}
    success_count = 0

    for (key, result) in zip(tasks.keys(), results):
        region, category = key.split(':')

        if region not in explore_data:
            explore_data[region] = {}

        # 예외가 발생한 경우 빈 배열로 대체
        if isinstance(result, Exception):
            logger.error(f"Task {key} failed with exception: {result}")
            explore_data[region][category] = []
        else:
            explore_data[region][category] = result
            success_count += 1

    logger.info(f"Completed parallel requests: {success_count}/{len(tasks)} successful")
    return explore_data


# ============================================================================
# 🚀 메인 페이지를 위한 API 엔드포인트들
# ============================================================================

@router.get("/main-feed/personalized", response_model=dict)
async def get_main_personalized_feed(
    current_user=Depends(get_current_user_optional),
    limit: int = Query(21, ge=1, le=50, description="대표 카드 1개 + 목록 20개 (최대 50개)"),
    region: Optional[str] = Query(None, description="지역 필터 (선택사항)")
):
    """
    메인 상단 'For You' 섹션 - 개인화 추천
    - 로그인: 개인화 추천 (지역/카테고리 무관, 균등 가중치 50:50)
    - 비로그인: 인기 추천 (bookmark_cnt 기준)
    """
    try:
        user_id = str(current_user.user_id) if current_user else None

        logger.info(f"Getting personalized feed for user: {user_id}, limit: {limit}")

        # 통합 엔진 호출 (메인 페이지용 fast_mode 적용)
        recommendations = await fetch_recommendations_with_fallback(
            user_id=user_id,
            region=region,  # 지역 필터 적용
            category=None,
            limit=limit,
            fast_mode=True  # 메인 피드는 항상 고속 모드
        )

        if not recommendations:
            return {
                "featured": None,
                "feed": [],
                "message": "추천할 콘텐츠가 없습니다."
            }

        # 응답 데이터에 category 필드 추가
        processed_recommendations = []
        for rec in recommendations:
            processed_rec = dict(rec)  # 딕셔너리 복사
            # table_name을 category로 매핑
            table_name = rec.get('table_name', '')
            category_mapping = {
                'accommodation': 'accommodation',
                'restaurants': 'restaurants',
                'shopping': 'shopping',
                'nature': 'nature',
                'humanities': 'culture',
                'leisure_sports': 'leisure'
            }
            processed_rec['category'] = category_mapping.get(table_name, table_name)
            processed_recommendations.append(processed_rec)

        return {
            "featured": processed_recommendations[0] if processed_recommendations else None,
            "feed": processed_recommendations[1:] if len(processed_recommendations) > 1 else [],
            "total_count": len(processed_recommendations)
        }

    except Exception as e:
        logger.error(f"Error in get_main_personalized_feed: {e}")
        raise HTTPException(
            status_code=500,
            detail="개인화 피드를 조회하는 중 오류가 발생했습니다."
        )


@router.get("/main-feed/explore", response_model=dict)
async def get_main_explore_feed(
    current_user=Depends(get_current_user_optional),
    regions: Optional[List[str]] = Query(None, description="요청할 지역 목록 (미지정시 인기순)"),
    categories: Optional[List[str]] = Query(None, description="요청할 카테고리 목록 (미지정시 인기순)")
):
    """
    메인 하단 '탐색' 섹션 - 동적 인기순 지역별/카테고리별 추천
    - 지역: 북마크 총합 기준 인기순
    - 카테고리: 북마크 총합 기준 인기순
    - 장소: bookmark_cnt 기준 인기순
    """
    try:
        user_id = str(current_user.user_id) if current_user else None

        # 동적 지역/카테고리 순서 결정 (하드코딩 제거)
        if not regions or not categories:
            engine = await get_engine()
            popular_data = await engine.get_popular_regions_and_categories()

            target_regions = regions or popular_data['regions']
            target_categories = categories or popular_data['categories']
        else:
            target_regions = regions
            target_categories = categories

        logger.info(f"Getting explore feed for user: {user_id}")
        logger.info(f"Dynamic regions: {target_regions[:3]}... ({len(target_regions)} total)")
        logger.info(f"Dynamic categories: {target_categories[:3]}... ({len(target_categories)} total)")

        # 성능을 위해 일부 카테고리만 사용, 지역은 모두 포함
        limited_regions = target_regions  # 모든 지역 포함
        limited_categories = target_categories[:6]  # 상위 6개 카테고리 (요청사항 반영)

        # 🚀 Redis 캐시 키 생성
        cache_key = f"explore_feed:{user_id or 'anonymous'}:{':'.join(sorted(limited_regions))}:{':'.join(sorted(limited_categories))}"
        
        # 캐시에서 조회 시도
        from cache_utils import cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"🎯 Cache hit for explore feed: {cache_key}")
            return cached_result

        # 병렬로 제한된 섹션 데이터 조회
        explore_data = await fetch_explore_data_parallel(
            user_id=user_id,
            regions=limited_regions,
            categories=limited_categories
        )

        # 응답에 메타데이터 추가
        total_sections = len(target_regions) * len(target_categories)
        non_empty_sections = sum(
            1 for region_data in explore_data.values()
            for category_data in region_data.values()
            if category_data
        )

        result = {
            "data": explore_data,
            "metadata": {
                "total_sections": total_sections,
                "non_empty_sections": non_empty_sections,
                "regions": target_regions,
                "categories": target_categories,
                "ordering": "dynamic_popularity"  # 동적 인기순 표시
            }
        }

        # 🚀 Redis 캐시에 저장 (10분 TTL)
        cache.set(cache_key, result, expire=600)
        logger.info(f"💾 Cached explore feed: {cache_key}")

        return result

    except Exception as e:
        logger.error(f"Error in get_main_explore_feed: {e}")
        raise HTTPException(
            status_code=500,
            detail="탐색 피드를 조회하는 중 오류가 발생했습니다."
        )


# ============================================================================
# 🔧 개별 섹션 조회 API (지연 로딩 지원)
# ============================================================================

@router.get("/explore/{region}/{category}", response_model=dict)
async def get_explore_section(
    region: str,
    category: str,
    current_user=Depends(get_current_user_optional),
    limit: int = Query(10, ge=1, le=50, description="조회할 아이템 수"),
    offset: int = Query(0, ge=0, description="페이징 오프셋")
):
    """
    특정 지역/카테고리 섹션 데이터 조회 (지연 로딩, 페이징 지원)
    """
    try:
        user_id = str(current_user.user_id) if current_user else None

        logger.info(f"Getting section data: {region}/{category} for user: {user_id}")

        recommendations = await fetch_recommendations_with_fallback(
            user_id=user_id,
            region=region,
            category=category,
            limit=limit + offset,  # offset 만큼 더 조회
            fast_mode=False  # 상세 섭션은 전체 기능 사용
        )

        # 오프셋 적용
        paginated_recommendations = recommendations[offset:offset + limit]

        return {
            "region": region,
            "category": category,
            "data": paginated_recommendations,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": len(recommendations),
                "has_more": len(recommendations) > offset + limit
            }
        }

    except Exception as e:
        logger.error(f"Error in get_explore_section: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"{region}/{category} 섹션을 조회하는 중 오류가 발생했습니다."
        )


# ============================================================================
# 📊 헬스체크 및 상태 확인 API
# ============================================================================

@router.get("/health", response_model=dict)
async def health_check():
    """
    추천 시스템 헬스체크
    """
    try:
        # 간단한 추천 요청으로 시스템 상태 확인
        test_recommendations = await fetch_recommendations_with_fallback(
            user_id=None,
            region=None,
            category=None,
            limit=1,
            fast_mode=True  # 헬스체크는 빠르게
        )

        return {
            "status": "healthy",
            "engine_responsive": True,
            "timestamp": asyncio.get_event_loop().time(),
            "test_result": len(test_recommendations) > 0
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "engine_responsive": False,
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }


# ============================================================================
# 📝 설정 정보 조회 API (디버깅/모니터링용)
# ============================================================================

@router.get("/regions", response_model=dict)
async def get_available_regions():
    """
    추천 시스템에서 사용 가능한 지역 목록 조회
    """
    try:
        engine = await get_engine()
        regions_data = await engine.get_popular_regions_and_categories()

        return {
            "regions": regions_data.get("regions", []),
            "categories": regions_data.get("categories", [])
        }
    except Exception as e:
        logger.error(f"❌ Regions retrieval failed: {e}")
        return {
            "regions": EXPLORE_REGIONS,
            "categories": EXPLORE_CATEGORIES
        }

@router.get("/config", response_model=dict)
async def get_recommendation_config():
    """
    현재 추천 시스템 설정 정보 조회 (개발/운영 모니터링용)
    """
    try:
        engine = await get_engine()
        return {
            "explore_regions": EXPLORE_REGIONS,
            "explore_categories": EXPLORE_CATEGORIES,
            "max_parallel_requests": MAX_PARALLEL_REQUESTS,
            "recommendation_timeout": RECOMMENDATION_TIMEOUT,
            "engine_type": type(engine).__name__,
            "weights": {
                "similarity": config.similarity_weight if config else 0.5,
                "popularity": config.popularity_weight if config else 0.5
            }
        }
    except Exception as e:
        logger.error(f"❌ Config retrieval failed: {e}")
        return {"error": str(e)}