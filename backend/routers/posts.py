import os
import base64
import uuid
from datetime import datetime
from typing import List
import boto3
from botocore.exceptions import ClientError
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from database import get_db
from models import Post, User, OAuthAccount
from schemas import PostCreate, PostResponse, PostListResponse
from config import settings
from auth_utils import get_current_user

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(tags=["posts"])

# S3 클라이언트 초기화
s3_client_config = {
    'region_name': settings.AWS_REGION
}

# AWS 자격 증명이 환경변수에 있으면 사용 (Access Key 방식)
if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
    s3_client_config['aws_access_key_id'] = os.getenv('AWS_ACCESS_KEY_ID')
    s3_client_config['aws_secret_access_key'] = os.getenv('AWS_SECRET_ACCESS_KEY')
    logger.info("Using AWS Access Key credentials for S3")

# VPC 엔드포인트 설정 제거 - 직접 S3 연결 사용
# if os.getenv('AWS_S3_ENDPOINT_URL'):
#     s3_client_config['endpoint_url'] = os.getenv('AWS_S3_ENDPOINT_URL')

s3_client = boto3.client('s3', **s3_client_config)


def save_image_to_s3(base64_data: str, filename: str) -> str:
    """Base64 데이터를 S3에 업로드하고 URL을 반환합니다."""
    try:
        # Base64 헤더 제거 (data:image/jpeg;base64, 등)
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        # Base64 디코딩
        image_data = base64.b64decode(base64_data)
        
        # S3에 업로드
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=f"posts/{filename}",
            Body=image_data,
            ContentType='image/jpeg'
            # ACL 제거: 버킷에서 ACL이 비활성화되어 있음
        )
        
        # S3 URL 반환
        s3_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/posts/{filename}"
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


@router.post("/", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """새 포스트를 생성합니다."""
    try:
        # JWT 토큰에서 가져온 현재 사용자 사용
        user = current_user
        logger.info(f"Creating post for user: {user.user_id} ({user.email})")
        
        # 고유한 파일명 생성
        file_extension = "jpg"  # 실제로는 이미지 데이터에서 확장자 추출해야 함
        filename = f"{uuid.uuid4()}.{file_extension}"
        
        # 이미지 저장
        image_url = save_image_to_s3(post_data.image_data, filename)
        
        # 포스트 생성
        db_post = Post(
            user_id=user.user_id,
            caption=post_data.caption,
            image_url=image_url,
            location=post_data.location
        )
        
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        
        # 사용자 정보와 함께 반환
        post_with_user = db.query(Post).options(joinedload(Post.user)).filter(Post.id == db_post.id).first()
        
        return post_with_user
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"포스트 생성 중 오류 발생: {str(e)}"
        )


@router.get("/", response_model=PostListResponse)
async def get_posts(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """포스트 목록을 가져옵니다."""
    try:
        # 최신 순으로 포스트 조회 (OAuth 계정 정보도 함께 로드)
        posts = (
            db.query(Post)
            .options(
                joinedload(Post.user).joinedload(User.oauth_accounts)
            )
            .order_by(desc(Post.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        total = db.query(Post).count()
        
        # 디버깅: OAuth 계정 정보 로깅
        if posts:
            logger.info(f"=== 포스트 조회 디버깅 ===")
            logger.info(f"전체 포스트 수: {len(posts)}")
            first_post = posts[0]
            logger.info(f"첫 번째 포스트 ID: {first_post.id}")
            logger.info(f"첫 번째 포스트 사용자: {first_post.user.email}")
            logger.info(f"OAuth 계정 수: {len(first_post.user.oauth_accounts)}")
            for oauth_account in first_post.user.oauth_accounts:
                logger.info(f"OAuth 계정: provider={oauth_account.provider}, profile_picture={oauth_account.profile_picture}")
            logger.info(f"========================")
        
        return PostListResponse(posts=posts, total=total)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"포스트 조회 중 오류 발생: {str(e)}"
        )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    """특정 포스트를 가져옵니다."""
    post = (
        db.query(Post)
        .options(joinedload(Post.user))
        .filter(Post.id == post_id)
        .first()
    )
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="포스트를 찾을 수 없습니다."
        )
    
    return post


@router.post("/{post_id}/like")
async def like_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    """포스트에 좋아요를 추가합니다."""
    post = db.query(Post).filter(Post.id == post_id).first()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="포스트를 찾을 수 없습니다."
        )
    
    post.likes_count += 1
    db.commit()
    
    return {"message": "좋아요가 추가되었습니다.", "likes_count": post.likes_count}


@router.delete("/{post_id}/like")
async def unlike_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    """포스트에서 좋아요를 제거합니다."""
    post = db.query(Post).filter(Post.id == post_id).first()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="포스트를 찾을 수 없습니다."
        )
    
    if post.likes_count > 0:
        post.likes_count -= 1
        db.commit()
    
    return {"message": "좋아요가 제거되었습니다.", "likes_count": post.likes_count}