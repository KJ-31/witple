import os
import base64
import uuid
import json
from datetime import datetime
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError
import logging
from PIL import Image
import io
import torch
from transformers import CLIPProcessor, CLIPModel

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from pydantic import BaseModel

from database import get_db
from models import Post, User, OAuthAccount, PostLike
from schemas import PostCreate, PostResponse, PostListResponse
from config import settings
from auth_utils import get_current_user
from cache_utils import cache, cached

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])

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

# CLIP 모델 설정 (환경변수로 설정 가능)
CLIP_MODEL_NAME = os.getenv('CLIP_MODEL_NAME', 'ViT-B-32')
CLIP_CHECKPOINT = os.getenv('CLIP_CHECKPOINT', 'laion2b_s34b_b79k')
IMAGE_VECTOR_DIM = int(os.getenv('IMAGE_VECTOR_DIM', '512'))

# CLIP 모델 초기화 (이미지 벡터화용)
clip_model = None
clip_processor = None

def get_clip_model():
    """CLIP 모델을 로드합니다 (지연 로딩)"""
    global clip_model, clip_processor
    if clip_model is None:
        logger.info(f"Loading CLIP model: openai/clip-vit-base-patch32")
        clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        logger.info("CLIP model loaded successfully")
    return clip_model, clip_processor

def vectorize_image(base64_data: str) -> List[float]:
    """Base64 이미지 데이터를 CLIP을 사용해 벡터로 변환합니다."""
    try:
        # Base64 헤더 제거
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]

        # Base64를 이미지로 디코딩
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes))

        # RGB로 변환 (CLIP은 RGB 이미지를 기대)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # CLIP 모델로 이미지 벡터화
        model, processor = get_clip_model()

        # 이미지를 CLIP 모델로 처리
        inputs = processor(images=image, return_tensors="pt")

        # 이미지 특성 추출
        with torch.no_grad():
            image_features = model.get_image_features(**inputs)
            # 벡터를 정규화
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        # numpy 배열로 변환하고 리스트로 변환
        vector = image_features.squeeze().cpu().numpy().tolist()

        # 벡터 차원 확인 및 조정
        if len(vector) > IMAGE_VECTOR_DIM:
            vector = vector[:IMAGE_VECTOR_DIM]  # 설정된 차원으로 트리밍
        elif len(vector) < IMAGE_VECTOR_DIM:
            vector = vector + [0.0] * (IMAGE_VECTOR_DIM - len(vector))  # 제로 패딩

        logger.info(f"Generated image vector with {len(vector)} dimensions (target: {IMAGE_VECTOR_DIM})")
        return vector

    except Exception as e:
        logger.error(f"Error vectorizing image: {str(e)}")
        # 오류 시 제로 벡터 반환 (None보다 나은 처리)
        logger.warning(f"Returning zero vector due to error: {str(e)}")
        return [0.0] * IMAGE_VECTOR_DIM


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
        
        # 이미지 형식 감지 및 고유한 파일명 생성
        image_bytes = base64.b64decode(post_data.image_data.split(',')[1] if ',' in post_data.image_data else post_data.image_data)
        image = Image.open(io.BytesIO(image_bytes))
        image_format = image.format or 'JPEG'
        file_extension = 'jpg' if image_format.upper() == 'JPEG' else image_format.lower()
        filename = f"{uuid.uuid4()}.{file_extension}"

        # 이미지 저장
        image_url = save_image_to_s3(post_data.image_data, filename)

        # 이미지 벡터화 (CLIP)
        logger.info(f"Generating image vector using CLIP (target dimension: {IMAGE_VECTOR_DIM})...")
        image_vector = vectorize_image(post_data.image_data)

        # 벡터화 결과 처리 (이제 항상 벡터가 반환됨)
        if image_vector is not None:
            image_vector_json = json.dumps(image_vector)
            logger.info(f"Image vector generated successfully: {len(image_vector)} dimensions")
        else:
            # 이론적으로 도달하지 않음 (vectorize_image가 항상 벡터 반환)
            logger.error("Unexpected: image_vector is None")
            image_vector_json = json.dumps([0.0] * IMAGE_VECTOR_DIM)

        # 포스트 생성
        db_post = Post(
            user_id=user.user_id,
            caption=post_data.caption,
            image_url=image_url,
            image_vector=image_vector_json,
            location=post_data.location
        )
        
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        
        # 캐시 무효화: 포스트 목록 캐시 삭제
        cache.delete("posts:list:0:10")  # 기본 페이지
        cache.delete("posts:list:0:20")  # 다른 페이지도 삭제 가능
        
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

        # 각 포스트에 기본 좋아요 상태 추가
        for post in posts:
            post.is_liked = False

        result = PostListResponse(posts=posts, total=total)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"포스트 조회 중 오류 발생: {str(e)}"
        )


