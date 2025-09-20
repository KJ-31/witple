from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from database import get_db
from models import User, UserPreference, UserPreferenceTag
from schemas import UserResponse, UserPreferencesBasic
from auth_utils import get_current_user
from cache_utils import cache
import logging

logger = logging.getLogger(__name__)
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
    
    # 중복 제거하고 태그 저장 (우선순위 기반 가중치 적용)
    unique_tags = list(set(all_tags))

    # 우선순위별 태그 가중치 매핑 (초강력 편향)
    priority_weights = {
        'restaurants': {'맛집': 10, '음식': 9, '레스토랑': 10, '카페': 8, '요리': 8,
                       '전통음식': 9, '고급음식': 9, '미식': 10, '다이닝': 8, '음식투자': 7},
        'nature': {'자연': 10, '산': 9, '바다': 9, '호수': 8, '공원': 7, '숲': 8,
                  '하이킹': 8, '트레킹': 9, '경치': 7, '풍경': 7},
        'culture': {'문화': 10, '역사': 9, '박물관': 9, '미술관': 8, '전통': 9,
                   '절': 8, '궁궐': 9, '문화체험': 8, '유적': 7, '예술': 7},
        'shopping': {'쇼핑': 10, '마트': 6, '백화점': 8, '아울렛': 9, '시장': 7,
                    '상가': 6, '패션': 7, '브랜드': 8},
        'accommodation': {'숙박': 10, '호텔': 9, '리조트': 8, '펜션': 7, '한옥': 9,
                         '전통': 8, '럭셔리': 8, '편안한': 7}
    }

    # 현재 사용자의 우선순위 가져오기
    user_priority = preferences.priority.value
    priority_tag_weights = priority_weights.get(user_priority, {})

    for tag in unique_tags:
        # 우선순위와 일치하는 태그는 높은 가중치, 나머지는 기본값
        if tag in priority_tag_weights:
            weight = priority_tag_weights[tag]
            logger.info(f"우선순위 태그 '{tag}' -> weight={weight} (사용자 우선순위: {user_priority})")
        else:
            weight = 1  # 기본 가중치

        tag_obj = UserPreferenceTag(
            user_id=current_user.user_id,
            tag=tag,
            weight=weight,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(tag_obj)
    
    db.commit()
    
    # 저장된 여행 취향 정보 로그 출력
    logger.info(f"여행 취향 업데이트 성공: {{user_id: '{current_user.user_id}', email: '{current_user.email}', name: '{current_user.name}', persona: '{db_prefs.persona}', priority: '{db_prefs.priority}', accommodation: '{db_prefs.accommodation}', exploration: '{db_prefs.exploration}', saved_tags: {len(unique_tags)}, updated_at: '{db_prefs.updated_at}'}}")
    
    # 캐시 무효화 - 사용자 취향 변경 시 추천 캐시 삭제
    user_id = str(current_user.user_id)
    
    # 개인화 추천 캐시 삭제 (모든 우선순위 태그 조합 포함) - 개선됨
    cache_patterns = [
        f"personalized:{user_id}:*",
        f"recommendations:{user_id}",
        f"user:{user_id}",
        f"rec_main:user_{user_id}:*",           # 메인 페이지 개인화 추천 (모든 우선순위 태그)
        f"main_personalized:user_{user_id}:*", # 메인 페이지 전체 응답 (모든 우선순위 태그)
        f"main_explore:user_{user_id}:*",      # 메인 페이지 탐색 섹션 (모든 우선순위 태그)
        f"explore_feed_v3:{user_id}:*",        # 탐색 피드 v3 (모든 우선순위 태그)
        f"explore_section:user_{user_id}:*"    # 개별 섹션 캐시 (모든 우선순위 태그)
    ]
    
    # Redis SCAN을 사용하여 패턴 매칭 키들 삭제
    try:
        import redis
        redis_client = cache.redis
        
        for pattern in cache_patterns:
            for key in redis_client.scan_iter(match=pattern):
                redis_client.delete(key)
                logger.info(f"Deleted cache key: {key}")
                
        logger.info(f"Cache invalidated for user preferences update: {user_id}")
    except Exception as cache_error:
        logger.warning(f"Cache invalidation failed: {cache_error}")
    
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
