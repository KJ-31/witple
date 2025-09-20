import os
import base64
import uuid
from datetime import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from database import get_db
from models import User, UserPreference, UserPreferenceTag
from sqlalchemy import text
from schemas import (
    UserResponse,
    ProfileImageUpdate,
    ProfileInfoUpdate,
    ProfilePreferencesUpdate
)
from config import settings
from auth_utils import get_current_user, get_current_user_optional
from cache_utils import cache

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])

# S3 클라이언트 초기화 (posts.py와 동일한 설정)
s3_client_config = {
    'region_name': settings.AWS_REGION
}

if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
    s3_client_config['aws_access_key_id'] = os.getenv('AWS_ACCESS_KEY_ID')
    s3_client_config['aws_secret_access_key'] = os.getenv('AWS_SECRET_ACCESS_KEY')
    logger.info("Using AWS Access Key credentials for S3")

s3_client = boto3.client('s3', **s3_client_config)


def save_profile_image_to_s3(base64_data: str, user_id: str) -> str:
    """Base64 프로필 이미지를 S3에 업로드하고 URL을 반환합니다."""
    try:
        # Base64 헤더 제거
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]

        # Base64 디코딩
        image_data = base64.b64decode(base64_data)

        # 고유한 파일명 생성
        filename = f"profile_{user_id}_{uuid.uuid4()}.jpg"

        # S3에 업로드
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=f"profiles/{filename}",
            Body=image_data,
            ContentType='image/jpeg'
            # ACL 제거: 버킷에서 ACL이 비활성화되어 있음
        )

        # S3 URL 반환
        s3_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/profiles/{filename}"
        return s3_url

    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"S3 업로드 중 오류 발생: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"이미지 처리 중 오류 발생: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 사용자의 프로필 정보를 가져옵니다."""
    try:
        # 캐시 키 생성
        cache_key = f"profile:{current_user.user_id}"

        # 캐시에서 조회 시도
        try:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for profile: {cache_key}")
                return UserResponse(**cached_result)
        except Exception as cache_error:
            logger.warning(f"Cache retrieval failed: {cache_error}")

        logger.info(f"Cache miss for profile: {cache_key}")

        # 사용자의 여행 취향 정보도 함께 가져오기
        user_preference = db.query(UserPreference).filter(
            UserPreference.user_id == current_user.user_id
        ).first()

        # UserResponse 객체 생성 시 여행 취향 정보 포함 (안전한 처리)
        user_data = {
            "user_id": str(current_user.user_id) if current_user.user_id else "",
            "email": str(current_user.email) if current_user.email else "",
            "name": current_user.name,
            "age": current_user.age,
            "nationality": current_user.nationality,
            "profile_image": current_user.profile_image,
            "created_at": None,
            "persona": user_preference.persona if user_preference else None,
            "priority": user_preference.priority if user_preference else None,
            "accommodation": user_preference.accommodation if user_preference else None,
            "exploration": user_preference.exploration if user_preference else None
        }

        # created_at 안전한 처리
        try:
            if current_user.created_at:
                if hasattr(current_user.created_at, 'isoformat'):
                    user_data["created_at"] = current_user.created_at.isoformat()
                else:
                    user_data["created_at"] = str(current_user.created_at)
        except Exception as date_error:
            logger.warning(f"Date conversion failed: {date_error}")

        # 결과를 캐시에 저장 (20분)
        try:
            cache.set(cache_key, user_data, timeout=1200)
        except Exception as cache_error:
            logger.warning(f"Cache storage failed: {cache_error}")

        return UserResponse(**user_data)

    except Exception as e:
        logger.error(f"❌ Error in get_current_user_profile: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로필 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """다른 사용자의 공개 프로필 정보를 조회합니다."""
    # 캐시 키 생성
    cache_key = f"profile:public:{user_id}"

    # 캐시에서 조회 시도
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.info(f"Cache hit for public profile: {cache_key}")
        return UserResponse(**cached_result)

    # 사용자 정보 조회
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )

    # 사용자 취향 정보 조회
    user_preference = db.query(UserPreference).filter(
        UserPreference.user_id == user_id
    ).first()

    # 공개 프로필 데이터 구성 (민감한 정보 제외)
    user_data = {
        "user_id": user.user_id,
        "email": user.email,  # 이메일은 공개 정보로 포함
        "name": user.name,
        "age": user.age,
        "nationality": user.nationality,
        "profile_image": user.profile_image,
        "created_at": user.created_at.isoformat() if hasattr(user.created_at, 'isoformat') and user.created_at else str(user.created_at) if user.created_at else None,
        "persona": user_preference.persona if user_preference else None,
        "priority": user_preference.priority if user_preference else None,
        "accommodation": user_preference.accommodation if user_preference else None,
        "exploration": user_preference.exploration if user_preference else None
    }

    # 결과를 캐시에 저장 (10분 - 다른 사용자 프로필이므로 짧게)
    cache.set(cache_key, user_data, expire=600)

    return UserResponse(**user_data)


@router.put("/image", response_model=UserResponse)
async def update_profile_image(
    image_data: ProfileImageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """프로필 이미지를 업데이트합니다."""
    try:
        # 이미지를 S3에 업로드
        image_url = save_profile_image_to_s3(image_data.image_data, current_user.user_id)

        # DB에서 사용자 객체를 다시 조회하여 세션에 연결
        user = db.query(User).filter(User.user_id == current_user.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다."
            )

        # 데이터베이스 업데이트
        user.profile_image = image_url
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        # 캐시 무효화
        cache.delete(f"profile:{current_user.user_id}")
        cache.delete(f"user_session:{current_user.email}")  # 사용자 세션 캐시도 무효화

        logger.info(f"Profile image updated for user: {current_user.user_id}")
        return user

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로필 이미지 업데이트 중 오류 발생: {str(e)}"
        )


@router.put("/info", response_model=UserResponse)
async def update_profile_info(
    profile_data: ProfileInfoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """기본 프로필 정보를 업데이트합니다."""
    try:
        # DB에서 사용자 객체를 다시 조회하여 세션에 연결
        user = db.query(User).filter(User.user_id == current_user.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다."
            )

        # 업데이트할 필드들
        if profile_data.name is not None:
            user.name = profile_data.name
        if profile_data.age is not None:
            user.age = profile_data.age
        if profile_data.nationality is not None:
            user.nationality = profile_data.nationality

        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        # 캐시 무효화
        cache.delete(f"profile:{current_user.user_id}")
        cache.delete(f"user_session:{current_user.email}")  # 사용자 세션 캐시도 무효화

        logger.info(f"Profile info updated for user: {current_user.user_id}")
        return user

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로필 정보 업데이트 중 오류 발생: {str(e)}"
        )


@router.put("/preferences", response_model=UserResponse)
async def update_profile_preferences(
    preferences_data: ProfilePreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사용자 여행 취향 정보를 업데이트합니다."""
    try:
        # DB에서 사용자 객체를 다시 조회하여 세션에 연결
        user = db.query(User).filter(User.user_id == current_user.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다."
            )

        # 기존 preferences 찾거나 새로 생성
        user_preference = db.query(UserPreference).filter(
            UserPreference.user_id == current_user.user_id
        ).first()

        if not user_preference:
            user_preference = UserPreference(user_id=current_user.user_id)
            db.add(user_preference)

        # 업데이트할 필드들
        if preferences_data.persona is not None:
            user_preference.persona = preferences_data.persona
        if preferences_data.priority is not None:
            user_preference.priority = preferences_data.priority
        if preferences_data.accommodation is not None:
            user_preference.accommodation = preferences_data.accommodation
        if preferences_data.exploration is not None:
            user_preference.exploration = preferences_data.exploration

        user_preference.updated_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()

        # 우선순위가 변경된 경우 태그 가중치 재생성
        if preferences_data.priority is not None:
            # 기존 사용자 태그 삭제
            db.query(UserPreferenceTag).filter(UserPreferenceTag.user_id == current_user.user_id).delete()

            # preference_definitions에서 모든 선호도 옵션의 태그 조회
            preference_options = [
                ('persona', preferences_data.persona or user_preference.persona),
                ('priority', preferences_data.priority or user_preference.priority),
                ('accommodation', preferences_data.accommodation or user_preference.accommodation),
                ('exploration', preferences_data.exploration or user_preference.exploration)
            ]

            all_tags = []
            for category, option_key in preference_options:
                if option_key:  # None이 아닌 경우만
                    # preference_definitions 테이블에서 태그 조회
                    result = db.execute(
                        text("SELECT tags FROM preference_definitions WHERE category = :category AND option_key = :option_key"),
                        {"category": category, "option_key": option_key}
                    ).fetchone()

                    if result and result[0]:  # tags 배열이 존재하면
                        tags = result[0]  # PostgreSQL array
                        for tag in tags:
                            all_tags.append(tag)

            # 중복 제거하고 우선순위 기반 가중치로 태그 저장
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
            user_priority = preferences_data.priority or user_preference.priority
            priority_tag_weights = priority_weights.get(user_priority, {})

            for tag in unique_tags:
                # 우선순위와 일치하는 태그는 높은 가중치, 나머지는 기본값
                if tag in priority_tag_weights:
                    weight = priority_tag_weights[tag]
                    logger.info(f"Profile: 우선순위 태그 '{tag}' -> weight={weight} (사용자 우선순위: {user_priority})")
                else:
                    weight = 1  # 기본 가중치

                tag_obj = UserPreferenceTag(
                    user_id=current_user.user_id,
                    tag=tag,
                    weight=weight,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(tag_obj)

            logger.info(f"Profile: 사용자 {current_user.user_id} 태그 가중치 재생성 완료 - {len(unique_tags)}개 태그")

        db.commit()
        db.refresh(user)

        # 캐시 무효화
        cache.delete(f"profile:{current_user.user_id}")
        cache.delete(f"user_session:{current_user.email}")  # 사용자 세션 캐시도 무효화

        # 변경된 여행 취향 정보 로그 출력
        logger.info(f"여행 취향 업데이트 성공: {{user_id: '{current_user.user_id}', email: '{current_user.email}', name: '{current_user.name}', persona: '{user_preference.persona}', priority: '{user_preference.priority}', accommodation: '{user_preference.accommodation}', exploration: '{user_preference.exploration}', updated_at: '{user_preference.updated_at}'}}")

        # 캐시 무효화 - 사용자 취향 변경 시 추천 캐시 삭제
        user_id = str(current_user.user_id)

        # 개인화 추천 캐시 삭제 (다양한 파라미터 조합)
        cache_patterns = [
            f"personalized:{user_id}:*",
            f"recommendations:{user_id}",
            f"user:{user_id}",
            f"rec_main:user_{user_id}:*",      # 메인 페이지 개인화 추천
            f"main_personalized:user_{user_id}:*",  # 메인 페이지 전체 응답
            f"main_explore:user_{user_id}:*",       # 메인 페이지 탐색 섹션
            f"explore_feed_v3:{user_id}:*"          # 탐색 피드 v3
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

        logger.info(f"Profile preferences updated for user: {current_user.user_id}")
        return user

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 취향 업데이트 중 오류 발생: {str(e)}"
        )