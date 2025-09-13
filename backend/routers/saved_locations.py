import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import SavedLocation, User
from schemas import SavedLocationCreate, SavedLocationResponse, SavedLocationListResponse
from auth_utils import get_current_user, get_current_user_optional
from cache_utils import cache

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
        
        # 캐시 무효화: 해당 사용자의 저장된 장소 목록 캐시 삭제
        cache.delete(f"saved_locations:list:{current_user.user_id}:0:20")
        cache.delete(f"saved_locations:list:{current_user.user_id}:0:10")
        
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
        # 캐시 키 생성 (사용자별로 캐시)
        cache_key = f"saved_locations:list:{current_user.user_id}:{skip}:{limit}"
        
        # 캐시에서 조회 시도
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Cache hit for saved locations: {cache_key}")
            return SavedLocationListResponse(**cached_result)
        
        logger.info(f"Cache miss for saved locations: {cache_key}")
        
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
        
        result = SavedLocationListResponse(locations=locations, total=total)
        
        # 결과를 캐시에 저장 (10분)
        cache.set(cache_key, result.dict(), expire=600)
        
        return result
        
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
    # 캐시 키 생성
    cache_key = f"saved_location:detail:{current_user.user_id}:{location_id}"
    
    # 캐시에서 조회 시도
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.info(f"Cache hit for saved location: {cache_key}")
        return SavedLocationResponse(**cached_result)
    
    logger.info(f"Cache miss for saved location: {cache_key}")
    
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
    
    # 결과를 캐시에 저장 (15분)
    location_dict = {
        "id": location.id,
        "user_id": location.user_id,
        "places": location.places,
        "created_at": location.created_at.isoformat() if location.created_at else None,
        "updated_at": location.updated_at.isoformat() if location.updated_at else None
    }
    cache.set(cache_key, location_dict, expire=900)
    
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
        
        # 캐시 무효화
        cache.delete(f"saved_location:detail:{current_user.user_id}:{location_id}")
        cache.delete(f"saved_locations:list:{current_user.user_id}:0:20")
        cache.delete(f"saved_locations:list:{current_user.user_id}:0:10")
        
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
        
        # 캐시 무효화
        cache.delete(f"saved_location:detail:{current_user.user_id}:{location_id}")
        cache.delete(f"saved_locations:list:{current_user.user_id}:0:20")
        cache.delete(f"saved_locations:list:{current_user.user_id}:0:10")
        
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


@router.get("/user/{user_id}", response_model=SavedLocationListResponse)
async def get_user_saved_locations(
    user_id: str,
    page: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """다른 사용자의 공개 저장된 장소 목록을 조회합니다."""
    # 캐시 키 생성
    cache_key = f"saved_locations:public:{user_id}:{page}:{limit}"
    
    # 캐시에서 조회 시도
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.info(f"Cache hit for public saved locations: {cache_key}")
        return SavedLocationListResponse(**cached_result)
    
    # 사용자 존재 확인
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # 해당 사용자의 저장된 장소 목록 조회 (공개 정보만)
    locations = (
        db.query(SavedLocation)
        .filter(SavedLocation.user_id == user_id)
        .order_by(desc(SavedLocation.created_at))
        .offset(page * limit)
        .limit(limit)
        .all()
    )
    
    # 총 개수 조회
    total = db.query(SavedLocation).filter(SavedLocation.user_id == user_id).count()
    
    # 응답 데이터 구성
    location_list = []
    for location in locations:
        location_dict = {
            "id": location.id,
            "user_id": location.user_id,
            "places": location.places,
            "created_at": location.created_at.isoformat() if location.created_at else None,
            "updated_at": location.updated_at.isoformat() if location.updated_at else None
        }
        location_list.append(location_dict)
    
    result = {
        "locations": location_list,
        "total": total,
        "page": page,
        "limit": limit,
        "hasMore": (page + 1) * limit < total
    }
    
    # 결과를 캐시에 저장 (5분 - 다른 사용자 데이터이므로 짧게)
    cache.set(cache_key, result, expire=300)
    
    return SavedLocationListResponse(**result)