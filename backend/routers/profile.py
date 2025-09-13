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
from models import User, UserPreference
from schemas import (
    UserResponse, 
    ProfileImageUpdate, 
    ProfileInfoUpdate, 
    ProfilePreferencesUpdate
)
from config import settings
from auth_utils import get_current_user
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
        
        # 캐시에서 조회 시도 (캐시 오류 시 무시하고 계속 진행)
        cached_result = None
        try:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for profile: {cache_key}")
                return UserResponse(**cached_result)
        except Exception as cache_error:
            logger.warning(f"Cache read error for {cache_key}: {cache_error}")
        
        logger.info(f"Cache miss for profile: {cache_key}")
        
        # 사용자의 여행 취향 정보도 함께 가져오기
        user_preference = None
        try:
            user_preference = db.query(UserPreference).filter(
                UserPreference.user_id == current_user.user_id
            ).first()
        except Exception as db_error:
            logger.warning(f"Database query error for user preferences: {db_error}")
        
        # created_at 필드 안전하게 처리
        created_at_str = None
        if current_user.created_at:
            if hasattr(current_user.created_at, 'isoformat'):
                # datetime 객체인 경우
                created_at_str = current_user.created_at.isoformat()
            else:
                # 이미 문자열인 경우
                created_at_str = str(current_user.created_at)
        
        # UserResponse 객체 생성 시 여행 취향 정보 포함
        user_data = {
            "user_id": current_user.user_id,
            "email": current_user.email,
            "name": current_user.name,
            "age": current_user.age,
            "nationality": current_user.nationality,
            "profile_image": current_user.profile_image,
            "created_at": created_at_str,
            "persona": user_preference.persona if user_preference else None,
            "priority": user_preference.priority if user_preference else None,
            "accommodation": user_preference.accommodation if user_preference else None,
            "exploration": user_preference.exploration if user_preference else None
        }
        
        # 결과를 캐시에 저장 (캐시 오류 시 무시하고 계속 진행)
        try:
            cache.set(cache_key, user_data, expire=1200)
        except Exception as cache_error:
            logger.warning(f"Cache write error for {cache_key}: {cache_error}")
        
        return UserResponse(**user_data)
        
    except Exception as e:
        logger.error(f"Profile API error for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로필 정보 조회 중 오류 발생: {str(e)}"
        )


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
            f"user:{user_id}"
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