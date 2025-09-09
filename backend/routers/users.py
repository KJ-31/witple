from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from database import get_db
from models import User, UserPreference, UserPreferenceTag
from schemas import UserResponse, UserPreferencesBasic
from auth_utils import get_current_user

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def read_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/preferences", response_model=UserPreferencesBasic)
async def save_user_preferences(
    preferences: UserPreferencesBasic,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save or update user travel preferences"""
    
    # Check if user already has preferences
    existing_prefs = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.user_id
    ).first()
    
    if existing_prefs:
        # Update existing preferences
        existing_prefs.persona = preferences.persona.value
        existing_prefs.priority = preferences.priority.value
        existing_prefs.accommodation = preferences.accommodation.value
        existing_prefs.exploration = preferences.exploration.value
        existing_prefs.updated_at = datetime.now()
        db_prefs = existing_prefs
    else:
        # Create new preferences
        db_prefs = UserPreference(
            user_id=current_user.user_id,
            persona=preferences.persona.value,
            priority=preferences.priority.value,
            accommodation=preferences.accommodation.value,
            exploration=preferences.exploration.value,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(db_prefs)
    
    db.commit()
    db.refresh(db_prefs)
    
    # 기존 사용자 태그 삭제
    db.query(UserPreferenceTag).filter(UserPreferenceTag.user_id == current_user.user_id).delete()
    
    # preference_definitions에서 선택된 옵션들의 태그 조회 및 저장
    preference_options = [
        ('persona', preferences.persona.value),
        ('priority', preferences.priority.value), 
        ('accommodation', preferences.accommodation.value),
        ('exploration', preferences.exploration.value)
    ]
    
    all_tags = []
    for category, option_key in preference_options:
        # preference_definitions 테이블에서 태그 조회
        result = db.execute(
            text("SELECT tags FROM preference_definitions WHERE category = :category AND option_key = :option_key"),
            {"category": category, "option_key": option_key}
        ).fetchone()
        
        if result and result[0]:  # tags 배열이 존재하면
            tags = result[0]  # PostgreSQL array
            for tag in tags:
                all_tags.append(tag)
    
    # 중복 제거하고 태그 저장
    unique_tags = list(set(all_tags))
    for tag in unique_tags:
        tag_obj = UserPreferenceTag(
            user_id=current_user.user_id,
            tag=tag,
            weight=1,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(tag_obj)
    
    db.commit()
    
    # Return the saved preferences
    return UserPreferencesBasic(
        persona=preferences.persona,
        priority=preferences.priority,
        accommodation=preferences.accommodation,
        exploration=preferences.exploration
    )


@router.get("/preferences", response_model=Optional[UserPreferencesBasic])
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user travel preferences"""
    
    prefs = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.user_id
    ).first()
    
    if not prefs:
        return None
    
    return UserPreferencesBasic(
        persona=prefs.persona,
        priority=prefs.priority,
        accommodation=prefs.accommodation,
        exploration=prefs.exploration
    )


@router.get("/preferences/check")
async def check_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if user has travel preferences set"""
    
    prefs = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.user_id
    ).first()
    
    return {
        "has_preferences": prefs is not None,
        "user_id": current_user.user_id
    }
