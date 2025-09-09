import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import SavedLocation, User
from schemas import SavedLocationCreate, SavedLocationResponse, SavedLocationListResponse
from auth_utils import get_current_user

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(tags=["saved-locations"])


@router.post("/", response_model=SavedLocationResponse)
async def create_saved_location(
    location_data: SavedLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """새 저장된 장소를 생성합니다."""
    try:
        # 중복 체크 (같은 사용자의 같은 places)
        existing_location = (
            db.query(SavedLocation)
            .filter(
                SavedLocation.user_id == current_user.user_id,
                SavedLocation.places == location_data.places
            )
            .first()
        )
        
        if existing_location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 저장된 장소입니다."
            )
        
        # 저장된 장소 생성
        db_location = SavedLocation(
            user_id=current_user.user_id,
            places=location_data.places
        )
        
        db.add(db_location)
        db.commit()
        db.refresh(db_location)
        
        logger.info(f"저장된 장소 생성: {db_location.places} for user {current_user.user_id}")
        return db_location
        
    except Exception as e:
        db.rollback()
        logger.error(f"저장된 장소 생성 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"저장된 장소 생성 중 오류 발생: {str(e)}"
        )


@router.get("/", response_model=SavedLocationListResponse)
async def get_saved_locations(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 사용자의 저장된 장소 목록을 가져옵니다."""
    try:
        # 최신 순으로 저장된 장소 조회
        locations = (
            db.query(SavedLocation)
            .filter(SavedLocation.user_id == current_user.user_id)
            .order_by(desc(SavedLocation.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        total = (
            db.query(SavedLocation)
            .filter(SavedLocation.user_id == current_user.user_id)
            .count()
        )
        
        return SavedLocationListResponse(locations=locations, total=total)
        
    except Exception as e:
        logger.error(f"저장된 장소 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"저장된 장소 조회 중 오류 발생: {str(e)}"
        )


@router.get("/{location_id}", response_model=SavedLocationResponse)
async def get_saved_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 저장된 장소를 가져옵니다."""
    location = (
        db.query(SavedLocation)
        .filter(
            SavedLocation.id == location_id,
            SavedLocation.user_id == current_user.user_id
        )
        .first()
    )
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="저장된 장소를 찾을 수 없습니다."
        )
    
    return location


@router.put("/{location_id}", response_model=SavedLocationResponse)
async def update_saved_location(
    location_id: int,
    location_data: SavedLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """저장된 장소를 수정합니다."""
    try:
        # 장소 조회
        location = (
            db.query(SavedLocation)
            .filter(
                SavedLocation.id == location_id,
                SavedLocation.user_id == current_user.user_id
            )
            .first()
        )
        
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="저장된 장소를 찾을 수 없습니다."
            )
        
        # 장소 정보 업데이트
        location.places = location_data.places
        
        db.commit()
        db.refresh(location)
        
        logger.info(f"저장된 장소 수정: {location.places} for user {current_user.user_id}")
        return location
        
    except Exception as e:
        db.rollback()
        logger.error(f"저장된 장소 수정 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"저장된 장소 수정 중 오류 발생: {str(e)}"
        )


@router.delete("/{location_id}")
async def delete_saved_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """저장된 장소를 삭제합니다."""
    try:
        # 장소 조회
        location = (
            db.query(SavedLocation)
            .filter(
                SavedLocation.id == location_id,
                SavedLocation.user_id == current_user.user_id
            )
            .first()
        )
        
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="저장된 장소를 찾을 수 없습니다."
            )
        
        # 장소 삭제
        db.delete(location)
        db.commit()
        
        logger.info(f"저장된 장소 삭제: {location.places} for user {current_user.user_id}")
        return {"message": "저장된 장소가 삭제되었습니다."}
        
    except Exception as e:
        db.rollback()
        logger.error(f"저장된 장소 삭제 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"저장된 장소 삭제 중 오류 발생: {str(e)}"
        )


@router.post("/check")
async def check_saved_location(
    location_data: SavedLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """장소가 이미 저장되었는지 확인합니다."""
    try:
        existing_location = (
            db.query(SavedLocation)
            .filter(
                SavedLocation.user_id == current_user.user_id,
                SavedLocation.places == location_data.places
            )
            .first()
        )
        
        return {
            "is_saved": existing_location is not None,
            "location_id": existing_location.id if existing_location else None
        }
        
    except Exception as e:
        logger.error(f"저장된 장소 확인 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"저장된 장소 확인 중 오류 발생: {str(e)}"
        )