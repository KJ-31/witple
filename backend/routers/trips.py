from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from database import get_db
from models import Trip, User
from schemas import TripCreate, TripResponse, TripListResponse, TripStatus
from routers.auth import get_current_user

router = APIRouter()


@router.get("/", response_model=TripListResponse)
async def get_user_trips(
    status_filter: Optional[TripStatus] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사용자의 여행 목록 조회"""
    query = db.query(Trip).filter(Trip.user_id == current_user.user_id)
    
    if status_filter:
        query = query.filter(Trip.status == status_filter.value)
    
    trips = query.offset(offset).limit(limit).all()
    total = query.count()
    
    # places JSON 필드 파싱
    for trip in trips:
        if trip.places:
            trip.places = json.loads(trip.places)
        else:
            trip.places = []
    
    return TripListResponse(trips=trips, total=total)


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 여행 상세 조회"""
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == current_user.user_id
    ).first()
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="여행을 찾을 수 없습니다."
        )
    
    # places JSON 필드 파싱
    if trip.places:
        trip.places = json.loads(trip.places)
    else:
        trip.places = []
    
    return trip


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
                place_id = place.get("id", "")
                day_number = place.get("dayNumber", 1)
                
                # 일차별 카운터 관리
                if day_number not in day_counters:
                    day_counters[day_number] = 1
                else:
                    day_counters[day_number] += 1
                
                # id에서 테이블명과 실제 ID 분리 (예: leisure_sports_950 -> leisure_sports, 950)
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
                    "order": day_counters[day_number]  # 일차별로 1부터 시작
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
            status="planning",  # 기본 상태
            total_budget=trip_data.get("total_budget"),
            cover_image=trip_data.get("cover_image"),
            description=trip_data.get("description")
        )
        
        db.add(trip)
        db.commit()
        db.refresh(trip)
        
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


@router.put("/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: int,
    trip_data: TripCreate,
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
        # feat 브랜치의 최적화된 places 저장 방식 적용
        simplified_places = []
        if trip_data.places:
            day_counters = {}
            
            for place in trip_data.places:
                place_dict = place.dict() if hasattr(place, 'dict') else place
                
                place_id = place_dict.get("id", "")
                day_number = place_dict.get("dayNumber", 1)
                
                if day_number not in day_counters:
                    day_counters[day_number] = 1
                else:
                    day_counters[day_number] += 1
                
                table_name = ""
                actual_id = ""
                if "_" in place_id:
                    parts = place_id.rsplit("_", 1)
                    if len(parts) == 2:
                        table_name = parts[0]
                        actual_id = parts[1]
                
                simplified_place = {
                    "table_name": table_name,
                    "id": actual_id,
                    "dayNumber": day_number,
                    "order": day_counters[day_number]
                }
                simplified_places.append(simplified_place)
        
        places_json = json.dumps(simplified_places) if simplified_places else None
        
        # Trip 정보 업데이트
        trip.title = trip_data.title
        trip.places = places_json
        trip.start_date = trip_data.start_date
        trip.end_date = trip_data.end_date
        trip.status = trip_data.status.value if hasattr(trip_data, 'status') and trip_data.status else trip.status
        trip.total_budget = trip_data.total_budget if hasattr(trip_data, 'total_budget') else trip.total_budget
        trip.cover_image = trip_data.cover_image if hasattr(trip_data, 'cover_image') else trip.cover_image
        trip.description = trip_data.description
        
        db.commit()
        db.refresh(trip)
        
        # places를 파싱하여 반환
        if trip.places:
            trip.places = json.loads(trip.places)
        else:
            trip.places = []
        
        return trip
        
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
        
        return {"message": f"여행 상태가 {status.value}로 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 상태 변경 중 오류가 발생했습니다: {str(e)}"
        )