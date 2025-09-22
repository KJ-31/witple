from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_, and_, case
import math

from database import get_db
from models import User
from models_attractions import Nature, Restaurant, Shopping, Accommodation, Humanities, LeisureSports
from schemas import UserResponse
# ❌ v1 추천 시스템 import 주석처리
# from routers.recommendations import get_current_user_optional, recommendation_engine, get_similarity_based_places

# ✅ v2 추천 시스템 import
from auth_utils import get_current_user_optional  # 인증 함수는 별도 모듈로 이동
from vectorization2 import get_engine  # v2 추천 엔진 사용
from cache_utils import cache, cache_attraction_data, get_cached_attraction_data, increment_view_count, get_view_count
import logging

router = APIRouter(tags=["attractions"])

logger = logging.getLogger(__name__)

@router.get("/stats/views/{attraction_id}")
async def get_attraction_view_count(attraction_id: str):
    """관광지 조회수 조회 (Redis에서)"""
    try:
        view_count = get_view_count(attraction_id)
        return {
            "attraction_id": attraction_id,
            "view_count": view_count
        }
    except Exception as e:
        logger.error(f"Error getting view count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="조회수 조회 중 오류가 발생했습니다."
        )

# 카테고리별 테이블 매핑
CATEGORY_TABLES = {
    "leisure_sports": LeisureSports,
    "accommodation": Accommodation,
    "shopping": Shopping,
    "nature": Nature,
    "restaurants": Restaurant,
    "humanities": Humanities
}

def get_category_from_table(table_name: str) -> str:
    """테이블명에서 카테고리 추출"""
    category_map = {
        "nature": "nature",
        "restaurants": "restaurants", 
        "shopping": "shopping",
        "accommodation": "accommodation",
        "humanities": "humanities",
        "leisure_sports": "leisure_sports"
    }
    return category_map.get(table_name, "tourist")

def format_attraction_data(attraction, category: str, table_name: str = None):
    """관광지 데이터 포맷팅"""
    # image_urls가 JSON 리스트인 경우 첫 번째 유효한 이미지 사용
    image_url = None
    if attraction.image_urls and isinstance(attraction.image_urls, list) and len(attraction.image_urls) > 0:
        # 유효한 이미지 URL 찾기 (None이 아니고 빈 문자열이 아닌 것)
        for img_url in attraction.image_urls:
            if img_url and img_url.strip() and img_url != "/images/default.jpg":
                image_url = img_url
                break
    
    # 유효한 이미지가 없으면 None으로 설정 (프론트엔드에서 기본 UI 표시)
    if not image_url:
        image_url = None
    
    # 고유 ID 생성: 테이블명_id 형식으로 변경
    unique_id = f"{table_name}_{attraction.id}" if table_name else str(attraction.id)
    
    # 기본 데이터 구조
    data = {
        "id": unique_id,
        "name": attraction.name or "이름 없음",
        "description": attraction.overview[:100] + "..." if attraction.overview and len(attraction.overview) > 100 else (attraction.overview or "설명 없음"),
        "imageUrl": image_url,
        "category": category,
        "address": attraction.address,
        "region": attraction.region,
        "city": attraction.city,
        "latitude": float(attraction.latitude) if attraction.latitude else None,
        "longitude": float(attraction.longitude) if attraction.longitude else None,
        "phoneNumber": getattr(attraction, 'phone_number', None),
        "parkingAvailable": getattr(attraction, 'parking_available', None),
        "sourceTable": table_name  # 원본 테이블 정보 추가
    }
    
    # 테이블별 특정 필드 추가
    if table_name == "restaurants":
        data["businessHours"] = getattr(attraction, 'business_hours', None)
        data["signatureMenu"] = getattr(attraction, 'signature_menu', None)
        data["menu"] = getattr(attraction, 'menu', None)
        data["closedDays"] = getattr(attraction, 'closed_days', None)
    elif table_name == "accommodation":
        data["roomCount"] = getattr(attraction, 'room_count', None)
        data["roomType"] = getattr(attraction, 'room_type', None)
        data["checkIn"] = getattr(attraction, 'check_in', None)
        data["checkOut"] = getattr(attraction, 'check_out', None)
        data["cookingAvailable"] = getattr(attraction, 'cooking_available', None)
    elif table_name in ["shopping", "leisure_sports"]:
        data["businessHours"] = getattr(attraction, 'business_hours', None)
        data["closedDays"] = getattr(attraction, 'closed_days', None)
    else:
        # nature, humanities 등
        data["usageHours"] = getattr(attraction, 'usage_hours', None)
        data["closedDays"] = getattr(attraction, 'closed_days', None)
    
    return data

