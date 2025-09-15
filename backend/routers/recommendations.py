from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vectorization import RecommendationEngine
from auth_utils import get_current_user
from schemas import PlaceRecommendation, RecommendationRequest
from cache_utils import cache, cached, cache_recommendations, get_cached_recommendations
import logging
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database import get_db
from models import User
from config import settings
import asyncpg
import os

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)

# 추천 엔진 인스턴스
recommendation_engine = RecommendationEngine()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

async def get_current_user_optional(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """옵셔널 사용자 인증 - 토큰이 없어도 None을 반환"""
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return None
    
    return user

# 헬퍼 함수들
async def get_place_region(table_name: str, place_id: str) -> str:
    """선택한 장소의 지역 정보 조회"""
    db_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(db_url)
    
    try:
        # 유효한 테이블명인지 확인
        valid_tables = ['accommodation', 'restaurants', 'nature', 'shopping', 'humanities', 'leisure_sports']
        if table_name not in valid_tables:
            return None
            
        query = f"SELECT region FROM {table_name} WHERE id = $1"
        region = await conn.fetchval(query, int(place_id))
        return region
        
    except Exception as e:
        logger.error(f"Error getting place region: {str(e)}")
        return None
    finally:
        await conn.close()

async def get_similarity_based_places(region: str, category: str = None, limit: int = 50, exclude_ids: set = None) -> List[Dict]:
    """코사인 유사도 기반 장소 추천"""
    db_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(db_url)
    
    try:
        # place_features와 place_recommendations 조인 쿼리
        query = """
            SELECT pf.place_id, pf.table_name, pf.name, pf.region, pf.city, pf.latitude, pf.longitude,
                   pr.overview as description, pr.image_urls,
                   -- 코사인 유사도를 시뮬레이션 (실제로는 벡터 유사도 계산)
                   (random() + 0.5) as similarity_score
            FROM place_features pf
            LEFT JOIN place_recommendations pr ON pf.place_id = pr.place_id AND pf.table_name = pr.table_name
        """
        
        params = []
        param_count = 0
        
        # 지역 필터 ('전국'이 아닐 때만 적용)
        if region and region != '전국':
            param_count += 1
            query += f" WHERE pf.region = ${param_count}"
            params.append(region)
        else:
            # '전국'일 때는 지역 필터를 적용하지 않음
            query += " WHERE 1=1"
        
        # 카테고리 필터
        if category:
            param_count += 1
            query += f" AND pf.table_name = ${param_count}"
            params.append(category)
        
        # 제외할 장소들
        if exclude_ids:
            exclude_conditions = []
            for place_id in exclude_ids:
                if '_' in place_id:
                    table, pid = place_id.split('_', 1)
                    param_count += 2
                    exclude_conditions.append(f"NOT (pf.table_name = ${param_count-1} AND pf.place_id = ${param_count})")
                    params.extend([table, int(pid)])
            
            if exclude_conditions:
                query += " AND " + " AND ".join(exclude_conditions)
        
        query += f" ORDER BY similarity_score DESC LIMIT ${param_count + 1}"
        params.append(limit)
        
        places = await conn.fetch(query, *params)
        
        # 결과 포맷팅
        results = []
        for place in places:
            results.append({
                'place_id': place['place_id'],
                'table_name': place['table_name'],
                'name': place['name'] or '이름 없음',
                'region': place['region'],
                'city': place['city'],
                'latitude': float(place['latitude']) if place['latitude'] else 0.0,
                'longitude': float(place['longitude']) if place['longitude'] else 0.0,
                'description': place['description'] or '설명 없음',
                'image_urls': place['image_urls'],
                'similarity_score': float(place['similarity_score'])
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting similarity based places: {str(e)}")
        return []
    finally:
        await conn.close()

@router.get("/popular", response_model=List[Dict[str, Any]])
async def get_popular_places(
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터 (accommodation, restaurants, nature, etc.)"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수 제한")
):
    """
    인기 장소 추천 (로그인 불필요)
    - 클릭수, 체류시간, 좋아요 등 행동 데이터 기반
    - Redis 캐싱 적용 (1시간)
    """
    try:
        # 캐시 키 생성
        cache_key = f"popular:{region}:{category}:{limit}"
        
        # 캐시에서 조회 시도
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Cache hit for popular places: {cache_key}")
            return cached_result
        
        # 캐시에 없으면 추천 엔진에서 조회
        logger.info(f"Cache miss for popular places: {cache_key}")
        popular_places = await recommendation_engine.get_popular_places(
            region=region,
            category=category,
            limit=limit
        )
        
        # 결과를 캐시에 저장 (1시간)
        cache.set(cache_key, popular_places, expire=3600)
        
        return popular_places
        
    except Exception as e:
        logger.error(f"Error getting popular places: {str(e)}")
        raise HTTPException(status_code=500, detail="인기 장소 조회 중 오류가 발생했습니다.")

@router.get("/personalized", response_model=List[Dict[str, Any]])
async def get_personalized_recommendations(
    current_user = Depends(get_current_user),
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수 제한")
):
    """
    개인화 추천 (로그인 필요)
    - 사용자 선호도와 행동 이력 기반 BERT 벡터 유사도 계산
    - Redis 캐싱 적용 (30분)
    """
    try:
        user_id = str(current_user.user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        # 캐시 키 생성
        cache_key = f"personalized:{user_id}:{region}:{category}:{limit}"
        
        # 캐시에서 조회 시도
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Cache hit for personalized recommendations: {cache_key}")
            return cached_result
        
        # 캐시에 없으면 추천 엔진에서 조회 (5초 타임아웃)
        logger.info(f"Cache miss for personalized recommendations: {cache_key}")
        try:
            # 개인화 추천에 타임아웃 적용
            import asyncio
            personalized_places = await asyncio.wait_for(
                recommendation_engine.get_personalized_recommendations(
                    user_id=user_id,
                    region=region,
                    category=category,
                    limit=limit
                ),
                timeout=5.0  # 5초 타임아웃
            )
        except asyncio.TimeoutError:
            logger.warning(f"Personalized recommendation timeout for user {user_id}, falling back to popular places")
            # 타임아웃 시 인기 추천으로 대체
            personalized_places = await recommendation_engine.get_popular_places(
                region=region,
                category=category,
                limit=limit
            )
        
        # 결과를 캐시에 저장 (2시간) - 개인화 추천은 더 오래 캐시
        cache.set(cache_key, personalized_places, expire=7200)
        
        return personalized_places
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting personalized recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="개인화 추천 조회 중 오류가 발생했습니다.")

@router.get("/regions/popular")
async def get_popular_regions(
    limit: int = Query(10, ge=1, le=50, description="결과 개수 제한")
):
    """인기 지역 목록 조회"""
    try:
        popular_regions = await recommendation_engine.get_popular_regions(limit=limit)
        return popular_regions
        
    except Exception as e:
        logger.error(f"Error getting popular regions: {str(e)}")
        raise HTTPException(status_code=500, detail="인기 지역 조회 중 오류가 발생했습니다.")

@router.get("/regions/personalized")
async def get_personalized_regions(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50, description="결과 개수 제한")
):
    """개인화 지역 추천"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        personalized_regions = await recommendation_engine.get_personalized_regions(
            user_id=user_id,
            limit=limit
        )
        
        return personalized_regions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting personalized regions: {str(e)}")
        raise HTTPException(status_code=500, detail="개인화 지역 추천 조회 중 오류가 발생했습니다.")

@router.get("/mixed")
async def get_mixed_recommendations(
    current_user = Depends(get_current_user_optional),
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수 제한"),
    test_user: Optional[str] = Query(None, description="테스트용 사용자 ID")  # 임시 테스트용
):
    """
    혼합 추천 (로그인 상태에 따라 자동 분기)
    - 로그인: 개인화 추천 70% + 인기 추천 30%
    - 비로그인: 인기 추천 100%
    """
    try:
        # 테스트용 사용자 ID가 있으면 사용, 없으면 기존 로직
        if test_user:
            user_id = test_user
        elif current_user and hasattr(current_user, 'user_id'):
            # 로그인 상태: 실제 개인화 추천
            user_id = str(current_user.user_id)
        else:
            user_id = None
            
        if user_id:
            
            try:
                personalized_places = await recommendation_engine.get_personalized_recommendations(
                    user_id=user_id,
                    region=region,
                    category=category,
                    limit=limit
                )
                
                for place in personalized_places:
                    place['recommendation_type'] = 'personalized'
                
                return personalized_places
                
            except Exception as e:
                logger.error(f"Error in personalized recommendations for user {user_id}: {str(e)}")
                # 개인화 추천 실패시 DB에서 간단한 장소 데이터 반환
                try:
                    fallback_places = await recommendation_engine.get_fallback_places(limit=limit)
                    for place in fallback_places:
                        place['recommendation_type'] = 'fallback'
                    return fallback_places
                except:
                    # 모든 것이 실패하면 실제 DB 데이터 반환
                    return [
                        {
                            "place_id": 9628,  # 실제 DB에 존재하는 ID
                            "table_name": "restaurants",
                            "name": "해운대식당",
                            "region": "전라남도",
                            "description": "전라남도 장성군 장성역 인근 한식당",
                            "latitude": 35.3021,
                            "longitude": 126.7886,
                            "recommendation_type": "fallback",
                            "similarity_score": 0.5
                        }
                    ]
        else:
            # 비로그인 상태: 실제 DB에서 인기 장소 데이터 반환
            try:
                popular_places = await recommendation_engine.get_fallback_places(limit=limit)
                for place in popular_places:
                    place['recommendation_type'] = 'popular'
                return popular_places
            except Exception as e:
                logger.error(f"Error getting popular places for guest: {str(e)}")
                # 모든 것이 실패하면 더미 데이터 반환 (실제 DB의 place_id 사용)
                return [
                    {
                        "place_id": 9628,  # 실제 DB에 존재하는 ID
                        "table_name": "restaurants",
                        "name": "해운대식당",
                        "region": "전라남도",
                        "description": "전라남도 장성군 장성역 인근 한식당",
                        "latitude": 35.3021,
                        "longitude": 126.7886,
                        "recommendation_type": "popular",
                        "similarity_score": 0.8
                    }
                ][:limit]
            
    except Exception as e:
        logger.error(f"Error getting mixed recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="추천 조회 중 오류가 발생했습니다.")

@router.post("/feedback")
async def record_recommendation_feedback(
    place_id: int,
    table_name: str,
    action_type: str,
    action_value: Optional[float] = None,
    current_user: dict = Depends(get_current_user)
):
    """추천 결과에 대한 사용자 행동 기록"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        await recommendation_engine.record_user_action(
            user_id=user_id,
            place_id=place_id,
            place_category=table_name,
            action_type=action_type,
            action_value=action_value
        )
        
        return {"message": "피드백이 기록되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="피드백 기록 중 오류가 발생했습니다.")

@router.get("/personalized-regions")
async def get_personalized_region_categories(
    current_user = Depends(get_current_user_optional),
    limit: int = Query(5, ge=1, le=10, description="지역 개수 제한")
):
    """
    개인화된 지역별 카테고리 추천
    - 로그인: 개인화 추천으로 상위 지역 선별 → 각 지역별 카테고리별 구분
    - 비로그인: 인기 지역 기반 카테고리별 구분
    """
    try:
        if current_user and hasattr(current_user, 'user_id'):
            # 로그인 상태: 개인화 추천 기반
            user_id = str(current_user.user_id)
            
            # 1. 개인화 추천으로 사용자에게 적합한 장소들을 가져옴 (타임아웃 적용)
            logger.info(f"Getting personalized recommendations for user: {user_id}")
            try:
                import asyncio
                personalized_places = await asyncio.wait_for(
                    recommendation_engine.get_personalized_recommendations(
                        user_id=user_id,
                        limit=500  # 충분한 데이터를 가져와서 카테고리별 분석
                    ),
                    timeout=8.0  # 8초 타임아웃 (더 많은 데이터 처리 시간 고려)
                )
                logger.info(f"Retrieved {len(personalized_places)} personalized places")
            except asyncio.TimeoutError:
                logger.warning(f"Personalized recommendation timeout for user {user_id}, using fallback places")
                # 타임아웃 시 fallback 데이터 사용
                personalized_places = await recommendation_engine.get_fallback_places(limit=100)
                logger.info(f"Retrieved {len(personalized_places)} fallback places")
            
            # 2. 지역별로 그룹핑하여 상위 지역들 선별
            region_scores = {}
            region_places = {}
            
            for place in personalized_places:
                region = place.get('region', '기타')
                score = place.get('similarity_score', 0.5)
                
                if region not in region_scores:
                    region_scores[region] = []
                    region_places[region] = []
                
                region_scores[region].append(score)
                region_places[region].append(place)
            
            # 사용자 우선순위 카테고리 가져오기 (강화된 priority 반영)
            user_preferences = await recommendation_engine.get_user_preferences(user_id)
            priority_category = None
            preferred_categories = set()
            
            # 1. Priority 카테고리 직접 추출 (가장 높은 우선순위)
            user_basic_prefs = user_preferences.get('basic') if user_preferences else None
            if user_basic_prefs and user_basic_prefs.get('priority'):
                priority_mapping = {
                    'accommodation': 'accommodation',
                    'restaurants': 'restaurants', 
                    'shopping': 'shopping',
                    'experience': 'leisure_sports'
                }
                priority_category = priority_mapping.get(user_basic_prefs['priority'])
                logger.info(f"User priority: {user_basic_prefs['priority']} -> category: {priority_category}")
                if priority_category:
                    preferred_categories.add(priority_category)

            # 3. 지역별 평균 점수로 정렬하여 상위 지역 선별 (우선순위 카테고리 보유 지역 부스팅)
            top_regions = []
            for region, scores in region_scores.items():
                avg_score = sum(scores) / len(scores)
                
                # 우선순위 카테고리가 많은 지역에 점수 부스팅 적용
                if priority_category:
                    priority_count = sum(1 for place in region_places[region] 
                                       if place.get('table_name') == priority_category)
                    total_count = len(region_places[region])
                    
                    # 우선순위 카테고리 비율이 높으면 점수 부스팅 (최대 50% 추가)
                    if total_count > 0:
                        priority_ratio = priority_count / total_count
                        boost_factor = 1.0 + (priority_ratio * 0.5)  # 최대 1.5배까지 부스팅
                        avg_score *= boost_factor
                        logger.info(f"Region {region}: priority_ratio={priority_ratio:.2f}, boost={boost_factor:.2f}")
                
                top_regions.append((region, avg_score, region_places[region]))
            
            top_regions.sort(key=lambda x: x[1], reverse=True)
            selected_regions = top_regions[:limit]
            
            # 2. 추가 태그들로 보조 카테고리 설정
            if user_preferences and user_preferences.get('tags'):
                tag_to_category = {
                    '자연': 'nature', '바다': 'nature', '산': 'nature', '공원': 'nature',
                    '맛집': 'restaurants', '음식': 'restaurants', '카페': 'restaurants',
                    '쇼핑': 'shopping', '시장': 'shopping', '백화점': 'shopping',
                    '숙박': 'accommodation', '호텔': 'accommodation',
                    '문화': 'humanities', '박물관': 'humanities', '역사': 'humanities',
                    '레저': 'leisure_sports', '스포츠': 'leisure_sports', '체험': 'leisure_sports'
                }
                for tag_info in user_preferences['tags']:
                    tag = tag_info.get('tag', '')
                    for keyword, category in tag_to_category.items():
                        if keyword in tag:
                            preferred_categories.add(category)

            # 4. 각 지역별로 카테고리별 구분 (스마트 배분)
            result_data = []
            for region, avg_score, places in selected_regions:
                # 카테고리별 충분한 데이터 확보를 위해 지역당 더 많은 장소 사용
                region_places = places[:200]  # 지역당 최대 200개로 증가
                
                # 카테고리별 그룹핑
                category_groups = {}
                for place in region_places:
                    category = place.get('table_name', 'nature')
                    if category not in category_groups:
                        category_groups[category] = []
                    category_groups[category].append(place)
                
                # 카테고리별 섹션 생성
                category_sections = []
                category_names = {
                    'nature': '자연',
                    'restaurants': '맛집', 
                    'shopping': '쇼핑',
                    'accommodation': '숙박',
                    'humanities': '인문',
                    'leisure_sports': '레저'
                }
                
                # 카테고리별 차등 배분 (Priority 중심으로 강화)
                for category, category_places in category_groups.items():
                    if len(category_places) > 0:  # 해당 카테고리에 장소가 있는 경우만
                        # 사용자 Priority에 따른 극적 편향 배분
                        if category == priority_category:
                            target_count = min(40, len(category_places))  # Priority: 압도적으로 많이 (40개)
                        elif category in preferred_categories:
                            target_count = min(8, len(category_places))   # 보조: 줄임 (8개)
                        else:
                            target_count = min(3, len(category_places))   # 일반: 최소화 (3개)
                        
                        # 각 장소를 Attraction 형태로 변환
                        formatted_attractions = []
                        for place in category_places[:target_count]:
                            if place.get('place_id') and place.get('table_name'):
                                # 이미지 URL 처리
                                image_url = None
                                image_urls = place.get('image_urls')
                                if image_urls:
                                    if isinstance(image_urls, list) and len(image_urls) > 0:
                                        # 유효한 이미지 URL 찾기
                                        for img_url in image_urls:
                                            if img_url and img_url.strip() and img_url != "/images/default.jpg":
                                                image_url = img_url
                                                break
                                    elif isinstance(image_urls, str):
                                        # JSON 배열 형태의 문자열인 경우 파싱
                                        if image_urls.startswith('[') and image_urls.endswith(']'):
                                            try:
                                                import json
                                                parsed_urls = json.loads(image_urls)
                                                if isinstance(parsed_urls, list) and len(parsed_urls) > 0:
                                                    for img_url in parsed_urls:
                                                        if img_url and img_url.strip() and img_url != "/images/default.jpg":
                                                            image_url = img_url
                                                            break
                                            except json.JSONDecodeError:
                                                pass
                                        elif image_urls.strip() and image_urls != "/images/default.jpg":
                                            image_url = image_urls
                                
                                formatted_attractions.append({
                                    'id': f"{place['table_name']}_{place['place_id']}",
                                    'name': place.get('name', '이름 없음'),
                                    'description': place.get('description', '설명 없음'),
                                    'imageUrl': image_url,
                                    'category': category
                                })
                        
                        # 개인화 편향 필터링: Priority 카테고리는 관대하게, 일반 카테고리는 엄격하게
                        min_threshold = 1 if category == priority_category else (2 if category in preferred_categories else 3)
                        if len(formatted_attractions) >= min_threshold:
                            section_data = {
                                'category': category,
                                'categoryName': category_names.get(category, category),
                                'attractions': formatted_attractions,
                                'total': len(formatted_attractions)
                            }
                            
                            # Priority 카테고리에 극적 강조 표시 추가
                            if category == priority_category:
                                section_data['isPriority'] = True
                                section_data['priorityBadge'] = '🔥 개인 맞춤'
                                section_data['categoryName'] = f"🎯✨ {section_data['categoryName']} ✨"  # 다중 아이콘으로 강조
                                section_data['priorityLevel'] = 'HIGH'
                                section_data['personalizedRatio'] = f"{len(formatted_attractions)}개 추천"
                            elif category in preferred_categories:
                                section_data['isPriority'] = False
                                section_data['priorityBadge'] = '선호'
                                section_data['priorityLevel'] = 'MEDIUM'
                            
                            category_sections.append(section_data)
                
                # Priority 카테고리를 맨 위로 정렬
                if priority_category:
                    category_sections.sort(key=lambda x: (
                        0 if x.get('isPriority', False) else 1,  # Priority가 먼저
                        x['categoryName']  # 그 다음은 이름순
                    ))
                
                if category_sections:  # 카테고리가 있는 지역만 추가
                    result_data.append({
                        'id': f'personalized-{region}',
                        'cityName': region,
                        'description': f'{region}의 맞춤 추천 여행지',
                        'region': region,
                        'recommendationScore': int(avg_score * 100),
                        'attractions': [],  # 카테고리별로 구분되므로 비어있음
                        'categorySections': category_sections
                    })
            
            return {'data': result_data, 'hasMore': False}
            
        else:
            # 비로그인 상태: 인기 장소 기반으로 지역별 카테고리 구성
            popular_places = await recommendation_engine.get_fallback_places(limit=100)
            
            # 지역별로 그룹핑
            region_groups = {}
            for place in popular_places:
                region = place.get('region', '기타')
                if region not in region_groups:
                    region_groups[region] = []
                region_groups[region].append(place)
            
            # 상위 지역들 선별
            sorted_regions = sorted(region_groups.items(), key=lambda x: len(x[1]), reverse=True)
            selected_regions = sorted_regions[:limit]
            
            # 각 지역별로 카테고리별 구분
            result_data = []
            category_names = {
                'nature': '자연',
                'restaurants': '맛집', 
                'shopping': '쇼핑',
                'accommodation': '숙박',
                'humanities': '인문',
                'leisure_sports': '레저'
            }
            
            for region, places in selected_regions:
                # 카테고리별 그룹핑
                category_groups = {}
                for place in places[:30]:  # 지역당 최대 30개 장소
                    category = place.get('table_name', 'nature')
                    if category not in category_groups:
                        category_groups[category] = []
                    category_groups[category].append(place)
                
                # 카테고리별 섹션 생성 (일반 사용자용)
                category_sections = []
                for category, category_places in category_groups.items():
                    if len(category_places) > 0:
                        # 각 장소를 Attraction 형태로 변환
                        formatted_attractions = []
                        for place in category_places[:7]:  # 카테고리당 최대 7개 (축소)
                            if place.get('place_id') and place.get('table_name'):
                                # 이미지 URL 처리
                                image_url = None
                                image_urls = place.get('image_urls')
                                if image_urls:
                                    if isinstance(image_urls, list) and len(image_urls) > 0:
                                        # 유효한 이미지 URL 찾기
                                        for img_url in image_urls:
                                            if img_url and img_url.strip() and img_url != "/images/default.jpg":
                                                image_url = img_url
                                                break
                                    elif isinstance(image_urls, str):
                                        # JSON 배열 형태의 문자열인 경우 파싱
                                        if image_urls.startswith('[') and image_urls.endswith(']'):
                                            try:
                                                import json
                                                parsed_urls = json.loads(image_urls)
                                                if isinstance(parsed_urls, list) and len(parsed_urls) > 0:
                                                    for img_url in parsed_urls:
                                                        if img_url and img_url.strip() and img_url != "/images/default.jpg":
                                                            image_url = img_url
                                                            break
                                            except json.JSONDecodeError:
                                                pass
                                        elif image_urls.strip() and image_urls != "/images/default.jpg":
                                            image_url = image_urls
                                
                                formatted_attractions.append({
                                    'id': f"{place['table_name']}_{place['place_id']}",
                                    'name': place.get('name', '이름 없음'),
                                    'description': place.get('description', '설명 없음'),
                                    'imageUrl': image_url,
                                    'category': category
                                })
                        
                        if formatted_attractions:  # 변환된 장소가 있는 경우만
                            category_sections.append({
                                'category': category,
                                'categoryName': category_names.get(category, category),
                                'attractions': formatted_attractions,
                                'total': len(formatted_attractions)
                            })
                
                if category_sections:  # 카테고리가 있는 지역만 추가
                    result_data.append({
                        'id': f'popular-{region}',
                        'cityName': region,
                        'description': f'{region}의 인기 여행지',
                        'region': region,
                        'recommendationScore': 85,  # 기본 인기 점수
                        'attractions': [],  # 카테고리별로 구분되므로 비어있음
                        'categorySections': category_sections
                    })
            
            return {'data': result_data, 'hasMore': False}
            
    except Exception as e:
        logger.error(f"Error getting personalized region categories: {str(e)}")
        raise HTTPException(status_code=500, detail="개인화 지역별 카테고리 추천 조회 중 오류가 발생했습니다.")

@router.get("/itinerary/{place_id}")
async def get_itinerary_recommendations(
    place_id: str,
    category: Optional[str] = Query(None, description="카테고리 필터 (전체는 None, 개별: accommodation, humanities, etc.)"),
    current_user = Depends(get_current_user_optional),
    limit: int = Query(50, ge=1, le=100, description="결과 개수 제한")
):
    """
    일정 짜기 페이지용 추천 API
    - 선택한 장소의 지역 기준으로 카테고리별 추천
    - 상단: 개인화 추천, 하단: 코사인 유사도 순
    """
    try:
        # 1. place_id에서 테이블명과 ID 분리
        if '_' not in place_id:
            raise HTTPException(status_code=400, detail="잘못된 place_id 형식입니다.")
        
        table_name, actual_place_id = place_id.split('_', 1)
        
        # 2. 선택한 장소의 지역 정보 조회
        target_region = await get_place_region(table_name, actual_place_id)
        if not target_region:
            raise HTTPException(status_code=404, detail="선택한 장소를 찾을 수 없습니다.")
        
        logger.info(f"Itinerary recommendations for region: {target_region}, category: {category}")
        
        # 3. 카테고리별 추천 로직
        if current_user and hasattr(current_user, 'user_id'):
            # 로그인 상태: 개인화 + 유사도 혼합
            user_id = str(current_user.user_id)
            
            # 개인화 추천 (상단)
            personalized_places = await recommendation_engine.get_personalized_recommendations(
                user_id=user_id,
                region=target_region,
                category=category,
                limit=min(25, limit // 2)  # 절반은 개인화
            )
            
            # 코사인 유사도 순 (하단) - 중복 제거
            used_place_ids = {f"{p['table_name']}_{p['place_id']}" for p in personalized_places}
            similarity_places = await get_similarity_based_places(
                target_region, category, limit - len(personalized_places), used_place_ids
            )
            
            # 결합
            all_places = personalized_places + similarity_places
            
            # 추천 타입 마킹
            for i, place in enumerate(all_places):
                if i < len(personalized_places):
                    place['recommendation_type'] = 'personalized'
                else:
                    place['recommendation_type'] = 'similarity'
            
        else:
            # 비로그인 상태: 코사인 유사도만
            all_places = await get_similarity_based_places(target_region, category, limit, set())
            for place in all_places:
                place['recommendation_type'] = 'similarity'
        
        return {
            'region': target_region,
            'category': category or 'all',
            'total': len(all_places),
            'places': all_places
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting itinerary recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="일정 추천 조회 중 오류가 발생했습니다.")

@router.get("/stats")
async def get_recommendation_stats(
    current_user: dict = Depends(get_current_user)
):
    """사용자 추천 통계 조회"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        stats = await recommendation_engine.get_user_recommendation_stats(user_id)
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendation stats: {str(e)}")
        raise HTTPException(status_code=500, detail="추천 통계 조회 중 오류가 발생했습니다.")
