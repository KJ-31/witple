from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
import json

from database import get_db
from models import Trip, User
from schemas import TripCreate, TripResponse, TripListResponse, TripStatus
from routers.auth import get_current_user
from auth_utils import get_current_user_optional
from cache_utils import cache

router = APIRouter()


def get_place_name(db: Session, table_name: str, place_id: str):
    """테이블명과 ID를 통해 장소명을 조회"""
    try:
        # 안전한 테이블명 검증 (SQL 인젝션 방지)
        valid_tables = ['accommodation', 'humanities', 'leisure_sports', 'nature', 'restaurants', 'shopping']
        if table_name not in valid_tables:
            return "Unknown Place"
        
        # 동적 쿼리 실행
        query = text(f"SELECT name FROM {table_name} WHERE id = :place_id")
        result = db.execute(query, {"place_id": place_id}).fetchone()
        
        return result[0] if result else "Unknown Place"
    except Exception as e:
        print(f"Error getting place name: {e}")
        return "Unknown Place"


def get_status_display(status: str):
    """여행 상태를 한국어로 변환"""
    status_map = {
        'planned': '📋 예정됨',
        'active': '🚩 진행중',
        'completed': '✓ 완료됨'
    }
    return status_map.get(status, status)


@router.get("/")
async def get_user_trips(
    status_filter: Optional[TripStatus] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사용자의 여행 목록 조회"""
    # 캐시 키 생성 (사용자별, 필터별)
    cache_key = f"trips:list:{current_user.user_id}:{status_filter.value if status_filter else 'all'}:{offset}:{limit}"
    
    # 캐시에서 조회 시도
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    query = db.query(Trip).filter(Trip.user_id == current_user.user_id)
    
    if status_filter:
        query = query.filter(Trip.status == status_filter.value)
    
    trips = query.offset(offset).limit(limit).all()
    total = query.count()
    
    # trips를 dict로 변환하여 반환
    trips_list = []
    for trip in trips:
        places = []
        if trip.places:
            places_data = json.loads(trip.places)
            # 각 장소에 대해 실제 장소명을 조회하여 추가
            for place in places_data:
                place_name = get_place_name(db, place.get('table_name', ''), place.get('id', ''))
                place['name'] = place_name
                places.append(place)
        
        trips_list.append({
            "id": trip.id,
            "title": trip.title,
            "description": trip.description,
            "places": places,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "status": trip.status,
            "status_display": get_status_display(trip.status),
            "created_at": trip.created_at.isoformat() if trip.created_at else None
        })
    
    result = {"trips": trips_list, "total": total}
    
    # 결과를 캐시에 저장 (15분)
    cache.set(cache_key, result, expire=900)
    
    return result


@router.get("/user/{user_id}")
async def get_user_public_trips(
    user_id: str,
    status_filter: Optional[TripStatus] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """다른 사용자의 공개 여행 목록 조회"""
    # 캐시 키 생성
    cache_key = f"trips:public:{user_id}:{status_filter.value if status_filter else 'all'}:{offset}:{limit}"
    
    # 캐시에서 조회 시도
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # 사용자 존재 확인
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    query = db.query(Trip).filter(Trip.user_id == user_id)
    
    if status_filter:
        query = query.filter(Trip.status == status_filter.value)
    
    trips = query.offset(offset).limit(limit).all()
    total = query.count()
    
    # trips를 dict로 변환하여 반환
    trips_list = []
    for trip in trips:
        places = []
        if trip.places:
            places_data = json.loads(trip.places)
            # 각 장소에 대해 실제 장소명을 조회하여 추가
            for place in places_data:
                place_name = get_place_name(db, place.get('table_name', ''), place.get('id', ''))
                place['name'] = place_name
                places.append(place)
        
        trips_list.append({
            "id": trip.id,
            "title": trip.title,
            "description": trip.description,
            "places": places,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "status": trip.status,
            "status_display": get_status_display(trip.status),
            "created_at": trip.created_at.isoformat() if trip.created_at else None
        })
    
    result = {"trips": trips_list, "total": total}
    
    # 결과를 캐시에 저장 (5분 - 다른 사용자 데이터이므로 짧게)
    cache.set(cache_key, result, expire=300)
    
    return result


@router.get("/{trip_id}")
async def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 여행 상세 조회"""
    # 캐시 키 생성
    cache_key = f"trip:detail:{current_user.user_id}:{trip_id}"
    
    # 캐시에서 조회 시도
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == current_user.user_id
    ).first()
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="여행을 찾을 수 없습니다."
        )
    
    # places JSON 필드 파싱 및 장소명 조회
    places = []
    if trip.places:
        places_data = json.loads(trip.places)
        # 각 장소에 대해 실제 장소명을 조회하여 추가
        for place in places_data:
            place_name = get_place_name(db, place.get('table_name', ''), place.get('id', ''))
            place['name'] = place_name
            places.append(place)
    
    result = {
        "id": trip.id,
        "title": trip.title,
        "description": trip.description,
        "places": places,
        "start_date": trip.start_date.isoformat() if trip.start_date else None,
        "end_date": trip.end_date.isoformat() if trip.end_date else None,
        "status": trip.status,
        "status_display": get_status_display(trip.status),
        "created_at": trip.created_at.isoformat() if trip.created_at else None
    }
    
    # 결과를 캐시에 저장 (20분)
    cache.set(cache_key, result, expire=1200)
    
    return result


