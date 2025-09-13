"""
AWS Batch 처리 관련 API 엔드포인트
- 배치 작업 완료 webhook 처리
- 사용자 행동 벡터 업데이트
- 장소 벡터 업데이트
- 배치 작업 상태 조회
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging
import boto3
from botocore.exceptions import ClientError

from database import get_db
from models import User, UserAction, UserBehaviorVector, PlaceVector
from auth_utils import get_current_user
import os

# 로깅 설정
logger = logging.getLogger(__name__)

# AWS 클라이언트 설정
batch_client = boto3.client('batch', region_name=os.getenv('AWS_REGION', 'ap-northeast-2'))

router = APIRouter(prefix="/batch", tags=["batch-processing"])

# ============= Pydantic 스키마들 =============

from pydantic import BaseModel
from typing import Union

class BatchJobCompletionWebhook(BaseModel):
    """AWS Batch 작업 완료 webhook 데이터"""
    job_id: str
    job_name: str
    job_status: str  # SUCCEEDED, FAILED
    batch_id: str
    processed_records: int
    processing_time_seconds: float
    s3_input_path: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class UserVectorUpdate(BaseModel):
    """사용자 벡터 업데이트 데이터"""
    user_id: str
    behavior_vector: List[float]  # 384차원 BERT 벡터
    like_score: float
    bookmark_score: float
    click_score: float
    dwell_time_score: float
    total_actions: int
    total_likes: int
    total_bookmarks: int
    total_clicks: int
    last_action_date: datetime

class PlaceVectorUpdate(BaseModel):
    """장소 벡터 업데이트 데이터"""
    place_id: str
    place_category: str
    content_vector: Optional[List[float]] = None
    behavior_vector: Optional[List[float]] = None
    combined_vector: Optional[List[float]] = None
    total_likes: int = 0
    total_bookmarks: int = 0
    total_clicks: int = 0
    unique_users: int = 0
    avg_dwell_time: float = 0.0
    popularity_score: float = 0.0
    engagement_score: float = 0.0

class BatchProcessingStatus(BaseModel):
    """배치 처리 상태 정보"""
    total_unprocessed_actions: int
    oldest_unprocessed_action: Optional[datetime]
    recent_batch_jobs: List[Dict[str, Any]]
    user_vectors_updated: int
    place_vectors_updated: int

# ============= 웹훅 엔드포인트 =============

@router.post("/webhook/completion")
async def batch_job_completion_webhook(
    webhook_data: BatchJobCompletionWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    AWS Batch 작업 완료 시 호출되는 webhook
    배치 작업이 성공하면 처리된 액션들을 batch_processed=True로 업데이트
    """
    logger.info(f"🔔 Batch job completion webhook: {webhook_data.job_id} - {webhook_data.job_status}")
    
    try:
        # 요청 메타데이터 로깅
        client_ip = request.client.host
        logger.info(f"Webhook from IP: {client_ip}, Job: {webhook_data.job_name}")
        
        if webhook_data.job_status == "SUCCEEDED":
            # 성공한 경우 - 해당 batch_id의 액션들을 처리 완료로 마킹
            updated_count = db.query(UserAction).filter(
                UserAction.batch_id == webhook_data.batch_id,
                UserAction.batch_processed == False
            ).update({
                UserAction.batch_processed: True,
                UserAction.batch_processed_at: datetime.now()
            })
            
            db.commit()
            
            logger.info(f"✅ Marked {updated_count} actions as processed for batch {webhook_data.batch_id}")
            
            # 백그라운드에서 벡터 업데이트 알림 처리
            background_tasks.add_task(
                process_vector_updates_notification,
                webhook_data.batch_id,
                webhook_data.processed_records
            )
            
            return {
                "success": True,
                "message": f"Batch job {webhook_data.job_id} completed successfully",
                "updated_actions": updated_count,
                "batch_id": webhook_data.batch_id
            }
            
        else:
            # 실패한 경우 - 로깅만 하고 재처리 가능하도록 둠
            logger.error(f"❌ Batch job {webhook_data.job_id} failed: {webhook_data.error_message}")
            
            return {
                "success": False,
                "message": f"Batch job {webhook_data.job_id} failed",
                "error": webhook_data.error_message,
                "batch_id": webhook_data.batch_id
            }
            
    except Exception as e:
        logger.error(f"❌ Webhook processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )

@router.post("/webhook/vector-updates")
async def batch_vector_updates_webhook(
    user_updates: List[UserVectorUpdate],
    place_updates: List[PlaceVectorUpdate],
    db: Session = Depends(get_db)
):
    """
    AWS Batch에서 계산된 벡터 업데이트를 받는 webhook
    사용자 및 장소 벡터 데이터를 일괄 업데이트
    """
    logger.info(f"📊 Vector updates webhook: {len(user_updates)} users, {len(place_updates)} places")
    
    try:
        updated_users = 0
        updated_places = 0
        
        # 사용자 벡터 업데이트
        for user_update in user_updates:
            # 기존 벡터 레코드 조회
            existing_vector = db.query(UserBehaviorVector).filter(
                UserBehaviorVector.user_id == user_update.user_id
            ).first()
            
            if existing_vector:
                # 기존 레코드 업데이트
                existing_vector.behavior_vector = user_update.behavior_vector
                existing_vector.like_score = user_update.like_score
                existing_vector.bookmark_score = user_update.bookmark_score
                existing_vector.click_score = user_update.click_score
                existing_vector.dwell_time_score = user_update.dwell_time_score
                existing_vector.total_actions = user_update.total_actions
                existing_vector.total_likes = user_update.total_likes
                existing_vector.total_bookmarks = user_update.total_bookmarks
                existing_vector.total_clicks = user_update.total_clicks
                existing_vector.last_action_date = user_update.last_action_date
                existing_vector.vector_updated_at = datetime.now()
            else:
                # 새 레코드 생성
                new_vector = UserBehaviorVector(
                    user_id=user_update.user_id,
                    behavior_vector=user_update.behavior_vector,
                    like_score=user_update.like_score,
                    bookmark_score=user_update.bookmark_score,
                    click_score=user_update.click_score,
                    dwell_time_score=user_update.dwell_time_score,
                    total_actions=user_update.total_actions,
                    total_likes=user_update.total_likes,
                    total_bookmarks=user_update.total_bookmarks,
                    total_clicks=user_update.total_clicks,
                    last_action_date=user_update.last_action_date
                )
                db.add(new_vector)
            
            updated_users += 1
        
        # 장소 벡터 업데이트
        for place_update in place_updates:
            # 기존 장소 벡터 조회
            existing_place = db.query(PlaceVector).filter(
                and_(
                    PlaceVector.place_id == place_update.place_id,
                    PlaceVector.place_category == place_update.place_category
                )
            ).first()
            
            if existing_place:
                # 기존 레코드 업데이트
                if place_update.content_vector:
                    existing_place.content_vector = place_update.content_vector
                if place_update.behavior_vector:
                    existing_place.behavior_vector = place_update.behavior_vector
                if place_update.combined_vector:
                    existing_place.combined_vector = place_update.combined_vector
                
                existing_place.total_likes = place_update.total_likes
                existing_place.total_bookmarks = place_update.total_bookmarks
                existing_place.total_clicks = place_update.total_clicks
                existing_place.unique_users = place_update.unique_users
                existing_place.avg_dwell_time = place_update.avg_dwell_time
                existing_place.popularity_score = place_update.popularity_score
                existing_place.engagement_score = place_update.engagement_score
                existing_place.vector_updated_at = datetime.now()
                existing_place.stats_updated_at = datetime.now()
            else:
                # 새 레코드 생성
                new_place = PlaceVector(
                    place_id=place_update.place_id,
                    place_category=place_update.place_category,
                    content_vector=place_update.content_vector,
                    behavior_vector=place_update.behavior_vector,
                    combined_vector=place_update.combined_vector,
                    total_likes=place_update.total_likes,
                    total_bookmarks=place_update.total_bookmarks,
                    total_clicks=place_update.total_clicks,
                    unique_users=place_update.unique_users,
                    avg_dwell_time=place_update.avg_dwell_time,
                    popularity_score=place_update.popularity_score,
                    engagement_score=place_update.engagement_score
                )
                db.add(new_place)
            
            updated_places += 1
        
        # 모든 변경사항 커밋
        db.commit()
        
        logger.info(f"✅ Vector updates completed: {updated_users} users, {updated_places} places")
        
        return {
            "success": True,
            "updated_users": updated_users,
            "updated_places": updated_places,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Vector updates failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector updates failed: {str(e)}"
        )

# ============= 배치 처리 관리 엔드포인트 =============

@router.get("/status", response_model=BatchProcessingStatus)
def get_batch_processing_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    배치 처리 상태 조회
    - 미처리 액션 수
    - 최신 배치 작업 상태
    - 벡터 업데이트 통계
    """
    try:
        # 미처리 액션 수 조회
        total_unprocessed = db.query(UserAction).filter(
            UserAction.batch_processed == False
        ).count()
        
        # 가장 오래된 미처리 액션 날짜
        oldest_unprocessed = db.query(UserAction.created_at).filter(
            UserAction.batch_processed == False
        ).order_by(UserAction.created_at.asc()).first()
        
        # 최근 업데이트된 벡터 수 (최근 24시간)
        yesterday = datetime.now() - timedelta(days=1)
        
        user_vectors_updated = db.query(UserBehaviorVector).filter(
            UserBehaviorVector.vector_updated_at >= yesterday
        ).count()
        
        place_vectors_updated = db.query(PlaceVector).filter(
            PlaceVector.vector_updated_at >= yesterday
        ).count()
        
        # AWS Batch 작업 상태 조회 (최근 10개)
        try:
            response = batch_client.list_jobs(
                jobQueue='witple-fargate-queue',
                maxResults=10
            )
            recent_batch_jobs = []
            for job in response.get('jobSummary', []):
                recent_batch_jobs.append({
                    'job_id': job['jobId'],
                    'job_name': job['jobName'],
                    'status': job['jobStatus'],
                    'created_at': job['createdAt'],
                    'started_at': job.get('startedAt'),
                    'stopped_at': job.get('stoppedAt')
                })
        except ClientError as e:
            logger.warning(f"⚠️ Could not fetch AWS Batch job status: {e}")
            recent_batch_jobs = []
        
        return BatchProcessingStatus(
            total_unprocessed_actions=total_unprocessed,
            oldest_unprocessed_action=oldest_unprocessed[0] if oldest_unprocessed else None,
            recent_batch_jobs=recent_batch_jobs,
            user_vectors_updated=user_vectors_updated,
            place_vectors_updated=place_vectors_updated
        )
        
    except Exception as e:
        logger.error(f"❌ Status check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status check failed: {str(e)}"
        )

@router.post("/trigger-processing")
def trigger_batch_processing(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    수동으로 배치 처리 트리거 (관리자용)
    미처리 액션들을 AWS Batch로 전송하여 처리 시작
    """
    try:
        # 미처리 액션 수 확인
        unprocessed_count = db.query(UserAction).filter(
            UserAction.batch_processed == False
        ).count()
        
        if unprocessed_count == 0:
            return {
                "success": True,
                "message": "No unprocessed actions to process",
                "unprocessed_count": 0
            }
        
        # 백그라운드에서 배치 작업 제출
        background_tasks.add_task(submit_batch_job, unprocessed_count)
        
        logger.info(f"🚀 Manual batch processing triggered for {unprocessed_count} actions")
        
        return {
            "success": True,
            "message": f"Batch processing triggered for {unprocessed_count} actions",
            "unprocessed_count": unprocessed_count
        }
        
    except Exception as e:
        logger.error(f"❌ Manual batch trigger failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual batch trigger failed: {str(e)}"
        )

# ============= 유틸리티 함수들 =============

async def process_vector_updates_notification(batch_id: str, processed_records: int):
    """배치 작업 완료 후 추가 처리 작업 (백그라운드)"""
    try:
        logger.info(f"🔄 Processing vector updates notification for batch {batch_id}")
        
        # TODO: 필요시 추가 알림 로직 구현
        # - 관리자에게 이메일 알림
        # - 모니터링 시스템에 메트릭 전송
        # - 캐시 무효화 등
        
        logger.info(f"✅ Vector updates notification processed for {processed_records} records")
        
    except Exception as e:
        logger.error(f"❌ Vector updates notification failed: {str(e)}")

async def submit_batch_job(unprocessed_count: int):
    """AWS Batch 작업 제출 (백그라운드)"""
    try:
        job_name = f"witple-vectorization-{int(datetime.now().timestamp())}"
        
        # 배치 작업 제출
        response = batch_client.submit_job(
            jobName=job_name,
            jobQueue='witple-fargate-queue',
            jobDefinition='witple-vectorization-job',  # 나중에 생성할 작업 정의
            parameters={
                'inputBucket': 'user-actions-data',
                'inputPrefix': 'user-actions/',
                'outputTable': 'user_behavior_vectors',
                'maxRecords': str(unprocessed_count)
            }
        )
        
        job_id = response['jobId']
        logger.info(f"🚀 Batch job submitted: {job_name} (ID: {job_id})")
        
        return {
            "job_id": job_id,
            "job_name": job_name,
            "status": "SUBMITTED"
        }
        
    except ClientError as e:
        logger.error(f"❌ Batch job submission failed: {str(e)}")
        raise e