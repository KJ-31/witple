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
        "rating": 4.5,  # 실제 평점 데이터가 없으므로 기본값
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


@router.get("/{attraction_id}")
async def get_attraction_details(attraction_id: str, db: Session = Depends(get_db)):
    """특정 관광지의 상세 정보를 가져옵니다."""
    try:
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
                return matching_attractions[0][1]
            
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


def sort_regions_by_priority(regions):
    """지역을 우선순위에 따라 정렬합니다."""
    # 우선순위 정의
    priority_order = [
        # 특별시/광역시
        "서울특별시", "서울시",
        "부산광역시", "부산시",
        "대구광역시", "대구시", 
        "인천광역시", "인천시",
        "광주광역시", "광주시",
        "대전광역시", "대전시",
        "울산광역시", "울산시",
        "세종특별자치시", "세종시",
        
        # 도
        "경기도",
        "강원특별자치도", "강원도",
        "충청북도",
        "충청남도", 
        "전북특별자치도", "전라북도",
        "전라남도",
        "경상북도",
        "경상남도",
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


@router.get("/filtered")
async def get_filtered_attractions(
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    page: int = Query(0, ge=0, description="페이지 번호 (0부터 시작)"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 결과 수"),
    db: Session = Depends(get_db)
):
    """지역 및 카테고리별로 필터링된 관광지 목록을 가져옵니다."""
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
        
        # 각 테이블에서 필터링된 결과 조회
        for table_name, table_model in search_tables.items():
            query = db.query(table_model)
            
            # 지역 필터
            if region:
                query = query.filter(
                    or_(
                        table_model.region.ilike(f"%{region}%"),
                        table_model.region == region
                    )
                )
            
            # 페이지네이션 적용하여 검색 결과 조회
            offset = page * limit
            attractions = query.offset(offset).limit(limit).all()
            
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
        
        # 전체 결과 개수 계산
        total_results = 0
        for table_name, table_model in search_tables.items():
            query = db.query(table_model)
            if region:
                query = query.filter(
                    or_(
                        table_model.region.ilike(f"%{region}%"),
                        table_model.region == region
                    )
                )
            total_results += query.count()
        
        return {
            "attractions": results,
            "total": len(results),
            "totalAvailable": total_results,
            "page": page,
            "limit": limit,
            "hasMore": (page + 1) * limit < total_results,
            "filters": {
                "region": region,
                "category": category
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"필터링된 관광지 조회 중 오류 발생: {str(e)}"
        )

