"""
사용자 행동 트래킹 API
Frontend에서 호출하는 실시간 트래킹 엔드포인트
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, List
import asyncpg
import json
import logging
from datetime import datetime
import uuid
import os
from action_pipeline import ActionDataPipeline

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter(prefix="/api/tracking", tags=["tracking"])

# Pydantic 모델들
class ActionLog(BaseModel):
    user_id: str
    place_category: str  # 'restaurants', 'accommodation', 'nature' 등
    place_id: str
    action_type: str     # 'click', 'like', 'bookmark', 'dwell_time', 'search', 'scroll_depth'
    action_value: Optional[float] = None  # 체류시간(초), 스크롤깊이(%) 등
    action_detail: Optional[str] = None   # 추가 정보 (검색어, 클릭 위치 등)

class BatchActionLog(BaseModel):
    actions: List[ActionLog]

class ActionResponse(BaseModel):
    success: bool
    action_id: Optional[str] = None
    message: Optional[str] = None

# 의존성 주입용 함수들
async def get_db_connection():
    """DB 연결"""
    return await asyncpg.connect(os.getenv("DATABASE_URL"))

# 메인 트래킹 API들
@router.post("/log-action", response_model=ActionResponse)
async def log_single_action(
    action: ActionLog,
    background_tasks: BackgroundTasks
):
    """단일 사용자 행동 로깅"""
    
    try:
        # 1. DB에 즉시 저장 (빠른 응답)
        conn = await get_db_connection()
        
        try:
            action_id = str(uuid.uuid4())
            
            await conn.execute("""
                INSERT INTO user_action_logs
                (id, user_id, place_category, place_id, action_type, action_value, action_detail, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            action_id,
            action.user_id,
            action.place_category,
            action.place_id,
            action.action_type,
            action.action_value,
            action.action_detail,
            datetime.utcnow()
            )
            
            # 2. 백그라운드에서 이미지 벡터 처리 (bookmark, like만)
            if action.action_type in ['bookmark', 'like']:
                background_tasks.add_task(
                    process_image_action_background,
                    action.dict()
                )
            
            logger.info(f"Action logged: {action_id} - {action.user_id} {action.action_type} {action.place_category}")
            
            return ActionResponse(
                success=True,
                action_id=action_id,
                message="Action logged successfully"
            )
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error logging action: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/log-actions-batch", response_model=ActionResponse)
async def log_batch_actions(
    batch: BatchActionLog,
    background_tasks: BackgroundTasks
):
    """배치 사용자 행동 로깅"""
    
    try:
        conn = await get_db_connection()
        action_ids = []
        
        try:
            # 트랜잭션으로 배치 처리
            async with conn.transaction():
                for action in batch.actions:
                    action_id = str(uuid.uuid4())
                    action_ids.append(action_id)
                    
                    await conn.execute("""
                        INSERT INTO user_action_logs
                        (id, user_id, place_category, place_id, action_type, action_value, action_detail, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    action_id,
                    action.user_id,
                    action.place_category,
                    action.place_id,
                    action.action_type,
                    action.action_value,
                    action.action_detail,
                    datetime.utcnow()
                    )
            
            # 백그라운드에서 이미지 관련 액션들 처리
            image_actions = [a for a in batch.actions if a.action_type in ['bookmark', 'like']]
            if image_actions:
                background_tasks.add_task(
                    process_batch_image_actions_background,
                    [action.dict() for action in image_actions]
                )
            
            logger.info(f"Batch logged: {len(batch.actions)} actions from users")
            
            return ActionResponse(
                success=True,
                message=f"Batch of {len(batch.actions)} actions logged successfully"
            )
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error logging batch actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 사용자별 행동 조회 API
@router.get("/user-actions/{user_id}")
async def get_user_actions(
    user_id: str,
    limit: int = 50,
    action_type: Optional[str] = None,
    place_category: Optional[str] = None
):
    """사용자별 행동 이력 조회"""
    
    try:
        conn = await get_db_connection()
        
        try:
            # 쿼리 조건 구성
            conditions = ["user_id = $1"]
            params = [user_id]
            param_count = 1
            
            if action_type:
                param_count += 1
                conditions.append(f"action_type = ${param_count}")
                params.append(action_type)
            
            if place_category:
                param_count += 1
                conditions.append(f"place_category = ${param_count}")
                params.append(place_category)
            
            query = f"""
                SELECT 
                    id::text,
                    user_id,
                    place_category,
                    place_id::text,
                    action_type::text,
                    action_value,
                    action_detail,
                    created_at
                FROM user_action_logs
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ${param_count + 1}
            """
            params.append(limit)
            
            actions = await conn.fetch(query, *params)
            
            # JSON 변환
            result = []
            for action in actions:
                result.append({
                    "id": action['id'],
                    "user_id": action['user_id'],
                    "place_category": action['place_category'],
                    "place_id": action['place_id'],
                    "action_type": action['action_type'],
                    "action_value": float(action['action_value']) if action['action_value'] else None,
                    "action_detail": action['action_detail'],
                    "created_at": action['created_at'].isoformat() + "Z"
                })
            
            return {
                "user_id": user_id,
                "actions": result,
                "count": len(result)
            }
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching user actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 통계 API
@router.get("/stats")
async def get_tracking_stats():
    """트래킹 통계 조회"""
    
    try:
        conn = await get_db_connection()
        
        try:
            # 전체 통계
            total_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_actions,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT place_id) as unique_places
                FROM user_action_logs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
            
            # 액션 타입별 통계
            action_stats = await conn.fetch("""
                SELECT 
                    action_type::text,
                    COUNT(*) as count
                FROM user_action_logs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY action_type
                ORDER BY count DESC
            """)
            
            # 장소 카테고리별 통계
            category_stats = await conn.fetch("""
                SELECT 
                    place_category,
                    COUNT(*) as count
                FROM user_action_logs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY place_category
                ORDER BY count DESC
            """)
            
            return {
                "time_period": "Last 24 hours",
                "total": dict(total_stats),
                "by_action_type": [dict(row) for row in action_stats],
                "by_category": [dict(row) for row in category_stats]
            }
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 백그라운드 작업 함수들
async def process_image_action_background(action_data: dict):
    """단일 이미지 관련 액션 백그라운드 처리"""
    try:
        pipeline = ActionDataPipeline()
        await pipeline.process_action_for_image_vectors(action_data)
        logger.info(f"Processed image action: {action_data['user_id']} - {action_data['action_type']}")
    except Exception as e:
        logger.error(f"Background image processing failed: {e}")

async def process_batch_image_actions_background(actions_data: List[dict]):
    """배치 이미지 관련 액션들 백그라운드 처리"""
    try:
        pipeline = ActionDataPipeline()
        processed = 0
        
        for action_data in actions_data:
            await pipeline.process_action_for_image_vectors(action_data)
            processed += 1
        
        logger.info(f"Background processed {processed} image actions")
        
    except Exception as e:
        logger.error(f"Background batch processing failed: {e}")

# 관리용 API들
@router.post("/admin/export-to-s3")
async def manual_export_to_s3(
    background_tasks: BackgroundTasks,
    hours_back: int = 1
):
    """수동으로 S3 내보내기 (관리용)"""
    
    background_tasks.add_task(export_to_s3_background, hours_back)
    
    return {
        "message": f"S3 export started for last {hours_back} hours",
        "status": "processing"
    }

async def export_to_s3_background(hours_back: int):
    """S3 내보내기 백그라운드 작업"""
    try:
        pipeline = ActionDataPipeline()
        await pipeline.export_actions_to_s3(hours_back)
        logger.info(f"Manual S3 export completed for {hours_back} hours")
    except Exception as e:
        logger.error(f"Manual S3 export failed: {e}")

@router.get("/admin/health")
async def health_check():
    """헬스 체크"""
    
    try:
        conn = await get_db_connection()
        
        try:
            # DB 연결 테스트
            await conn.fetchval("SELECT 1")
            
            # 최근 액션 수 확인
            recent_count = await conn.fetchval("""
                SELECT COUNT(*) FROM user_action_logs 
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """)
            
            return {
                "status": "healthy",
                "database": "connected",
                "recent_actions_1h": recent_count,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
        finally:
            await conn.close()
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

# JavaScript용 트래킹 코드 생성 API
@router.get("/tracking-script")
async def get_tracking_script():
    """Frontend용 트래킹 JavaScript 코드 반환"""
    
    script_content = """
// Witple 사용자 행동 트래킹 스크립트
class WitpleTracker {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
        this.userId = null;
        this.pendingActions = [];
        this.batchInterval = 30000; // 30초
        
        // 페이지 언로드시 전송
        window.addEventListener('beforeunload', () => {
            this.flush(true);
        });
        
        // 정기 전송
        setInterval(() => {
            this.flush();
        }, this.batchInterval);
    }
    
    setUserId(userId) {
        this.userId = userId;
    }
    
    track(actionType, placeId, placeCategory, actionValue = null, actionDetail = null) {
        if (!this.userId) return;
        
        const action = {
            user_id: this.userId,
            place_category: placeCategory,
            place_id: placeId,
            action_type: actionType,
            action_value: actionValue,
            action_detail: actionDetail
        };
        
        this.pendingActions.push(action);
        
        // 중요한 액션은 즉시 전송
        if (['bookmark', 'like'].includes(actionType)) {
            this.flush();
        }
    }
    
    // 편의 메서드들
    trackClick(placeId, placeCategory, detail = null) {
        this.track('click', placeId, placeCategory, null, detail);
    }
    
    trackBookmark(placeId, placeCategory) {
        this.track('bookmark', placeId, placeCategory);
    }
    
    trackLike(placeId, placeCategory) {
        this.track('like', placeId, placeCategory);
    }
    
    trackDwellTime(placeId, placeCategory, seconds) {
        this.track('dwell_time', placeId, placeCategory, seconds);
    }
    
    trackSearch(query, placeCategory = 'general') {
        this.track('search', 'search_' + Date.now(), placeCategory, null, query);
    }
    
    trackScrollDepth(placeId, placeCategory, percentage) {
        this.track('scroll_depth', placeId, placeCategory, percentage);
    }
    
    flush(immediate = false) {
        if (this.pendingActions.length === 0) return;
        
        const actions = [...this.pendingActions];
        this.pendingActions = [];
        
        const payload = { actions: actions };
        
        if (immediate && navigator.sendBeacon) {
            // 페이지 언로드시 beacon 사용
            navigator.sendBeacon(
                this.apiBaseUrl + '/api/tracking/log-actions-batch',
                JSON.stringify(payload)
            );
        } else {
            // 일반적인 fetch 사용
            fetch(this.apiBaseUrl + '/api/tracking/log-actions-batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            }).catch(err => {
                console.warn('Tracking failed:', err);
                // 실패한 경우 다시 버퍼에 추가
                this.pendingActions.unshift(...actions);
            });
        }
    }
}

// 전역 인스턴스 생성
window.witpleTracker = new WitpleTracker('{API_BASE_URL}');

// 사용 예시:
// witpleTracker.setUserId('user123');
// witpleTracker.trackClick('place456', 'restaurants');
// witpleTracker.trackBookmark('place789', 'accommodation');
    """.replace('{API_BASE_URL}', os.getenv('API_BASE_URL', 'http://localhost:8000'))
    
    return {
        "content_type": "application/javascript",
        "script": script_content
    }