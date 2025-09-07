from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json

from database import get_db
from auth_utils import get_current_user
from models import Trip, User


router = APIRouter()


class TripCreate(BaseModel):
    title: str
    description: Optional[str] = None
    places: Optional[List[dict]] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    days: Optional[int] = None


class TripResponse(BaseModel):
    id: int
    user_id: str
    title: str
    description: Optional[str]
    places: Optional[str]  # text 타입으로 변경
    start_date: Optional[datetime]  # datetime 타입으로 변경
    end_date: Optional[datetime]    # datetime 타입으로 변경
    status: Optional[str]
    total_budget: Optional[int]
    cover_image: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.post("/", response_model=TripResponse)
async def create_trip(
    trip_data: TripCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    새 여행 일정을 생성합니다.
    """
    try:
        # places를 최소한의 정보만 저장 (효율적인 방식)
        simplified_places = []
        if trip_data.places:
            for i, place in enumerate(trip_data.places, 1):
                place_id = place.get("id", "")
                
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
                    "dayNumber": place.get("dayNumber", 1),
                    "order": i
                }
                simplified_places.append(simplified_place)
        
        places_json = json.dumps(simplified_places) if simplified_places else None
        
        # 날짜 문자열을 datetime 객체로 변환
        start_date = datetime.fromisoformat(trip_data.startDate) if trip_data.startDate else None
        end_date = datetime.fromisoformat(trip_data.endDate) if trip_data.endDate else None
        
        # 새로운 Trip 객체 생성
        db_trip = Trip(
            user_id=current_user.user_id,
            title=trip_data.title,
            description=trip_data.description,
            places=places_json,
            start_date=start_date,
            end_date=end_date,
            status="planning"  # 기본 상태
        )
        
        # 데이터베이스에 저장
        db.add(db_trip)
        db.commit()
        db.refresh(db_trip)
        
        return db_trip
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 일정 저장 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/", response_model=List[TripResponse])
async def get_user_trips(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    현재 사용자의 모든 여행 일정을 가져옵니다.
    """
    trips = db.query(Trip).filter(Trip.user_id == current_user.user_id).all()
    return trips


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    특정 여행 일정을 가져옵니다.
    """
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == current_user.user_id
    ).first()
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="여행 일정을 찾을 수 없습니다."
        )
    
    return trip


@router.delete("/{trip_id}")
async def delete_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    여행 일정을 삭제합니다.
    """
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == current_user.user_id
    ).first()
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="여행 일정을 찾을 수 없습니다."
        )
    
    db.delete(trip)
    db.commit()
    
    return {"message": "여행 일정이 삭제되었습니다."}