@router.post("/")
async def create_trip(
    trip_data: dict,  # 프론트엔드 데이터를 직접 받음
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """새 여행 생성"""
    try:
        # feat 브랜치의 최적화된 places 저장 방식 적용
        simplified_places = []
        places = trip_data.get("places", [])
        if places:
            # 일차별로 그룹핑하여 각 일차마다 order를 1부터 시작
            day_counters = {}  # 각 일차별 카운터
            
            for place in places:
                day_number = place.get("dayNumber", 1)
                
                # 일차별 카운터 관리
                if day_number not in day_counters:
                    day_counters[day_number] = 1
                else:
                    day_counters[day_number] += 1
                
                # 프론트엔드에서 이미 분리된 데이터를 보낸 경우
                if place.get("table_name") and place.get("id"):
                    table_name = place.get("table_name", "")
                    actual_id = place.get("id", "")
                else:
                    # 아직 분리되지 않은 데이터를 보낸 경우 (레거시 호환성)
                    place_id = place.get("id", "")
                    table_name = ""
                    actual_id = ""
                    if "_" in place_id:
                        parts = place_id.rsplit("_", 1)  # 마지막 언더스코어로 분리
                        if len(parts) == 2:
                            table_name = parts[0]
                            actual_id = parts[1]
                
                simplified_place = {
                    "table_name": table_name,
                    "id": actual_id,
                    "dayNumber": day_number,
                    "order": day_counters[day_number],  # 일차별로 1부터 시작
                    "isLocked": place.get("isLocked", False)  # 잠금 상태 추가
                }
                simplified_places.append(simplified_place)
        
        places_json = json.dumps(simplified_places) if simplified_places else None
        
        # 날짜 문자열을 datetime으로 변환 (프론트엔드에서 camelCase로 보냄)
        start_date = None
        end_date = None
        
        if trip_data.get("startDate"):
            start_date = datetime.fromisoformat(trip_data["startDate"])
        if trip_data.get("endDate"):
            end_date = datetime.fromisoformat(trip_data["endDate"])
        
        # Trip 생성
        trip = Trip(
            user_id=current_user.user_id,
            title=trip_data.get("title", ""),
            places=places_json,
            start_date=start_date,
            end_date=end_date,
            status="planned",  # 기본 상태 (프론트엔드와 매칭)
            total_budget=trip_data.get("total_budget"),
            cover_image=trip_data.get("cover_image"),
            description=trip_data.get("description")
        )
        
        db.add(trip)
        db.commit()
        db.refresh(trip)
        
        # 캐시 무효화: 해당 사용자의 여행 목록 캐시 삭제
        cache.delete(f"trips:list:{current_user.user_id}:all:0:20")
        cache.delete(f"trips:list:{current_user.user_id}:all:0:10")
        
        # 성공 응답 반환
        return {
            "message": "여행이 성공적으로 저장되었습니다.",
            "trip_id": trip.id,
            "title": trip.title
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.put("/{trip_id}")
async def update_trip(
    trip_id: int,
    trip_data: dict,  # 프론트엔드 데이터를 직접 받음
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """여행 정보 수정"""
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == current_user.user_id
    ).first()
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="여행을 찾을 수 없습니다."
        )
    
    try:
        # feat 브랜치의 최적화된 places 저장 방식 적용 (POST와 동일한 로직)
        simplified_places = []
        places = trip_data.get("places", [])
        if places:
            # 일차별로 그룹핑하여 각 일차마다 order를 1부터 시작
            day_counters = {}  # 각 일차별 카운터
            
            for place in places:
                day_number = place.get("dayNumber", 1)
                
                # 일차별 카운터 관리
                if day_number not in day_counters:
                    day_counters[day_number] = 1
                else:
                    day_counters[day_number] += 1
                
                # 프론트엔드에서 이미 분리된 데이터를 보낸 경우
                if place.get("table_name") and place.get("id"):
                    table_name = place.get("table_name", "")
                    actual_id = place.get("id", "")
                else:
                    # 아직 분리되지 않은 데이터를 보낸 경우 (레거시 호환성)
                    place_id = place.get("id", "")
                    table_name = ""
                    actual_id = ""
                    if "_" in place_id:
                        parts = place_id.rsplit("_", 1)  # 마지막 언더스코어로 분리
                        if len(parts) == 2:
                            table_name = parts[0]
                            actual_id = parts[1]
                
                simplified_place = {
                    "table_name": table_name,
                    "id": actual_id,
                    "dayNumber": day_number,
                    "order": day_counters[day_number],  # 일차별로 1부터 시작
                    "isLocked": place.get("isLocked", False)  # 잠금 상태 추가
                }
                simplified_places.append(simplified_place)
        
        places_json = json.dumps(simplified_places) if simplified_places else None
        
        # 날짜 문자열을 datetime으로 변환 (프론트엔드에서 camelCase로 보냄)
        start_date = None
        end_date = None
        
        if trip_data.get("start_date"):
            start_date = datetime.fromisoformat(trip_data["start_date"])
        if trip_data.get("end_date"):
            end_date = datetime.fromisoformat(trip_data["end_date"])
        
        # Trip 정보 업데이트
        trip.title = trip_data.get("title", trip.title)
        trip.places = places_json
        trip.start_date = start_date if start_date else trip.start_date
        trip.end_date = end_date if end_date else trip.end_date
        trip.total_budget = trip_data.get("total_budget", trip.total_budget)
        trip.cover_image = trip_data.get("cover_image", trip.cover_image)
        trip.description = trip_data.get("description", trip.description)
        
        db.commit()
        db.refresh(trip)
        
        # 캐시 무효화
        cache.delete(f"trip:detail:{current_user.user_id}:{trip_id}")
        cache.delete(f"trips:list:{current_user.user_id}:all:0:20")
        cache.delete(f"trips:list:{current_user.user_id}:all:0:10")
        
        # 성공 응답 반환 (POST와 유사한 형식)
        return {
            "message": "여행이 성공적으로 수정되었습니다.",
            "trip_id": trip.id,
            "title": trip.title
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 수정 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{trip_id}")
async def delete_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """여행 삭제"""
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == current_user.user_id
    ).first()
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="여행을 찾을 수 없습니다."
        )
    
    try:
        db.delete(trip)
        db.commit()
        
        # 캐시 무효화
        cache.delete(f"trip:detail:{current_user.user_id}:{trip_id}")
        cache.delete(f"trips:list:{current_user.user_id}:all:0:20")
        cache.delete(f"trips:list:{current_user.user_id}:all:0:10")
        
        return {"message": "여행이 삭제되었습니다."}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 삭제 중 오류가 발생했습니다: {str(e)}"
        )


@router.patch("/{trip_id}/status")
async def update_trip_status(
    trip_id: int,
    status: TripStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """여행 상태 변경"""
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == current_user.user_id
    ).first()
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="여행을 찾을 수 없습니다."
        )
    
    try:
        trip.status = status.value
        db.commit()
        db.refresh(trip)
        
        # 캐시 무효화
        cache.delete(f"trip:detail:{current_user.user_id}:{trip_id}")
        cache.delete(f"trips:list:{current_user.user_id}:all:0:20")
        cache.delete(f"trips:list:{current_user.user_id}:all:0:10")
        
        return {"message": f"여행 상태가 {status.value}로 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 상태 변경 중 오류가 발생했습니다: {str(e)}"
        )