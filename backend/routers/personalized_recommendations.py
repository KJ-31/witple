"""
개인화 추천 API
사용자 행동 데이터를 기반으로 계산된 선호도에 따른 맞춤 추천
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional
import logging
from database import get_db
# from auth_utils import get_current_user_id  # 임시로 주석 처리

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter(prefix="/api/v1/personalized", tags=["personalized_recommendations"])

@router.get("/preferences/{user_id}")
async def get_user_preferences(
    user_id: str,
    db: Session = Depends(get_db)
):
    """사용자의 카테고리별 선호도 조회"""
    try:
        query = text("""
            SELECT 
                place_category,
                preference_score,
                last_updated
            FROM user_category_preferences 
            WHERE user_id = :user_id 
            ORDER BY preference_score DESC
        """)
        
        result = db.execute(query, {"user_id": user_id}).fetchall()
        
        if not result:
            return {
                "user_id": user_id,
                "preferences": [],
                "message": "No preferences found for this user"
            }
        
        preferences = []
        for row in result:
            preferences.append({
                "place_category": row.place_category,
                "preference_score": float(row.preference_score),
                "last_updated": row.last_updated.isoformat() + "Z"
            })
        
        return {
            "user_id": user_id,
            "preferences": preferences,
            "top_category": preferences[0]["place_category"] if preferences else None
        }
        
    except Exception as e:
        logger.error(f"Error fetching user preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{user_id}")
async def get_personalized_recommendations(
    user_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """사용자 맞춤 추천 (선호도 기반으로 가중치 적용)"""
    try:
        # 1. 사용자 선호도 조회
        pref_query = text("""
            SELECT place_category, preference_score
            FROM user_category_preferences 
            WHERE user_id = :user_id 
            ORDER BY preference_score DESC
        """)
        
        preferences = db.execute(pref_query, {"user_id": user_id}).fetchall()
        
        if not preferences:
            # 선호도가 없으면 일반 추천 반환
            return await get_general_recommendations(limit, db)
        
        # 2. 선호도 기반 가중 추천
        # 카테고리별 선호도를 가중치로 사용하여 추천
        category_weights = {row.place_category: float(row.preference_score) for row in preferences}
        
        # 정규화 (가장 높은 점수를 1.0으로)
        max_score = max(category_weights.values()) if category_weights else 1.0
        normalized_weights = {k: v/max_score for k, v in category_weights.items()}
        
        # 3. 각 카테고리에서 추천 개수 계산
        recommendations = []
        total_weight = sum(normalized_weights.values())
        
        for category, weight in normalized_weights.items():
            # 가중치에 비례하여 추천 개수 할당
            category_limit = max(1, int((weight / total_weight) * limit))
            
            # 해당 카테고리의 인기 장소 조회 (예시)
            category_recs = await get_category_recommendations(category, category_limit, db)
            
            # 선호도 점수를 추가하여 개인화 정보 제공
            for rec in category_recs:
                rec["user_preference_score"] = weight
                rec["recommendation_reason"] = f"Based on your preference for {category}"
            
            recommendations.extend(category_recs)
        
        return {
            "user_id": user_id,
            "recommendations": recommendations[:limit],
            "personalization_applied": True,
            "user_preferences": [
                {"category": k, "score": v} 
                for k, v in normalized_weights.items()
            ]
        }
        
    except Exception as e:
        logger.error(f"Error generating personalized recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_category_recommendations(
    category: str, 
    limit: int, 
    db: Session
) -> List[Dict[str, Any]]:
    """특정 카테고리의 추천 장소 조회"""
    try:
        # 카테고리별 테이블 매핑 (실제 스키마에 맞게 수정)
        table_mapping = {
            'restaurants': 'restaurants',
            'accommodation': 'accommodation', 
            'nature': 'nature',
            'culture': 'humanities',
            'shopping': 'shopping'
        }
        
        table_name = table_mapping.get(category, 'restaurants')
        
        # 해당 카테고리에서 인기순으로 장소 조회 (실제 컬럼명 사용)
        query = text(f"""
            SELECT 
                id,
                name,
                overview as description,
                address,
                latitude,
                longitude,
                image_urls as image_url
            FROM {table_name}
            ORDER BY id
            LIMIT :limit
        """)
        
        result = db.execute(query, {"limit": limit}).fetchall()
        
        recommendations = []
        for row in result:
            recommendations.append({
                "id": str(row.id),
                "name": row.name,
                "description": row.description[:200] + "..." if row.description and len(row.description) > 200 else row.description,
                "address": row.address,
                "latitude": float(row.latitude) if row.latitude else None,
                "longitude": float(row.longitude) if row.longitude else None, 
                "image_url": row.image_url,
                "category": category
            })
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error fetching category recommendations for {category}: {e}")
        return []

async def get_general_recommendations(limit: int, db: Session) -> Dict[str, Any]:
    """일반 추천 (개인화되지 않음)"""
    try:
        # 모든 카테고리에서 균등하게 추천
        categories = ['restaurants', 'accommodation', 'nature', 'culture', 'shopping']
        recommendations = []
        
        items_per_category = max(1, limit // len(categories))
        
        for category in categories:
            category_recs = await get_category_recommendations(category, items_per_category, db)
            for rec in category_recs:
                rec["user_preference_score"] = 0.0
                rec["recommendation_reason"] = "General recommendation"
            recommendations.extend(category_recs)
        
        return {
            "recommendations": recommendations[:limit],
            "personalization_applied": False,
            "message": "General recommendations (no user preference data available)"
        }
        
    except Exception as e:
        logger.error(f"Error generating general recommendations: {e}")
        return {"recommendations": [], "personalization_applied": False, "error": str(e)}

@router.get("/my-recommendations/{user_id}")
async def get_my_recommendations(
    user_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """현재 로그인한 사용자의 맞춤 추천 (임시로 user_id 파라미터 사용)"""
    return await get_personalized_recommendations(user_id, limit, db)

@router.get("/stats")
async def get_recommendation_stats(db: Session = Depends(get_db)):
    """추천 시스템 통계"""
    try:
        query = text("""
            SELECT 
                COUNT(*) as total_users_with_preferences,
                COUNT(DISTINCT place_category) as tracked_categories,
                AVG(preference_score) as avg_preference_score,
                MAX(last_updated) as latest_update
            FROM user_category_preferences
        """)
        
        result = db.execute(query).fetchone()
        
        if result:
            return {
                "total_users_with_preferences": result.total_users_with_preferences,
                "tracked_categories": result.tracked_categories,
                "avg_preference_score": float(result.avg_preference_score) if result.avg_preference_score else 0.0,
                "latest_update": result.latest_update.isoformat() + "Z" if result.latest_update else None
            }
        else:
            return {
                "total_users_with_preferences": 0,
                "tracked_categories": 0,
                "avg_preference_score": 0.0,
                "latest_update": None
            }
            
    except Exception as e:
        logger.error(f"Error fetching recommendation stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))