@router.get("/user/{user_id}/likes")
async def get_user_likes(
    user_id: str,
    db: Session = Depends(get_db)
):
    """사용자가 좋아요를 누른 포스트 ID 목록을 가져옵니다."""
    try:
        likes = db.query(PostLike.post_id).filter(
            PostLike.user_id == user_id
        ).all()

        post_ids = [like.post_id for like in likes]
        return {"liked_post_ids": post_ids}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"좋아요 목록 조회 중 오류 발생: {str(e)}"
        )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    """특정 포스트를 가져옵니다."""
    # 캐시 키 생성
    cache_key = f"post:detail:{post_id}"
    
    # 캐시에서 조회 시도
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.info(f"Cache hit for post: {cache_key}")
        # 캐시된 데이터가 dict라면 PostResponse로 변환
        if isinstance(cached_result, dict):
            return PostResponse(**cached_result)
        return cached_result
    
    logger.info(f"Cache miss for post: {cache_key}")
    
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
    
    # 포스트를 dict로 변환하여 캐시에 저장 (10분)
    post_dict = {
        "id": post.id,
        "user_id": post.user_id,
        "caption": post.caption,
        "image_url": post.image_url,
        "location": post.location,
        "likes_count": post.likes_count,
        "comments_count": getattr(post, 'comments_count', 0),  # 기본값 0
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "user": {
            "user_id": post.user.user_id,
            "email": post.user.email,
            "name": post.user.name,
            "profile_image": post.user.profile_image
        } if post.user else None
    }
    
    cache.set(cache_key, post_dict, expire=600)
    
    return post


class LikeRequest(BaseModel):
    user_id: str

@router.post("/{post_id}/like")
async def like_post(
    post_id: int,
    request: LikeRequest,
    db: Session = Depends(get_db)
):
    """포스트에 좋아요를 추가합니다."""
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="포스트를 찾을 수 없습니다."
        )

    # 중복 체크
    existing = db.query(PostLike).filter(
        PostLike.post_id == post_id,
        PostLike.user_id == request.user_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 좋아요를 누른 포스트입니다."
        )

    # 좋아요 추가
    new_like = PostLike(post_id=post_id, user_id=request.user_id)
    db.add(new_like)
    post.likes_count += 1
    db.commit()

    return {"message": "좋아요가 추가되었습니다.", "likes_count": post.likes_count}


@router.delete("/{post_id}/like")
async def unlike_post(
    post_id: int,
    user_id: str,
    db: Session = Depends(get_db)
):
    """포스트에서 좋아요를 제거합니다."""
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="포스트를 찾을 수 없습니다."
        )

    # 좋아요 레코드 찾아서 삭제
    existing = db.query(PostLike).filter(
        PostLike.post_id == post_id,
        PostLike.user_id == user_id
    ).first()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="좋아요를 누르지 않은 포스트입니다."
        )

    db.delete(existing)
    if post.likes_count > 0:
        post.likes_count -= 1
    db.commit()

    return {"message": "좋아요가 제거되었습니다.", "likes_count": post.likes_count}


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int,
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """포스트를 수정합니다."""
    try:
        # 포스트 조회
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="포스트를 찾을 수 없습니다."
            )
        
        # 포스트 소유자 확인
        if post.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="포스트를 수정할 권한이 없습니다."
            )
        
        # 이미지 업데이트 (새로운 이미지가 제공된 경우)
        if post_data.image_data:
            file_extension = "jpg"
            filename = f"{uuid.uuid4()}.{file_extension}"
            image_url = save_image_to_s3(post_data.image_data, filename)
            post.image_url = image_url
        
        # 포스트 정보 업데이트
        post.caption = post_data.caption
        post.location = post_data.location
        
        db.commit()
        db.refresh(post)
        
        # 캐시 무효화
        cache.delete(f"post:detail:{post.id}")  # 해당 포스트 상세 캐시 삭제
        cache.delete("posts:list:0:10")  # 포스트 목록 캐시 삭제
        cache.delete("posts:list:0:20")
        
        # 사용자 정보와 함께 반환
        post_with_user = db.query(Post).options(joinedload(Post.user)).filter(Post.id == post.id).first()
        
        logger.info(f"포스트 수정 완료: {post.id} by {current_user.user_id}")
        return post_with_user
        
    except Exception as e:
        db.rollback()
        logger.error(f"포스트 수정 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"포스트 수정 중 오류 발생: {str(e)}"
        )


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """포스트를 삭제합니다."""
    try:
        # 포스트 조회
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="포스트를 찾을 수 없습니다."
            )
        
        # 포스트 소유자 확인
        if post.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="포스트를 삭제할 권한이 없습니다."
            )
        
        # 포스트 삭제
        db.delete(post)
        db.commit()
        
        # 캐시 무효화
        cache.delete(f"post:detail:{post_id}")  # 해당 포스트 상세 캐시 삭제
        cache.delete("posts:list:0:10")  # 포스트 목록 캐시 삭제
        cache.delete("posts:list:0:20")
        
        logger.info(f"포스트 삭제 완료: {post_id} by {current_user.user_id}")
        return {"message": "포스트가 삭제되었습니다."}
        
    except Exception as e:
        db.rollback()
        logger.error(f"포스트 삭제 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"포스트 삭제 중 오류 발생: {str(e)}"
        )