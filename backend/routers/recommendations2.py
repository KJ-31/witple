# 파일명: recommendation2.py (완성된 개선 버전)

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
import asyncio
import logging
from asyncio import Semaphore
import hashlib
import json

# 통합된 임포트 (backend 환경에 맞게 수정)
try:
    # backend 환경에서의 임포트
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

    from vectorization2 import get_engine, close_engine
    from auth_utils import get_current_user_optional
    from recommendation_config import EXPLORE_REGIONS, EXPLORE_CATEGORIES, config
    from cache_utils import cache, cached  # Redis 캐싱 유틸리티 추가
except ImportError:
    try:
        # 상대 임포트 시도
        from ..vectorization2 import get_engine, close_engine
        from ..auth_utils import get_current_user_optional
        from ..recommendation_config import EXPLORE_REGIONS, EXPLORE_CATEGORIES, config
        from ..cache_utils import cache, cached  # Redis 캐싱 유틸리티 추가
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
        
        # Mock cache
        class MockCache:
            def get(self, key): return None
            def set(self, key, value, expire=None): return True
        cache = MockCache()
        def cached(expire=300, key_prefix=""):
            def decorator(func):
                return func
            return decorator

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
# 🔧 Redis 캐싱 유틸리티 함수들
# ============================================================================

def generate_cache_key(prefix: str, user_id: Optional[str], region: Optional[str], 
                      category: Optional[str], limit: int, **kwargs) -> str:
    """
    캐시 키 생성 함수 (사용자 우선순위 태그 포함) - 개선된 버전
    """
    # 사용자별로 다른 캐시를 사용 (개인화 추천)
    user_part = f"user_{user_id}" if user_id else "anonymous"
    
    # 우선순위 태그 추출 (캐시 키에 반드시 포함)
    priority_tag = kwargs.get('priority_tag', 'none')
    
    # 파라미터들을 정렬된 문자열로 변환 (우선순위 태그 포함)
    params = {
        'region': region or 'all',
        'category': category or 'all',
        'limit': limit,
        'priority_tag': priority_tag  # 🔑 핵심: 우선순위 태그를 캐시 키에 포함
    }
    
    # 다른 kwargs도 추가 (fast_mode, exclude_names 등)
    for key, value in kwargs.items():
        if key != 'priority_tag':  # 이미 추가됨
            params[key] = str(value) if value is not None else 'none'
    
    # 안정적인 해시 생성을 위해 정렬
    param_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    
    # MD5 해시로 긴 키를 줄임
    hash_obj = hashlib.md5(param_str.encode())
    param_hash = hash_obj.hexdigest()[:8]
    
    return f"{prefix}:{user_part}:{priority_tag}:{param_hash}"

def get_recommendations_cache(cache_key: str) -> Optional[List[Dict[str, Any]]]:
    """캐시에서 추천 데이터 조회 (복원됨)"""
    try:
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ Cache hit: {cache_key}")
            return cached_data
        logger.debug(f"🔍 Cache miss: {cache_key}")
        return None
    except Exception as e:
        logger.error(f"❌ Cache get error: {e}")
        return None

def set_recommendations_cache(cache_key: str, data: List[Dict[str, Any]], expire: int = 900) -> bool:
    """캐시에 추천 데이터 저장 (기본 15분) - 복원됨"""
    try:
        success = cache.set(cache_key, data, expire=expire)
        if success:
            logger.info(f"💾 Cache set: {cache_key} (expire: {expire}s)")
        return success
    except Exception as e:
        logger.error(f"❌ Cache set error: {e}")
        return False


# ============================================================================
# 🔧 안전한 추천 데이터 조회 유틸리티 함수들 (캐싱 적용)
# ============================================================================

