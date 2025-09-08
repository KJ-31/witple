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
    # 사용자의 여행 취향 정보도 함께 가져오기
    user_preference = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.user_id
    ).first()
    
    # UserResponse 객체 생성 시 여행 취향 정보 포함
    user_data = {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "name": current_user.name,
        "age": current_user.age,
        "nationality": current_user.nationality,
        "profile_image": current_user.profile_image,
        "created_at": current_user.created_at,
        "persona": user_preference.persona if user_preference else None,
        "priority": user_preference.priority if user_preference else None,
        "accommodation": user_preference.accommodation if user_preference else None,
        "exploration": user_preference.exploration if user_preference else None
    }
    
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
        
        # 데이터베이스 업데이트
        current_user.profile_image = image_url
        current_user.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Profile image updated for user: {current_user.user_id}")
        return current_user
        
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
        # 업데이트할 필드들
        if profile_data.name is not None:
            current_user.name = profile_data.name
        if profile_data.age is not None:
            current_user.age = profile_data.age
        if profile_data.nationality is not None:
            current_user.nationality = profile_data.nationality
            
        current_user.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Profile info updated for user: {current_user.user_id}")
        return current_user
        
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
        current_user.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Profile preferences updated for user: {current_user.user_id}")
        return current_user
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"여행 취향 업데이트 중 오류 발생: {str(e)}"
        )