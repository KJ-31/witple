from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vectorization import RecommendationEngine
from auth_utils import get_current_user
from schemas import PlaceRecommendation, RecommendationRequest
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)

# 추천 엔진 인스턴스
recommendation_engine = RecommendationEngine()

@router.get("/popular", response_model=List[Dict[str, Any]])
async def get_popular_places(
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터 (accommodation, restaurants, nature, etc.)"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수 제한")
):
    """
    인기 장소 추천 (로그인 불필요)
    - 클릭수, 체류시간, 좋아요 등 행동 데이터 기반
    """
    try:
        popular_places = await recommendation_engine.get_popular_places(
            region=region,
            category=category,
            limit=limit
        )
        
        return popular_places
        
    except Exception as e:
        logger.error(f"Error getting popular places: {str(e)}")
        raise HTTPException(status_code=500, detail="인기 장소 조회 중 오류가 발생했습니다.")

@router.get("/personalized", response_model=List[Dict[str, Any]])
async def get_personalized_recommendations(
    current_user: dict = Depends(get_current_user),
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수 제한")
):
    """
    개인화 추천 (로그인 필요)
    - 사용자 선호도와 행동 이력 기반 BERT 벡터 유사도 계산
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        personalized_places = await recommendation_engine.get_personalized_recommendations(
            user_id=user_id,
            region=region,
            category=category,
            limit=limit
        )
        
        return personalized_places
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting personalized recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="개인화 추천 조회 중 오류가 발생했습니다.")

@router.get("/regions/popular")
async def get_popular_regions(
    limit: int = Query(10, ge=1, le=50, description="결과 개수 제한")
):
    """인기 지역 목록 조회"""
    try:
        popular_regions = await recommendation_engine.get_popular_regions(limit=limit)
        return popular_regions
        
    except Exception as e:
        logger.error(f"Error getting popular regions: {str(e)}")
        raise HTTPException(status_code=500, detail="인기 지역 조회 중 오류가 발생했습니다.")

@router.get("/regions/personalized")
async def get_personalized_regions(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50, description="결과 개수 제한")
):
    """개인화 지역 추천"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        personalized_regions = await recommendation_engine.get_personalized_regions(
            user_id=user_id,
            limit=limit
        )
        
        return personalized_regions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting personalized regions: {str(e)}")
        raise HTTPException(status_code=500, detail="개인화 지역 추천 조회 중 오류가 발생했습니다.")

@router.get("/mixed")
async def get_mixed_recommendations(
    current_user: Optional[dict] = Depends(get_current_user),
    region: Optional[str] = Query(None, description="지역 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    limit: int = Query(20, ge=1, le=100, description="결과 개수 제한")
):
    """
    혼합 추천 (로그인 상태에 따라 자동 분기)
    - 로그인: 개인화 추천 70% + 인기 추천 30%
    - 비로그인: 인기 추천 100%
    """
    try:
        if current_user and current_user.get("user_id"):
            # 로그인 상태: 혼합 추천
            user_id = current_user["user_id"]
            
            # 개인화 추천 (70%)
            personalized_limit = int(limit * 0.7)
            personalized_places = await recommendation_engine.get_personalized_recommendations(
                user_id=user_id,
                region=region,
                category=category,
                limit=personalized_limit
            )
            
            # 인기 추천 (30%)
            popular_limit = limit - len(personalized_places)
            if popular_limit > 0:
                # 이미 추천된 장소 제외
                exclude_ids = [(p['place_id'], p['table_name']) for p in personalized_places]
                popular_places = await recommendation_engine.get_popular_places(
                    region=region,
                    category=category,
                    limit=popular_limit,
                    exclude_places=exclude_ids
                )
                
                # 타입 표시 추가
                for place in personalized_places:
                    place['recommendation_type'] = 'personalized'
                for place in popular_places:
                    place['recommendation_type'] = 'popular'
                
                return personalized_places + popular_places
            else:
                for place in personalized_places:
                    place['recommendation_type'] = 'personalized'
                return personalized_places
        else:
            # 비로그인 상태: 인기 추천만
            popular_places = await recommendation_engine.get_popular_places(
                region=region,
                category=category,
                limit=limit
            )
            
            for place in popular_places:
                place['recommendation_type'] = 'popular'
            
            return popular_places
            
    except Exception as e:
        logger.error(f"Error getting mixed recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="추천 조회 중 오류가 발생했습니다.")

@router.post("/feedback")
async def record_recommendation_feedback(
    place_id: int,
    table_name: str,
    action_type: str,
    action_value: Optional[float] = None,
    current_user: dict = Depends(get_current_user)
):
    """추천 결과에 대한 사용자 행동 기록"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        await recommendation_engine.record_user_action(
            user_id=user_id,
            place_id=place_id,
            place_category=table_name,
            action_type=action_type,
            action_value=action_value
        )
        
        return {"message": "피드백이 기록되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="피드백 기록 중 오류가 발생했습니다.")

@router.get("/stats")
async def get_recommendation_stats(
    current_user: dict = Depends(get_current_user)
):
    """사용자 추천 통계 조회"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다.")
        
        stats = await recommendation_engine.get_user_recommendation_stats(user_id)
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendation stats: {str(e)}")
        raise HTTPException(status_code=500, detail="추천 통계 조회 중 오류가 발생했습니다.")