def get_approximate_bounds(lat: float, lng: float, radius_km: float = 1.0) -> dict:
    """대략적인 검색 범위 계산 (PostGIS 없이 성능 최적화용)"""
    # 위도 1도 ≈ 111km, 경도 1도 ≈ 88km (한국 기준)
    lat_offset = radius_km / 111.0
    lng_offset = radius_km / 88.0
    
    return {
        'min_lat': lat - lat_offset,
        'max_lat': lat + lat_offset,
        'min_lng': lng - lng_offset,
        'max_lng': lng + lng_offset
    }

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 지점 간의 거리를 계산 (Haversine formula, 단위: km)"""
    if not all([lat1, lon1, lat2, lon2]):
        return float('inf')
    
    # 지구의 반지름 (km)
    R = 6371.0
    
    # 라디안으로 변환
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # 차이 계산
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine 공식
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance

async def get_nearby_attractions(db: Session, selected_places: List[dict], radius_km: float = 1.0, limit: int = 50, category: str = None):
    """선택한 장소들 기준으로 주변 관광지 검색"""
    try:
        if not selected_places:
            return []
        
        nearby_attractions = []
        processed_ids = set()  # 중복 방지

        # 카테고리 필터에 따른 테이블 선택
        search_tables = {}
        if category:
            # 특정 카테고리에 맞는 테이블만 검색
            for table_name, table_model in CATEGORY_TABLES.items():
                if get_category_from_table(table_name) == category:
                    search_tables[table_name] = table_model
            logger.info(f"카테고리 '{category}' 필터 적용: {list(search_tables.keys())} 테이블에서 검색")
        else:
            # 카테고리 필터가 없으면 모든 테이블 검색
            search_tables = CATEGORY_TABLES
            logger.info("전체 카테고리에서 검색")

        # 각 경유지마다 균등하게 할당 (최소 10개씩은 보장)
        places_count = len(selected_places)
        limit_per_place = max(10, limit // places_count)

        logger.info(f"경유지별 할당: {places_count}개 경유지, 각각 최대 {limit_per_place}개씩")

        # 선택한 각 장소를 중심으로 검색
        for place_index, selected_place in enumerate(selected_places):
            if not selected_place.get('latitude') or not selected_place.get('longitude'):
                continue

            center_lat = float(selected_place['latitude'])
            center_lng = float(selected_place['longitude'])

            # 검색 범위 계산 (성능 최적화)
            bounds = get_approximate_bounds(center_lat, center_lng, radius_km)

            # 현재 경유지에서 찾은 장소 수 카운트
            current_place_count = 0

            # 선택된 카테고리 테이블에서 검색
            for table_name, table_model in search_tables.items():
                if current_place_count >= limit_per_place:
                    break
                try:
                    # 범위 기반 필터링으로 성능 최적화 - LIMIT 제거로 범위 내 모든 데이터 조회
                    query = db.query(table_model).filter(
                        table_model.latitude.isnot(None),
                        table_model.longitude.isnot(None),
                        table_model.latitude.between(bounds['min_lat'], bounds['max_lat']),
                        table_model.longitude.between(bounds['min_lng'], bounds['max_lng'])
                    )
                    
                    attractions = query.all()
                    logger.info(f"Table {table_name}: found {len(attractions)} attractions in bounds")

                    # 거리 계산하고 정렬해서 가까운 장소부터 처리
                    attractions_with_distance = []
                    for attraction in attractions:
                        distance = calculate_distance(
                            center_lat, center_lng,
                            float(attraction.latitude), float(attraction.longitude)
                        )
                        if distance <= radius_km:
                            attractions_with_distance.append((attraction, distance))

                    # 거리순으로 정렬
                    attractions_with_distance.sort(key=lambda x: x[1])

                except Exception as table_error:
                    logger.error(f"Error querying table {table_name}: {str(table_error)}")
                    continue
                
                # 거리순으로 정렬된 장소들을 처리
                for attraction, distance in attractions_with_distance:
                    # 현재 경유지 할당량 체크
                    if current_place_count >= limit_per_place:
                        break

                    # 고유 ID 생성
                    unique_id = f"{table_name}_{attraction.id}"

                    # 이미 처리된 장소는 스킵
                    if unique_id in processed_ids:
                        continue

                    # 선택한 장소와 같은 장소는 제외
                    if unique_id == selected_place.get('id'):
                        continue

                    category = get_category_from_table(table_name)
                    formatted_attraction = format_attraction_data(attraction, category, table_name)
                    formatted_attraction['distance'] = round(distance, 2)  # 거리 정보 추가
                    formatted_attraction['nearbyTo'] = selected_place.get('name', '선택한 장소')  # 어느 장소 근처인지

                    nearby_attractions.append(formatted_attraction)
                    processed_ids.add(unique_id)
                    current_place_count += 1

                    # 현재 경유지에서 할당량 달성시 중단
                    if current_place_count >= limit_per_place:
                        break
        
        # 거리 순으로 정렬
        nearby_attractions.sort(key=lambda x: x['distance'])
        
        return nearby_attractions[:limit]
        
    except Exception as e:
        logger.error(f"Error in get_nearby_attractions: {str(e)}")
        return []

async def get_db_fallback_places(db: Session, region: str, category: str = None, limit: int = 20, page: int = 0, exclude_ids: set = None):
    """추천 엔진 실패시 DB에서 직접 가져오는 fallback"""
    places = []
    exclude_ids = exclude_ids or set()
    
    # 검색할 테이블들 결정
    search_tables = {}
    if category and category != 'all':
        for table_name, table_model in CATEGORY_TABLES.items():
            if get_category_from_table(table_name) == category:
                search_tables[table_name] = table_model
    else:
        search_tables = CATEGORY_TABLES
    
    for table_name, table_model in search_tables.items():
        if len(places) >= limit:
            break
            
        # 지역으로 필터링
        if region == "전국":
            # 전국일 때는 모든 데이터 가져오기
            query = db.query(table_model).offset(page * limit).limit(limit - len(places))
        else:
            query = db.query(table_model).filter(
                or_(
                    table_model.region.ilike(f"%{region}%"),
                    table_model.region == region,
                    table_model.city.ilike(f"%{region}%")
                )
            ).offset(page * limit).limit(limit - len(places))
        
        attractions = query.all()
        table_category = get_category_from_table(table_name)
        
        for attraction in attractions:
            place_id = f"{table_name}_{attraction.id}"
            if place_id not in exclude_ids:
                formatted_place = format_attraction_data(attraction, table_category, table_name)
                places.append(formatted_place)
                
                if len(places) >= limit:
                    break
    
    return places

async def get_attractions_by_city(db: Session, city_name: str, limit: int = 8):
    """도시별 관광지 조회 - 각 카테고리에서 골고루 가져오기"""
    attractions = []
    
    # 각 카테고리에서 1개씩 가져와서 다양성 확보
    for table_name, table_model in CATEGORY_TABLES.items():
        query_result = db.query(table_model).filter(
            table_model.city.ilike(f"%{city_name}%")
        ).limit(1).all()  # 각 카테고리에서 1개씩
        
        category = get_category_from_table(table_name)
        for attraction in query_result:
            attractions.append(format_attraction_data(attraction, category, table_name))
    
    # 아직 limit에 도달하지 않았으면 추가로 더 가져오기
    if len(attractions) < limit:
        for table_name, table_model in CATEGORY_TABLES.items():
            if len(attractions) >= limit:
                break
            query_result = db.query(table_model).filter(
                table_model.city.ilike(f"%{city_name}%")
            ).offset(1).limit(1).all()  # 두 번째부터 가져오기
            
            category = get_category_from_table(table_name)
            for attraction in query_result:
                attractions.append(format_attraction_data(attraction, category, table_name))
    
    return attractions[:limit]  # 최대 limit개까지만

async def get_cities_with_attractions(db: Session, offset: int = 0, limit: int = 3):
    """관광지가 있는 도시들 조회"""
    cities_data = []
    
    # 모든 테이블에서 도시 정보 수집
    all_cities = set()
    for table_model in CATEGORY_TABLES.values():
        cities = db.query(table_model.city, table_model.region).filter(
            table_model.city.isnot(None)
        ).distinct().all()
        
        for city, region in cities:
            if city and city.strip():
                all_cities.add((city.strip(), region.strip() if region else ""))
    
    # 도시 목록 정렬
    sorted_cities = sorted(list(all_cities))
    
    # 페이지네이션 적용
    paginated_cities = sorted_cities[offset:offset + limit]
    
    for index, (city, region) in enumerate(paginated_cities):
        attractions = await get_attractions_by_city(db, city, limit=20)
        
        # 관광지가 있는 도시만 포함
        if attractions:
            # 도시별 설명 및 점수 계산 (임시)
            city_descriptions = {
                "서울": "과거와 현재가 공존하는",
                "제주": "자연이 선사하는 힐링",
                "부산": "바다와 산이 어우러진 영화의 도시",
                "전주": "한국의 맛과 전통문화의 중심지",
                "강릉": "동해안의 보석",
                "경주": "천년고도, 살아있는 역사의 도시"
            }
            
            # unique ID 생성 (도시명 + 지역 + 인덱스)
            city_id = f"{city.lower().replace(' ', '-')}-{region.lower().replace(' ', '-') if region else 'unknown'}-{offset + index}"
            
            cities_data.append({
                "id": city_id,
                "cityName": city,
                "description": city_descriptions.get(city, f"{city}의 아름다운 여행지"),
                "region": region or "unknown",
                "recommendationScore": max(90 - len(cities_data) * 5, 60),  # 점수 계산
                "attractions": attractions
            })
    
    return cities_data, len(sorted_cities)


@router.post("/nearby")
async def get_nearby_places(
    selected_places: List[dict],
    radius_km: float = Query(1.0, ge=0.1, le=10, description="검색 반경 (km)"),
    limit: int = Query(50, ge=1, le=500, description="최대 결과 수"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    db: Session = Depends(get_db)
):
    """선택한 장소들을 기준으로 주변 관광지를 검색합니다."""
    try:
        logger.info(f"Nearby places request: {len(selected_places)} selected places, radius: {radius_km}km")
        
        if not selected_places:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="선택한 장소가 없습니다."
            )
        
        # 주변 관광지 검색
        nearby_attractions = await get_nearby_attractions(
            db=db,
            selected_places=selected_places,
            radius_km=radius_km,
            limit=limit,
            category=category
        )
        
        return {
            "attractions": nearby_attractions,
            "total": len(nearby_attractions),
            "searchRadius": radius_km,
            "selectedPlacesCount": len(selected_places),
            "message": f"{len(selected_places)}개 장소 기준 {radius_km}km 반경에서 {len(nearby_attractions)}개 장소를 찾았습니다."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in nearby places search: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"주변 장소 검색 중 오류 발생: {str(e)}"
        )


@router.get("/regions")
async def get_regions(db: Session = Depends(get_db)):
    """사용 가능한 지역 목록을 가져옵니다."""
    try:
        regions = set()
        
        # 모든 테이블에서 지역 정보 수집
        for table_model in CATEGORY_TABLES.values():
            region_results = db.query(table_model.region).filter(
                table_model.region.isnot(None),
                table_model.region != ""
            ).distinct().all()
            
            for (region,) in region_results:
                if region and region.strip():
                    regions.add(region.strip())
        
        # 지역 목록을 우선순위에 따라 정렬
        sorted_regions = sort_regions_by_priority(list(regions))
        
        return {
            "regions": sorted_regions,
            "total": len(sorted_regions)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지역 목록 조회 중 오류 발생: {str(e)}"
        )


@router.get("/categories")
async def get_categories():
    """사용 가능한 카테고리 목록을 가져옵니다."""
    try:
        categories = [
            {"id": "nature", "name": "자연", "description": "자연 경관과 공원"},
            {"id": "restaurants", "name": "맛집", "description": "음식점과 카페"},
            {"id": "shopping", "name": "쇼핑", "description": "쇼핑몰과 시장"},
            {"id": "accommodation", "name": "숙박", "description": "호텔과 펜션"},
            {"id": "humanities", "name": "인문", "description": "문화재와 박물관"},
            {"id": "leisure_sports", "name": "레저", "description": "스포츠와 레저 활동"}
        ]
        
        return {
            "categories": categories,
            "total": len(categories)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"카테고리 목록 조회 중 오류 발생: {str(e)}"
        )


@router.get("/filtered-by-category")
async def get_filtered_attractions_by_category(
    region: Optional[str] = Query(None, description="지역 필터"),
    page: int = Query(0, ge=0, description="페이지 번호 (0부터 시작)"),
    limit: int = Query(8, ge=1, le=50, description="카테고리당 결과 수"),
    db: Session = Depends(get_db)
):
    """지역별로 카테고리별 그룹화된 관광지 목록을 가져옵니다."""
    try:
        if not region:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="지역을 선택해주세요."
            )
        
        # 카테고리별로 그룹화된 결과
        category_sections = []
        
        # 각 카테고리별로 데이터 조회
        for table_name, table_model in CATEGORY_TABLES.items():
            category = get_category_from_table(table_name)
            
            # 해당 카테고리에서 지역 필터 적용
            query = db.query(table_model).filter(
                or_(
                    table_model.region.ilike(f"%{region}%"),
                    table_model.region == region
                )
            )
            
            # 페이지네이션 적용
            offset = page * limit
            attractions = query.offset(offset).limit(limit).all()
            
            # 결과가 있는 카테고리만 포함
            if attractions:
                formatted_attractions = []
                for attraction in attractions:
                    formatted_attraction = format_attraction_data(attraction, category, table_name)
                    formatted_attraction["city"] = {
                        "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                        "name": attraction.city or "알 수 없음",
                        "region": attraction.region or "알 수 없음"
                    }
                    formatted_attractions.append(formatted_attraction)
                
                # 카테고리 섹션 생성
                category_sections.append({
                    "category": category,
                    "categoryName": get_category_korean_name(category),
                    "attractions": formatted_attractions,
                    "total": len(formatted_attractions)
                })
        
        # 카테고리별 총 개수 계산
        total_by_category = {}
        for table_name, table_model in CATEGORY_TABLES.items():
            category = get_category_from_table(table_name)
            query = db.query(table_model).filter(
                or_(
                    table_model.region.ilike(f"%{region}%"),
                    table_model.region == region
                )
            )
            total_by_category[category] = query.count()
        
        return {
            "region": region,
            "categorySections": category_sections,
            "totalByCategory": total_by_category,
            "page": page,
            "limit": limit,
            "hasMore": any(total > (page + 1) * limit for total in total_by_category.values())
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지역별 카테고리 관광지 조회 중 오류 발생: {str(e)}"
        )


def get_category_korean_name(category: str) -> str:
    """카테고리 영어명을 한국어명으로 변환"""
    category_map = {
        "nature": "자연",
        "restaurants": "맛집", 
        "shopping": "쇼핑",
        "accommodation": "숙박",
        "humanities": "인문",
        "leisure_sports": "레저"
    }
    return category_map.get(category, category)


def get_first_valid_image(image_urls):
    """이미지 URL에서 첫 번째 유효한 이미지 반환"""
    if not image_urls:
        return None
    
    try:
        if isinstance(image_urls, list) and len(image_urls) > 0:
            for img_url in image_urls:
                if img_url and img_url.strip() and img_url != "/images/default.jpg":
                    return img_url
        elif isinstance(image_urls, str):
            if image_urls.startswith('[') and image_urls.endswith(']'):
                import json
                parsed_urls = json.loads(image_urls)
                if isinstance(parsed_urls, list) and len(parsed_urls) > 0:
                    for img_url in parsed_urls:
                        if img_url and img_url.strip() and img_url != "/images/default.jpg":
                            return img_url
            elif image_urls.strip() and image_urls != "/images/default.jpg":
                return image_urls
    except Exception:
        pass
    
    return None


def sort_regions_by_priority(regions):
    """지역을 우선순위에 따라 정렬합니다."""
    # 우선순위 정의
    priority_order = [
        "서울특별시", "서울", "서울시",
        "부산광역시", "부산", "부산시",
        "대구광역시", "대구", "대구시",
        "인천광역시", "인천", "인천시",
        "광주광역시", "광주", "광주시",
        "대전광역시", "대전", "대전시",
        "울산광역시", "울산", "울산시",
        "세종특별자치시", "세종", "세종시",
        "경기도", "경기",
        "강원도", "강원",
        "충청북도", "충북",
        "충청남도", "충남",
        "전라북도", "전북",
        "전라남도", "전남",
        "경상북도", "경북",
        "경상남도", "경남",
        "제주특별자치도", "제주도", "제주"
    ]
    
    # 우선순위에 따라 정렬
    sorted_regions = []
    remaining_regions = regions.copy()
    
    # 우선순위 순서대로 추가
    for priority_region in priority_order:
        for region in remaining_regions:
            if priority_region in region or region in priority_region:
                sorted_regions.append(region)
                remaining_regions.remove(region)
                break
    
    # 남은 지역들을 알파벳 순으로 추가
    sorted_regions.extend(sorted(remaining_regions))
    
    return sorted_regions


@router.get("/cities-by-category")
async def get_cities_by_category(
    page: int = Query(0, ge=0, description="페이지 번호 (0부터 시작)"),
    limit: int = Query(3, ge=1, le=10, description="페이지당 지역 수"),
    db: Session = Depends(get_db)
):
    """지역별로 카테고리별 구분된 섹션을 반환합니다."""
    try:
        # 모든 지역 수집
        all_regions = set()
        for table_model in CATEGORY_TABLES.values():
            region_results = db.query(table_model.region).filter(
                table_model.region.isnot(None),
                table_model.region != ""
            ).distinct().all()
            
            for (region,) in region_results:
                if region and region.strip():
                    all_regions.add(region.strip())
        
        # 지역을 우선순위에 따라 정렬
        sorted_regions = sort_regions_by_priority(list(all_regions))
        
        # 페이지네이션 적용
        offset = page * limit
        paginated_regions = sorted_regions[offset:offset + limit]
        
        cities_data = []
        
        for region in paginated_regions:
            # 해당 지역의 카테고리별 데이터 조회
            category_sections = []
            
            for table_name, table_model in CATEGORY_TABLES.items():
                category = get_category_from_table(table_name)
                
                # 해당 카테고리에서 지역 필터 적용
                query = db.query(table_model).filter(
                    or_(
                        table_model.region.ilike(f"%{region}%"),
                        table_model.region == region
                    )
                )
                
                # 각 카테고리에서 최대 10개씩 가져오기
                attractions = query.limit(10).all()
                
                # 결과가 있는 카테고리만 포함
                if attractions:
                    formatted_attractions = []
                    for attraction in attractions:
                        formatted_attraction = format_attraction_data(attraction, category, table_name)
                        formatted_attraction["city"] = {
                            "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                            "name": attraction.city or "알 수 없음",
                            "region": attraction.region or "알 수 없음"
                        }
                        formatted_attractions.append(formatted_attraction)
                    
                    # 카테고리 섹션 생성
                    category_sections.append({
                        "category": category,
                        "categoryName": get_category_korean_name(category),
                        "attractions": formatted_attractions,
                        "total": len(formatted_attractions)
                    })
            
            # 카테고리가 있는 지역만 포함
            if category_sections:
                cities_data.append({
                    "id": f"region-{region}-{page}",
                    "cityName": region,
                    "description": f"{region}의 아름다운 여행지",
                    "region": region,
                    "recommendationScore": 95 - len(cities_data) * 5,
                    "categorySections": category_sections
                })
        
        return {
            "data": cities_data,
            "hasMore": offset + limit < len(sorted_regions),
            "total": len(sorted_regions),
            "page": page,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"지역별 카테고리 데이터 조회 중 오류 발생: {str(e)}"
        )


@router.get("/cities")
async def get_recommended_cities(
    page: int = Query(0, ge=0, description="페이지 번호 (0부터 시작)"),
    limit: int = Query(3, ge=1, le=10, description="페이지당 도시 수"),
    db: Session = Depends(get_db)
):
    """추천 도시 목록을 페이지네이션으로 가져옵니다."""
    try:
        # 페이지네이션 계산
        offset = page * limit
        
        # 실제 데이터베이스에서 도시 데이터 조회
        cities_data, total_cities = await get_cities_with_attractions(db, offset, limit)
        has_more = offset + limit < total_cities
        
        return {
            "data": cities_data,
            "hasMore": has_more,
            "total": total_cities,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"도시 데이터 조회 중 오류 발생: {str(e)}"
        )


@router.get("/cities/{city_id}")
async def get_city_details(city_id: str, db: Session = Depends(get_db)):
    """특정 도시의 상세 정보를 가져옵니다."""
    try:
        # city_id에서 실제 도시명 추출 (예: "seoul" -> "서울")
        city_name_map = {
            "seoul": "서울",
            "jeju": "제주",
            "busan": "부산", 
            "jeonju": "전주",
            "gangneung": "강릉",
            "gyeongju": "경주",
            "incheon": "인천",
            "andong": "안동"
        }
        
        actual_city_name = city_name_map.get(city_id)
        if not actual_city_name:
            # city_id를 그대로 사용하여 검색
            actual_city_name = city_id.replace("-", " ").title()
        
        # 데이터베이스에서 해당 도시의 관광지들 조회
        attractions = await get_attractions_by_city(db, actual_city_name, limit=20)
        
        if not attractions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="도시를 찾을 수 없습니다."
            )
        
        # 도시 정보 조회 (첫 번째 관광지의 정보 사용)
        city_region = "unknown"
        for table_model in CATEGORY_TABLES.values():
            result = db.query(table_model.region).filter(
                table_model.city.ilike(f"%{actual_city_name}%")
            ).first()
            if result and result.region:
                city_region = result.region
                break
        
        city_descriptions = {
            "서울": "과거와 현재가 공존하는",
            "제주": "자연이 선사하는 힐링",
            "부산": "바다와 산이 어우러진 영화의 도시",
            "전주": "한국의 맛과 전통문화의 중심지",
            "강릉": "동해안의 보석",
            "경주": "천년고도, 살아있는 역사의 도시"
        }
        
        city_data = {
            "id": city_id,
            "cityName": actual_city_name,
            "description": city_descriptions.get(actual_city_name, f"{actual_city_name}의 아름다운 여행지"),
            "region": city_region,
            "recommendationScore": 85,  # 기본 점수
            "attractions": attractions
        }
        
        return city_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"도시 상세 정보 조회 중 오류 발생: {str(e)}"
        )


@router.get("/{table_name}/{attraction_id}")
async def get_attraction_details_by_table(table_name: str, attraction_id: str, db: Session = Depends(get_db)):
    """특정 테이블에서 관광지 상세 정보를 가져옵니다."""
    try:
        # 테이블명 검증
        if table_name not in CATEGORY_TABLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"잘못된 테이블명: {table_name}"
            )
        
        table_model = CATEGORY_TABLES[table_name]
        attraction = db.query(table_model).filter(
            table_model.id == int(attraction_id)
        ).first()
        
        if not attraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="관광지를 찾을 수 없습니다."
            )
        
        category = get_category_from_table(table_name)
        formatted_attraction = format_attraction_data(attraction, category, table_name)
        
        # 추가 상세 정보 포함
        formatted_attraction.update({
            "city": {
                "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                "name": attraction.city or "알 수 없음",
                "region": attraction.region or "알 수 없음"
            },
            "detailedInfo": getattr(attraction, 'detailed_info', None),
            "closedDays": getattr(attraction, 'closed_days', None),
            "majorCategory": getattr(attraction, 'major_category', None),
            "middleCategory": getattr(attraction, 'middle_category', None),
            "minorCategory": getattr(attraction, 'minor_category', None),
            "imageUrls": attraction.image_urls if attraction.image_urls else [],
            "createdAt": attraction.created_at.isoformat() if attraction.created_at else None,
            "updatedAt": attraction.updated_at.isoformat() if attraction.updated_at else None,
            "sourceTable": table_name  # 원본 테이블 정보 추가
        })
        
        return formatted_attraction
        
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="잘못된 관광지 ID입니다."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"관광지 상세 정보 조회 중 오류 발생: {str(e)}"
        )


@router.get("/search")
async def search_attractions(
    q: str = Query(..., description="검색 키워드"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    region: Optional[str] = Query(None, description="지역 필터"),
    page: int = Query(0, ge=0, description="페이지 번호 (0부터 시작)"),
    limit: int = Query(50, ge=1, le=200, description="페이지당 결과 수"),
    db: Session = Depends(get_db)
):
    """관광지 검색 기능"""
    try:
        results = []
        
        # 카테고리 필터에 따른 테이블 선택
        search_tables = {}
        if category:
            # 카테고리에 맞는 테이블만 검색
            for table_name, table_model in CATEGORY_TABLES.items():
                table_category = get_category_from_table(table_name)
                if table_category == category:
                    search_tables[table_name] = table_model
        else:
            # 모든 테이블 검색
            search_tables = CATEGORY_TABLES
        
        # 각 테이블에서 검색
        seen_attractions = set()  # 중복 방지를 위한 집합
        
        for table_name, table_model in search_tables.items():
            query = db.query(table_model)
            
            # 검색 키워드 필터
            search_filter = or_(
                table_model.name.ilike(f"%{q}%"),
                table_model.overview.ilike(f"%{q}%"),
                table_model.address.ilike(f"%{q}%"),
                table_model.city.ilike(f"%{q}%")
            )
            query = query.filter(search_filter)
            
            # 지역 필터
            if region:
                query = query.filter(table_model.region.ilike(f"%{region}%"))
            
            # 총 개수를 먼저 구하기
            total_count = query.count()
            
            # 페이지네이션 적용하여 검색 결과 조회
            offset = page * limit
            attractions = query.offset(offset).limit(limit).all()
            
            # 결과 포맷팅 및 중복 제거
            table_category = get_category_from_table(table_name)
            for attraction in attractions:
                # 중복 체크: 이름과 주소가 같은 항목은 제외
                attraction_key = f"{attraction.name}_{attraction.address}"
                if attraction_key in seen_attractions:
                    continue
                seen_attractions.add(attraction_key)
                
                formatted_attraction = format_attraction_data(attraction, table_category, table_name)
                formatted_attraction["city"] = {
                    "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                    "name": attraction.city or "알 수 없음",
                    "region": attraction.region or "알 수 없음"
                }
                results.append(formatted_attraction)
        
        # 전체 결과 개수 계산 (모든 테이블의 매칭 결과 합계)
        total_results = 0
        for table_name, table_model in search_tables.items():
            query = db.query(table_model)
            search_filter = or_(
                table_model.name.ilike(f"%{q}%"),
                table_model.overview.ilike(f"%{q}%"),
                table_model.address.ilike(f"%{q}%"),
                table_model.city.ilike(f"%{q}%")
            )
            query = query.filter(search_filter)
            if region:
                query = query.filter(table_model.region.ilike(f"%{region}%"))
            total_results += query.count()
        
        return {
            "results": results,
            "total": len(results),
            "totalAvailable": total_results,
            "page": page,
            "limit": limit,
            "hasMore": (page + 1) * limit < total_results,
            "query": q,
            "filters": {
                "category": category,
                "region": region
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 중 오류 발생: {str(e)}"
        )


@router.get("/filtered")
async def get_filtered_attractions(
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    page: int = Query(0, ge=0, description="페이지 번호 (0부터 시작)"),
    limit: int = Query(50, ge=1, le=100, description="페이지당 결과 수"),
    current_user = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """일정 짜기 페이지용 추천 알고리즘 적용 관광지 목록"""
    try:
        logger.info(f"Filtered attractions request: region={region}, category={category}, limit={limit}")
        
        # 지역이 필수로 필요함 (일정 짜기 페이지는 특정 지역 기반)
        if not region:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="지역을 선택해주세요."
            )
        
        # 캐시 키 생성 (사용자별, 파라미터별)
        user_id = str(current_user.user_id) if current_user and hasattr(current_user, 'user_id') else "anonymous"
        cache_key = f"filtered_attractions:{user_id}:{region}:{category}:{page}:{limit}"
        
        # 캐시에서 조회 시도
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Cache hit for filtered attractions: {cache_key}")
            return cached_result
        
        results = []
        
        # 로그인 상태에 따른 추천 알고리즘 적용
        if current_user and hasattr(current_user, 'user_id'):
            # 로그인 시: 개인화 추천 + 코사인 유사도 혼합
            user_id = str(current_user.user_id)
            logger.info(f"Personalized recommendations for user: {user_id}")
            
            try:
                # 개인화 추천 (상단 절반)
                personalized_limit = min(25, limit // 2)
                personalized_places = await recommendation_engine.get_personalized_recommendations(
                    user_id=user_id,
                    region=region,
                    category=category,
                    limit=personalized_limit
                )
                
                # ❌ v1 주석처리
                # # 코사인 유사도 기반 (하단 절반) - 중복 제거
                # used_place_ids = {f"{p['table_name']}_{p['place_id']}" for p in personalized_places}
                # similarity_limit = limit - len(personalized_places)
                # similarity_places = await get_similarity_based_places(
                #     region=region,
                #     category=category,
                #     limit=similarity_limit,
                #     exclude_ids=used_place_ids
                # )

                # v2에서는 이미 통합되어 처리되므로 별도 유사도 기반 처리 불필요
                similarity_places = []
                
                # 결과 결합 및 포맷팅
                all_recommendations = personalized_places + similarity_places
                
                for i, place in enumerate(all_recommendations):
                    # recommendations 형태를 attractions 형태로 변환
                    formatted_attraction = {
                        "id": f"{place['table_name']}_{place['place_id']}",
                        "name": place.get('name', '이름 없음'),
                        "description": place.get('description', '설명 없음'),
                        "imageUrl": get_first_valid_image(place.get('image_urls')),

                        "category": get_category_from_table(place['table_name']),
                        "region": place.get('region', region),
                        "city": {
                            "name": place.get('city', '알 수 없음'),
                            "region": place.get('region', region)
                        },
                        "latitude": place.get('latitude'),
                        "longitude": place.get('longitude'),
                        "sourceTable": place['table_name'],
                        "recommendationType": "personalized" if i < len(personalized_places) else "similarity"
                    }
                    results.append(formatted_attraction)
                
                logger.info(f"Retrieved {len(results)} personalized attractions")
                
            except Exception as e:
                logger.error(f"Personalized recommendations failed: {str(e)}")
                # ❌ v1 주석처리
                # # 개인화 실패시 유사도 기반으로 fallback
                # similarity_places = await get_similarity_based_places(
                #     region=region,
                #     category=category,
                #     limit=limit,
                #     exclude_ids=set()
                # )

                # ✅ v2 추천 시스템 사용 (fallback)
                engine = await get_engine()
                similarity_places = await engine.get_recommendations(
                    user_id=None,  # 비로그인 사용자로 처리
                    region=region,
                    category=category,
                    limit=limit
                )
                
                for place in similarity_places:
                    formatted_attraction = {
                        "id": f"{place['table_name']}_{place['place_id']}",
                        "name": place.get('name', '이름 없음'),
                        "description": place.get('description', '설명 없음'),
                        "imageUrl": get_first_valid_image(place.get('image_urls')),

                        "category": get_category_from_table(place['table_name']),
                        "region": place.get('region', region),
                        "city": {
                            "name": place.get('city', '알 수 없음'),
                            "region": place.get('region', region)
                        },
                        "latitude": place.get('latitude'),
                        "longitude": place.get('longitude'),
                        "sourceTable": place['table_name'],
                        "recommendationType": "similarity"
                    }
                    results.append(formatted_attraction)
        
        else:
            # ❌ v1 주석처리
            # # 비로그인 시: 코사인 유사도만
            # logger.info("Guest user - similarity based recommendations")
            # similarity_places = await get_similarity_based_places(
            #     region=region,
            #     category=category,
            #     limit=limit,
            #     exclude_ids=set()
            # )

            # ✅ v2 추천 시스템 사용 (비로그인)
            logger.info("Guest user - v2 recommendation system")
            engine = await get_engine()
            similarity_places = await engine.get_recommendations(
                user_id=None,  # 비로그인 사용자로 처리
                region=region,
                category=category,
                limit=limit
            )
            
            for place in similarity_places:
                formatted_attraction = {
                    "id": f"{place['table_name']}_{place['place_id']}",
                    "name": place.get('name', '이름 없음'),
                    "description": place.get('description', '설명 없음'),
                    "imageUrl": get_first_valid_image(place.get('image_urls')),

                    "category": get_category_from_table(place['table_name']),
                    "region": place.get('region', region),
                    "city": {
                        "name": place.get('city', '알 수 없음'),
                        "region": place.get('region', region)
                    },
                    "latitude": place.get('latitude'),
                    "longitude": place.get('longitude'),
                    "sourceTable": place['table_name'],
                    "recommendationType": "similarity"
                }
                results.append(formatted_attraction)
        
        # v2 추천 엔진이 0개를 반환하면 DB fallback 사용
        if len(results) == 0:
            logger.info("v2 추천 엔진이 0개 반환 - DB fallback 사용")
            fallback_places = await get_db_fallback_places(db, region, category, limit, page)
            results.extend(fallback_places)
            logger.info(f"DB fallback에서 {len(fallback_places)}개 장소 반환")
        
        # 전체 결과 수 계산 (페이지네이션 없이)
        total_available = 0
        
        for table_name, table_model in CATEGORY_TABLES.items():
            query = db.query(table_model)
            if region and region != '전국':
                query = query.filter(table_model.region.ilike(f"%{region}%"))
            if category:
                table_category = get_category_from_table(table_name)
                if table_category == category:
                    count = query.count()
                    total_available += count
            else:
                count = query.count()
                total_available += count
        
        # hasMore 계산
        has_more = (page + 1) * limit < total_available
        
        result = {
            "attractions": results,
            "total": len(results),
            "totalAvailable": total_available,
            "page": page,
            "limit": limit,
            "hasMore": has_more,
            "filters": {
                "region": region,
                "category": category
            }
        }
        
        # 결과를 캐시에 저장 (5분으로 단축 - 테스트용)
        cache.set(cache_key, result, expire=300)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in filtered attractions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필터링된 관광지 조회 중 오류 발생: {str(e)}"
        )


@router.get("/{attraction_id}")
async def get_attraction_details(attraction_id: str, db: Session = Depends(get_db)):
    """특정 관광지의 상세 정보를 가져옵니다. (Redis 캐싱 적용)"""
    try:
        # 캐시에서 조회 시도
        cached_result = get_cached_attraction_data(attraction_id)
        if cached_result is not None:
            logger.info(f"Cache hit for attraction: {attraction_id}")
            # 조회수 증가
            increment_view_count(attraction_id)
            return cached_result
        
        logger.info(f"Cache miss for attraction: {attraction_id}")
        # 새로운 ID 형식 처리: table_name_id 형식
        if "_" in attraction_id:
            # 테이블명이 여러 단어로 구성된 경우를 고려하여 마지막 _ 기준으로 분리
            parts = attraction_id.split("_")
            if len(parts) >= 2:
                # 마지막 부분이 숫자인지 확인
                if parts[-1].isdigit():
                    original_id = parts[-1]
                    table_name = "_".join(parts[:-1])
                else:
                    # 마지막 부분이 숫자가 아니면 첫 번째 _ 기준으로 분리
                    table_name, original_id = attraction_id.split("_", 1)
            else:
                table_name, original_id = attraction_id.split("_", 1)
            
            # 테이블명 검증
            if table_name not in CATEGORY_TABLES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"잘못된 테이블명: {table_name}"
                )
            
            table_model = CATEGORY_TABLES[table_name]
            attraction = db.query(table_model).filter(
                table_model.id == int(original_id)
            ).first()
            
            if not attraction:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="관광지를 찾을 수 없습니다."
                )
            
            category = get_category_from_table(table_name)
            formatted_attraction = format_attraction_data(attraction, category, table_name)
            
            # 추가 상세 정보 포함
            formatted_attraction.update({
                "city": {
                    "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                    "name": attraction.city or "알 수 없음",
                    "region": attraction.region or "알 수 없음"
                },
                "detailedInfo": getattr(attraction, 'detailed_info', None),
                "closedDays": getattr(attraction, 'closed_days', None),
                "majorCategory": getattr(attraction, 'major_category', None),
                "middleCategory": getattr(attraction, 'middle_category', None),
                "minorCategory": getattr(attraction, 'minor_category', None),
                "imageUrls": attraction.image_urls if attraction.image_urls else [],
                "createdAt": attraction.created_at.isoformat() if attraction.created_at else None,
                "updatedAt": attraction.updated_at.isoformat() if attraction.updated_at else None
            })
            
            # 조회수 증가
            increment_view_count(attraction_id)
            
            # 결과를 캐시에 저장 (2시간)
            cache_attraction_data(attraction_id, formatted_attraction, expire=7200)
            
            return formatted_attraction
        
        else:
            # 기존 ID 형식 (숫자만) - 하위 호환성을 위해 유지
            matching_attractions = []
            for table_name, table_model in CATEGORY_TABLES.items():
                attraction = db.query(table_model).filter(
                    table_model.id == int(attraction_id)
                ).first()
                
                if attraction:
                    category = get_category_from_table(table_name)
                    formatted_attraction = format_attraction_data(attraction, category, table_name)
                    
                    # 추가 상세 정보 포함
                    formatted_attraction.update({
                        "city": {
                            "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                            "name": attraction.city or "알 수 없음",
                            "region": attraction.region or "알 수 없음"
                        },
                        "detailedInfo": getattr(attraction, 'detailed_info', None),
                        "closedDays": getattr(attraction, 'closed_days', None),
                        "majorCategory": getattr(attraction, 'major_category', None),
                        "middleCategory": getattr(attraction, 'middle_category', None),
                        "minorCategory": getattr(attraction, 'minor_category', None),
                        "imageUrls": attraction.image_urls if attraction.image_urls else [],
                        "createdAt": attraction.created_at.isoformat() if attraction.created_at else None,
                        "updatedAt": attraction.updated_at.isoformat() if attraction.updated_at else None
                    })
                    
                    matching_attractions.append((table_name, formatted_attraction))
            
            # 매칭된 결과가 있으면 첫 번째 결과 반환
            if matching_attractions:
                result = matching_attractions[0][1]
                
                # 조회수 증가
                increment_view_count(attraction_id)
                
                # 결과를 캐시에 저장 (2시간)
                cache_attraction_data(attraction_id, result, expire=7200)
                
                return result
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="관광지를 찾을 수 없습니다."
            )
        
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="잘못된 관광지 ID입니다."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"관광지 상세 정보 조회 중 오류 발생: {str(e)}"
        )


@router.get("/{table_name}/{attraction_id}")
async def get_attraction_details_by_table(table_name: str, attraction_id: str, db: Session = Depends(get_db)):
    """특정 테이블에서 관광지 상세 정보를 가져옵니다."""
    try:
        # 테이블명 검증
        if table_name not in CATEGORY_TABLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"잘못된 테이블명: {table_name}"
            )
        
        table_model = CATEGORY_TABLES[table_name]
        attraction = db.query(table_model).filter(
            table_model.id == int(attraction_id)
        ).first()
        
        if not attraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="관광지를 찾을 수 없습니다."
            )
        
        category = get_category_from_table(table_name)
        formatted_attraction = format_attraction_data(attraction, category, table_name)
        
        # 추가 상세 정보 포함
        formatted_attraction.update({
            "city": {
                "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                "name": attraction.city or "알 수 없음",
                "region": attraction.region or "알 수 없음"
            },
            "detailedInfo": getattr(attraction, 'detailed_info', None),
            "closedDays": getattr(attraction, 'closed_days', None),
            "majorCategory": getattr(attraction, 'major_category', None),
            "middleCategory": getattr(attraction, 'middle_category', None),
            "minorCategory": getattr(attraction, 'minor_category', None),
            "imageUrls": attraction.image_urls if attraction.image_urls else [],
            "createdAt": attraction.created_at.isoformat() if attraction.created_at else None,
            "updatedAt": attraction.updated_at.isoformat() if attraction.updated_at else None,
            "sourceTable": table_name  # 원본 테이블 정보 추가
        })
        
        return formatted_attraction
        
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="잘못된 관광지 ID입니다."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"관광지 상세 정보 조회 중 오류 발생: {str(e)}"
        )