async def fetch_recommendations_with_fallback(
    user_id: Optional[str],
    region: Optional[str],
    category: Optional[str],
    limit: int,
    fast_mode: bool = False,  # 메인 페이지용 고속 모드
    priority_tag: Optional[str] = None  # 사용자 우선순위 태그
) -> List[Dict[str, Any]]:
    """
    안전한 추천 데이터 조회 (통합 엔진 사용) - Redis 캐싱 적용
    """
    # 캐시 키 생성 (우선순위 태그 포함)
    cache_key = generate_cache_key(
        prefix="rec_main",
        user_id=user_id,
        region=region,
        category=category,
        limit=limit,
        fast_mode=fast_mode,
        priority_tag=priority_tag or "none"
    )
    
    # 캐시에서 조회 시도 (복원됨)
    cached_result = get_recommendations_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
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
            
            # 결과가 있으면 캐시에 저장 (메인페이지는 1시간, 일반은 15분) - 복원됨
            if result:
                expire_time = 3600 if fast_mode else 900  # 1시간 or 15분
                set_recommendations_cache(cache_key, result, expire=expire_time)
            
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
    fast_mode: bool = True,  # explore는 기본적으로 fast_mode
    priority_tag: Optional[str] = None  # 사용자 우선순위 태그
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
            fast_mode=fast_mode,  # fast_mode 전달
            priority_tag=priority_tag or "none"
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
    메인 상단 'For You' 섹션 - 개인화 추천 (Redis 캐싱 적용)
    - 로그인: 개인화 추천 (지역/카테고리 무관, 균등 가중치 50:50)
    - 비로그인: 인기 추천 (bookmark_cnt 기준)
    """
    try:
        user_id = str(current_user.user_id) if current_user else None

        # priority_tag 가져오기 (캐시 키에 포함하기 위해 먼저 조회)
        user_priority_tag = "none"
        if user_id:
            try:
                engine = await get_engine()
                priority = await engine.get_user_priority_tag(user_id)
                user_priority_tag = priority or "none"
            except Exception as e:
                logger.warning(f"Failed to get user priority for cache key: {e}")

        # 전체 응답 캐싱을 위한 캐시 키 생성 (우선순위 태그 포함)
        response_cache_key = generate_cache_key(
            prefix="main_personalized",
            user_id=user_id,
            region=region,
            category=None,
            limit=limit,
            priority_tag=user_priority_tag  # 우선순위 태그 추가
        )
        
        # 캐시된 응답 조회 (복원됨)
        cached_response = cache.get(response_cache_key)
        if cached_response is not None:
            logger.info(f"🚀 Main personalized feed cache hit: {response_cache_key}")
            return cached_response

        # user_priority_tag는 이미 위에서 조회됨

        logger.info(f"🔍 Getting personalized feed for user: {user_id}, priority_tag: {user_priority_tag}, limit: {limit}")
        print(f"🔍 DEBUG: user_id={user_id}, priority_tag={user_priority_tag}")

        # experience 사용자는 별도 처리 (폴백 포함)
        if user_priority_tag == "experience":
            logger.info(f"🎯 Processing experience user with fallback")
            # 먼저 개인화 추천 시도
            recommendations = await fetch_recommendations_with_fallback(
                user_id=user_id,
                region=region,
                category=None,
                limit=limit,
                fast_mode=True,
                priority_tag=user_priority_tag
            )
            # 개인화 추천이 실패하면 experience 카테고리의 인기 추천으로 폴백
            if not recommendations:
                logger.info(f"🎯 Fallback to popular experience recommendations")
                # experience 카테고리별로 인기 추천 가져오기
                experience_recommendations = []
                experience_categories = ["nature", "humanities", "leisure_sports"]
                for category in experience_categories:
                    category_recs = await fetch_recommendations_with_fallback(
                        user_id=None,  # 인기 추천을 위해 None
                        region=None,
                        category=category,
                        limit=limit // len(experience_categories) + 2,
                        fast_mode=True,
                        priority_tag="none"  # 인기 추천이므로 우선순위 태그 없음
                    )
                    if category_recs:
                        experience_recommendations.extend(category_recs)

                # 점수순으로 정렬하고 제한
                if experience_recommendations:
                    experience_recommendations.sort(key=lambda x: x.get('final_score', 0), reverse=True)
                    recommendations = experience_recommendations[:limit]
                    logger.info(f"🎯 Fallback returned {len(recommendations)} experience recommendations")
        else:
            # 일반 사용자는 기존 로직
            recommendations = await fetch_recommendations_with_fallback(
                user_id=user_id,
                region=region,  # 지역 필터 적용
                category=None,
                limit=limit,
                fast_mode=True,  # 메인 피드는 항상 고속 모드
                priority_tag=user_priority_tag
            )

        logger.info(f"🔍 Initial recommendations count: {len(recommendations) if recommendations else 0}")

        if not recommendations:
            return {
                "featured": None,
                "feed": [],
                "message": "추천할 콘텐츠가 없습니다."
            }

        # 체험 우선순위 사용자에게는 체험 관련 카테고리만 필터링
        if user_priority_tag == "experience":
            experience_categories = ["nature", "humanities", "leisure_sports"]
            logger.info(f"🎯 Experience user - filtering to experience categories: {experience_categories}")
            recommendations = [
                rec for rec in recommendations
                if rec.get('table_name') in experience_categories
            ]
            logger.info(f"🎯 Filtered recommendations count: {len(recommendations)}")

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

        # 응답 데이터 구성
        response_data = {
            "featured": processed_recommendations[0] if processed_recommendations else None,
            "feed": processed_recommendations[1:] if len(processed_recommendations) > 1 else [],
            "total_count": len(processed_recommendations)
        }
        
        # 결과를 캐시에 저장 (1시간 캐싱) - 복원됨
        cache.set(response_cache_key, response_data, expire=3600)
        logger.info(f"🚀 Main personalized feed cached: {response_cache_key}")
        
        return response_data

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
    메인 하단 '탐색' 섹션 - 동적 인기순 지역별/카테고리별 추천 (Redis 캐싱 적용)
    - 지역: 북마크 총합 기준 인기순
    - 카테고리: 북마크 총합 기준 인기순
    - 장소: bookmark_cnt 기준 인기순
    """
    try:
        user_id = str(current_user.user_id) if current_user else None

        # 전체 응답 캐싱을 위한 캐시 키 생성
        regions_str = ",".join(sorted(regions)) if regions else "default"
        categories_str = ",".join(sorted(categories)) if categories else "default"
        
        explore_cache_key = generate_cache_key(
            prefix="main_explore",
            user_id=user_id,
            region=regions_str,
            category=categories_str,
            limit=50,  # 기본 limit
            regions_count=len(regions) if regions else 0,
            categories_count=len(categories) if categories else 0
        )
        
        # 캐시된 응답 조회 (복원됨)
        cached_response = cache.get(explore_cache_key)
        if cached_response is not None:
            logger.info(f"🚀 Main explore feed cache hit: {explore_cache_key}")
            return cached_response

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

        # 🔑 사용자 우선순위 태그 조회 (카테고리 필터링용)
        user_priority_tag = "none"
        if user_id:
            try:
                engine = await get_engine()
                priority = await engine.get_user_priority_tag(user_id)
                user_priority_tag = priority or "none"
            except Exception as e:
                logger.warning(f"Failed to get user priority for cache key: {e}")

        # 성능을 위해 일부 카테고리만 사용, 지역은 모두 포함
        limited_regions = target_regions  # 모든 지역 포함

        # 체험 우선순위 사용자에게는 체험 관련 카테고리만 제공
        if user_priority_tag == "experience":
            limited_categories = ["nature", "humanities", "leisure_sports"]
            logger.info(f"🎯 Experience user - showing only experience categories: {limited_categories}")
        else:
            limited_categories = target_categories[:6]  # 상위 6개 카테고리 (요청사항 반영)

        # 🚀 Redis 캐시 키 생성 (우선순위 태그 포함) - v3 (체험 우선순위 필터링 수정)
        cache_key = f"explore_feed_v3:{user_id or 'anonymous'}:{user_priority_tag}:{':'.join(sorted(limited_regions))}:{':'.join(sorted(limited_categories))}"

        logger.info(f"🔑 Cache key generated: {cache_key}")

        # 캐시에서 조회 시도 (주석처리)
        # from cache_utils import cache
        # cached_result = cache.get(cache_key)
        # if cached_result is not None:
        #     logger.info(f"🎯 Cache hit for explore feed: {cache_key}")
        #     return cached_result
        # else:
        #     logger.info(f"🔍 Cache miss for explore feed: {cache_key}")

        # 병렬로 제한된 섹션 데이터 조회
        explore_data = await fetch_explore_data_parallel(
            user_id=user_id,
            regions=limited_regions,
            categories=limited_categories,
            priority_tag=user_priority_tag
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

        # 🚀 응답을 새로운 캐시 키로 저장 (1시간 TTL - 메인페이지용 최적화) - 복원됨
        cache.set(explore_cache_key, result, expire=3600)
        logger.info(f"🚀 Main explore feed cached: {explore_cache_key}")

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
    offset: int = Query(0, ge=0, description="페이징 오프셋"),
    exclude_place_names: Optional[str] = Query(None, description="제외할 장소 이름들 (쉼표로 구분)")
):
    """
    특정 지역/카테고리 섹션 데이터 조회 (우선순위 태그 기반 필터링, 지연 로딩, 페이징 지원) - Redis 캐싱 적용
    """
    try:
        user_id = str(current_user.user_id) if current_user else None

        # 개별 섹션 캐시 키 생성
        section_cache_key = generate_cache_key(
            prefix="explore_section",
            user_id=user_id,
            region=region,
            category=category,
            limit=limit,
            offset=offset
        )
        
        # 캐시된 응답 조회 (복원됨)
        cached_section = cache.get(section_cache_key)
        if cached_section is not None:
            logger.info(f"🚀 Explore section cache hit: {section_cache_key}")
            return cached_section

        logger.info(f"Getting section data: {region}/{category} for user: {user_id}")

        # 🎯 로그인된 사용자의 경우 우선순위 태그 기반으로 카테고리 결정 (안전한 처리)
        target_category = category
        user_priority = None  # 기본값 설정
        if current_user and user_id:
            try:
                engine = await get_engine()

                # 사용자 우선순위 태그 조회 (추가 보호)
                try:
                    user_priority = await asyncio.wait_for(
                        engine.get_user_priority_tag(user_id),
                        timeout=2.0  # 2초 타임아웃
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout getting user priority for {user_id}")
                    user_priority = None
                except Exception as priority_e:
                    logger.warning(f"Error getting user priority for {user_id}: {priority_e}")
                    user_priority = None

                if user_priority:
                    logger.info(f"User {user_id} priority tag: {user_priority}")

                    # 우선순위 태그에 따른 카테고리 매핑
                    priority_category_map = {
                        'accommodation': 'accommodation',
                        'restaurants': 'restaurants',
                        'shopping': 'shopping',
                        'experience': category  # 체험은 요청된 카테고리 그대로 사용
                    }

                    # 체험 태그인 경우 nature/humanities/leisure_sports 중에서만 허용
                    if user_priority == 'experience':
                        experience_categories = ['nature', 'humanities', 'leisure_sports']
                        if category in experience_categories:
                            target_category = category
                        else:
                            # 요청된 카테고리가 체험 카테고리가 아니면 nature로 기본 설정
                            target_category = 'nature'
                    else:
                        # 다른 우선순위 태그의 경우 해당 카테고리로 고정
                        if user_priority in priority_category_map:
                            target_category = priority_category_map[user_priority]

                    logger.info(f"Target category for region {region}: {target_category} (based on priority: {user_priority})")
                else:
                    logger.info(f"No priority tag found for user {user_id}, using original category: {category}")

            except Exception as e:
                logger.error(f"Failed to process user priority for {user_id}: {e}")
                # 실패 시 원래 카테고리 사용
                target_category = category

        # 제외할 장소 이름들 파싱
        excluded_names = set()
        if exclude_place_names:
            excluded_names = {name.strip().lower() for name in exclude_place_names.split(',') if name.strip()}
            logger.info(f"🚫 제외할 장소 {len(excluded_names)}개: {list(excluded_names)[:3]}...")

        # 추천 조회 (추가 타임아웃 보호) - 중복 제거를 위해 더 많이 조회
        extra_limit = len(excluded_names) * 2 + 5  # 제외될 장소들을 고려해서 더 많이 조회
        try:
            recommendations = await asyncio.wait_for(
                fetch_recommendations_with_fallback(
                    user_id=user_id,
                    region=region,
                    category=target_category,
                    limit=limit + offset + extra_limit,  # 중복 제거를 위해 더 많이 조회
                    fast_mode=False,  # 상세 섭션은 전체 기능 사용
                    priority_tag=user_priority or "none"
                ),
                timeout=10.0  # 10초 타임아웃
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout getting recommendations for {region}/{target_category}")
            recommendations = []
        except Exception as rec_e:
            logger.error(f"Error getting recommendations for {region}/{target_category}: {rec_e}")
            recommendations = []

        # 중복 제거: 제외할 장소 이름들 필터링
        if excluded_names and recommendations:
            original_count = len(recommendations)
            recommendations = [
                rec for rec in recommendations 
                if rec.get('name', '').strip().lower() not in excluded_names
            ]
            filtered_count = len(recommendations)
            if filtered_count < original_count:
                logger.info(f"✅ 중복 제거: {original_count}개 → {filtered_count}개 (제거: {original_count - filtered_count}개)")

        # 오프셋 적용
        paginated_recommendations = recommendations[offset:offset + limit]

        # 응답 데이터 구성
        section_response = {
            "region": region,
            "category": target_category,  # 실제 사용된 카테고리 반환
            "original_category": category,  # 원래 요청된 카테고리
            "data": paginated_recommendations,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": len(recommendations),
                "has_more": len(recommendations) > offset + limit
            },
            "success": True,
            "message": f"Found {len(paginated_recommendations)} recommendations"
        }
        
        # 결과를 캐시에 저장 (개별 섹션은 15분 캐싱) - 복원됨
        cache.set(section_cache_key, section_response, expire=900)
        logger.info(f"🚀 Explore section cached: {section_cache_key}")
        
        return section_response

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
    추천 시스템 헬스체크 (캐시 상태 포함)
    """
    try:
        # 캐시 상태 확인
        cache_status = "healthy"
        cache_info = {"cached_keys": 0}
        try:
            # 테스트 캐시 쓰기/읽기 (복원됨)
            test_key = "health_check_test"
            test_value = {"status": "ok", "timestamp": asyncio.get_event_loop().time()}
            cache.set(test_key, test_value, expire=60)
            read_value = cache.get(test_key)
            
            if read_value and read_value.get("status") == "ok":
                cache_status = "healthy"
                # Redis 캐시 키 개수 확인
                try:
                    if hasattr(cache, 'redis'):
                        rec_keys = len(cache.redis.keys("rec_*"))
                        main_keys = len(cache.redis.keys("main_*"))
                        explore_keys = len(cache.redis.keys("explore_*"))
                        cache_info = {
                            "rec_keys": rec_keys,
                            "main_keys": main_keys,
                            "explore_keys": explore_keys,
                            "total_rec_cache": rec_keys + main_keys + explore_keys
                        }
                except Exception:
                    cache_info["note"] = "키 개수 확인 불가"
                    
            else:
                cache_status = "write/read error"
        except Exception as e:
            cache_status = f"error: {str(e)[:50]}"

        # 간단한 추천 요청으로 시스템 상태 확인 (캐시 효과 확인)
        import time
        start_time = time.time()
        test_recommendations = await fetch_recommendations_with_fallback(
            user_id=None,
            region=None,
            category=None,
            limit=1,
            fast_mode=True,  # 헬스체크는 빠르게
            priority_tag="none"
        )
        response_time = round((time.time() - start_time) * 1000, 1)  # ms

        return {
            "status": "healthy",
            "engine_responsive": True,
            "cache_status": cache_status,
            "cache_info": cache_info,
            "test_response_time_ms": response_time,
            "cache_working": response_time < 100,  # 100ms 이하면 캐시에서 응답
            "timestamp": asyncio.get_event_loop().time(),
            "test_result": len(test_recommendations) > 0,
            "recommendations_count": len(test_recommendations)
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "engine_responsive": False,
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }


@router.delete("/cache/clear")
async def clear_cache():
    """추천 캐시 삭제 (복원됨)"""
    try:
        cleared = 0
        if hasattr(cache, 'redis'):
            for pattern in ["rec_*", "main_*", "explore_*"]:
                keys = cache.redis.keys(pattern)
                if keys:
                    cleared += cache.redis.delete(*keys)
        logger.info(f"🗑️ Cache cleared: {cleared} keys deleted")
        return {"cleared_keys": cleared, "message": f"{cleared}개 캐시 삭제됨"}
    except Exception as e:
        logger.error(f"❌ Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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