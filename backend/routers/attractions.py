from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_, and_

from database import get_db
from models import User
from models_attractions import Nature, Restaurant, Shopping, Accommodation, Humanities, LeisureSports
from schemas import UserResponse

router = APIRouter(tags=["attractions"])

# 카테고리별 테이블 매핑
CATEGORY_TABLES = {
    "nature": Nature,
    "restaurants": Restaurant, 
    "shopping": Shopping,
    "accommodation": Accommodation,
    "humanities": Humanities,
    "leisure_sports": LeisureSports
}

def get_category_from_table(table_name: str) -> str:
    """테이블명에서 카테고리 추출"""
    category_map = {
        "nature": "nature",
        "restaurants": "food", 
        "shopping": "shopping",
        "accommodation": "accommodation",
        "humanities": "culture",
        "leisure_sports": "leisure"
    }
    return category_map.get(table_name, "tourist")

def format_attraction_data(attraction, category: str, table_name: str = None):
    """관광지 데이터 포맷팅"""
    # image_urls가 JSON 리스트인 경우 첫 번째 이미지 사용
    image_url = "/images/default.jpg"
    if attraction.image_urls and isinstance(attraction.image_urls, list) and len(attraction.image_urls) > 0:
        image_url = attraction.image_urls[0]
    
    # 기본 데이터 구조
    data = {
        "id": str(attraction.id),
        "name": attraction.name or "이름 없음",
        "description": attraction.overview[:100] + "..." if attraction.overview and len(attraction.overview) > 100 else (attraction.overview or "설명 없음"),
        "imageUrl": image_url,
        "rating": 4.5,  # 실제 평점 데이터가 없으므로 기본값
        "category": category,
        "address": attraction.address,
        "region": attraction.region,
        "city": attraction.city,
        "latitude": float(attraction.latitude) if attraction.latitude else None,
        "longitude": float(attraction.longitude) if attraction.longitude else None,
        "phoneNumber": getattr(attraction, 'phone_number', None),
        "parkingAvailable": getattr(attraction, 'parking_available', None)
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

async def get_attractions_by_city(db: Session, city_name: str, limit: int = 4):
    """도시별 관광지 조회"""
    attractions = []
    
    for table_name, table_model in CATEGORY_TABLES.items():
        query_result = db.query(table_model).filter(
            table_model.city.ilike(f"%{city_name}%")
        ).limit(2).all()  # 각 카테고리에서 2개씩
        
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
        attractions = await get_attractions_by_city(db, city)
        
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

# 임시 여행 데이터 - 실제로는 DB에서 가져와야 함
ATTRACTION_DATA = [
    {
        "id": "seoul",
        "cityName": "서울",
        "description": "과거와 현재가 공존하는",
        "region": "capital",
        "recommendationScore": 95,
        "attractions": [
            {
                "id": "gyeongbokgung",
                "name": "경복궁",
                "description": "조선왕조의 정궁",
                "imageUrl": "/images/gyeongbokgung.jpg",
                "rating": 4.5,
                "category": "culture"
            },
            {
                "id": "myeongdong",
                "name": "명동",
                "description": "쇼핑과 맛집의 메카",
                "imageUrl": "/images/myeongdong.jpg",
                "rating": 4.2,
                "category": "shopping"
            },
            {
                "id": "namsan-tower",
                "name": "남산타워",
                "description": "서울의 야경 명소",
                "imageUrl": "/images/namsan-tower.jpg",
                "rating": 4.3,
                "category": "tourist"
            },
            {
                "id": "hongdae",
                "name": "홍대",
                "description": "젊음과 예술의 거리",
                "imageUrl": "/images/hongdae.jpg",
                "rating": 4.4,
                "category": "culture"
            }
        ]
    },
    {
        "id": "jeju",
        "cityName": "제주도",
        "description": "자연이 선사하는 힐링",
        "region": "jeju",
        "recommendationScore": 92,
        "attractions": [
            {
                "id": "hallasan",
                "name": "한라산",
                "description": "제주도의 상징",
                "imageUrl": "/images/hallasan.jpg",
                "rating": 4.7,
                "category": "nature"
            },
            {
                "id": "seongsan-ilchulbong",
                "name": "성산일출봉",
                "description": "일출의 명소",
                "imageUrl": "/images/seongsan-ilchulbong.jpg",
                "rating": 4.6,
                "category": "nature"
            },
            {
                "id": "jeju-black-pork",
                "name": "제주 흑돼지",
                "description": "제주도만의 특별한 맛",
                "imageUrl": "/images/jeju-black-pork.jpg",
                "rating": 4.8,
                "category": "food"
            }
        ]
    },
    {
        "id": "busan",
        "cityName": "부산",
        "description": "바다와 산이 어우러진 영화의 도시",
        "region": "southeast",
        "recommendationScore": 88,
        "attractions": [
            {
                "id": "haeundae-beach",
                "name": "해운대 해수욕장",
                "description": "한국 최고의 해수욕장",
                "imageUrl": "/images/haeundae-beach.jpg",
                "rating": 4.6,
                "category": "nature"
            },
            {
                "id": "jagalchi-market",
                "name": "자갈치시장",
                "description": "신선한 해산물 전통시장",
                "imageUrl": "/images/jagalchi-market.jpg",
                "rating": 4.4,
                "category": "food"
            },
            {
                "id": "gamcheon-village",
                "name": "감천문화마을",
                "description": "한국의 마추픽추",
                "imageUrl": "/images/gamcheon-village.jpg",
                "rating": 4.5,
                "category": "culture"
            }
        ]
    },
    {
        "id": "jeonju",
        "cityName": "전주",
        "description": "한국의 맛과 전통문화의 중심지",
        "region": "southwest",
        "recommendationScore": 82,
        "attractions": [
            {
                "id": "jeonju-hanok-village",
                "name": "전주 한옥마을",
                "description": "전통 한옥 문화관광지",
                "imageUrl": "/images/jeonju-hanok-village.jpg",
                "rating": 4.5,
                "category": "culture"
            },
            {
                "id": "jeonju-bibimbap",
                "name": "전주 비빔밥",
                "description": "전주 대표 향토음식",
                "imageUrl": "/images/jeonju-bibimbap.jpg",
                "rating": 4.7,
                "category": "food"
            }
        ]
    },
    {
        "id": "gangneung",
        "cityName": "강릉",
        "description": "동해안의 보석",
        "region": "northeast",
        "recommendationScore": 78,
        "attractions": [
            {
                "id": "anmok-beach",
                "name": "안목해변",
                "description": "커피거리로 유명한 해변",
                "imageUrl": "/images/anmok-beach.jpg",
                "rating": 4.3,
                "category": "nature"
            },
            {
                "id": "gyeongpo-beach",
                "name": "경포해변",
                "description": "넓은 백사장의 아름다운 해변",
                "imageUrl": "/images/gyeongpo-beach.jpg",
                "rating": 4.4,
                "category": "nature"
            }
        ]
    }
]


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


@router.get("/attractions/{attraction_id}")
async def get_attraction_details(attraction_id: str, db: Session = Depends(get_db)):
    """특정 관광지의 상세 정보를 가져옵니다."""
    try:
        # 모든 테이블에서 해당 ID의 관광지 검색
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
                
                return formatted_attraction
        
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


@router.get("/search")
async def search_attractions(
    q: str = Query(..., description="검색 키워드"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    region: Optional[str] = Query(None, description="지역 필터"),
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
            
            # 검색 결과 조회 (최대 50개)
            attractions = query.limit(50).all()
            
            # 결과 포맷팅
            table_category = get_category_from_table(table_name)
            for attraction in attractions:
                formatted_attraction = format_attraction_data(attraction, table_category, table_name)
                formatted_attraction["city"] = {
                    "id": attraction.city.lower().replace(" ", "-") if attraction.city else "unknown",
                    "name": attraction.city or "알 수 없음",
                    "region": attraction.region or "알 수 없음"
                }
                results.append(formatted_attraction)
        
        return {
            "results": results,
            "total": len(results),
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