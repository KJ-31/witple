from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

# LLM_RAG.py를 임포트하기 위해 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from LLM_RAG import get_travel_recommendation, get_travel_recommendation_langgraph, LANGGRAPH_AVAILABLE
    print("✅ LLM_RAG module imported successfully")
    print(f"🔧 LangGraph 사용 가능: {LANGGRAPH_AVAILABLE}")
    print(f"🔧 get_travel_recommendation 함수: {get_travel_recommendation is not None}")
    print(f"🔧 get_travel_recommendation_langgraph 함수: {get_travel_recommendation_langgraph is not None}")
except ImportError as e:
    print(f"❌ Warning: Could not import LLM_RAG module: {e}")
    print("This is likely due to missing dependencies (langchain_aws, boto3, etc.)")
    import traceback
    traceback.print_exc()
    get_travel_recommendation = None
    get_travel_recommendation_langgraph = None
    LANGGRAPH_AVAILABLE = False
except Exception as e:
    print(f"❌ Error initializing LLM_RAG module: {e}")
    import traceback
    traceback.print_exc()
    get_travel_recommendation = None
    get_travel_recommendation_langgraph = None
    LANGGRAPH_AVAILABLE = False

router = APIRouter()

def process_response_for_frontend(response: str) -> tuple[str, List[str]]:
    """프론트엔드에서 쉽게 처리할 수 있도록 응답을 여러 형태로 변환"""
    
    # HTML 형태 변환 (\n -> <br>)
    response_html = response.replace('\n', '<br>')
    
    # 줄별 배열 형태 변환
    response_lines = []
    for line in response.split('\n'):
        # 빈 줄은 유지하되 공백 문자열로 변환
        response_lines.append(line.strip() if line.strip() else "")
    
    return response_html, response_lines

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    success: bool
    error: Optional[str] = None
    travel_plan: Optional[dict] = None  # 구조화된 여행 일정
    action_required: Optional[str] = None  # 페이지 이동 등 필요 액션
    formatted_response: Optional[dict] = None  # UI용 구조화된 응답
    response_html: Optional[str] = None  # HTML 형태 응답 (개행 처리)
    response_lines: Optional[List[str]] = None  # 줄별 배열 형태 응답
    redirect_url: Optional[str] = None  # 리다이렉트 URL
    places: Optional[List[dict]] = None  # 지도 표시용 장소 정보

@router.post("/chat", response_model=ChatResponse)
async def chat_with_llm(chat_message: ChatMessage):
    """
    사용자의 메시지를 받아 LangGraph 기반 여행 추천 시스템으로 응답을 생성합니다.
    LangGraph가 사용 불가능할 때는 기존 RAG 시스템으로 폴백합니다.
    """
    try:
        if get_travel_recommendation is None and get_travel_recommendation_langgraph is None:
            # 모든 RAG 시스템이 사용 불가능할 때 기본 응답
            default_message = f"죄송합니다. 현재 AI 여행 추천 시스템을 준비 중입니다. 📝\n\n'{chat_message.message}'에 대한 답변을 위해 조금만 기다려주세요!"
            default_html, default_lines = process_response_for_frontend(default_message)
            
            return ChatResponse(
                response=default_message,
                success=True,
                response_html=default_html,
                response_lines=default_lines
            )
        
        print(f"🔍 Processing travel query: {chat_message.message}")
        
        # LangGraph 사용 가능한 경우 우선 사용
        if LANGGRAPH_AVAILABLE and get_travel_recommendation_langgraph:
            print("🚀 Using LangGraph workflow for enhanced travel recommendation")
            
            # 간단한 세션 ID (실제로는 사용자별 고유 ID 사용)
            # 현재는 데모용으로 고정 세션 ID 사용
            session_id = "demo_session"
            
            result = get_travel_recommendation_langgraph(chat_message.message, session_id=session_id)
            
            print(f"✅ LangGraph result: {result.get('response', '')[:100]}...")
            
            response_text = result.get('response', '응답을 생성할 수 없습니다.')
            response_html, response_lines = process_response_for_frontend(response_text)
            
            # tool_results에서 redirect_url과 places 정보 추출
            tool_results = result.get('raw_state', {}).get('tool_results', {})
            
            return ChatResponse(
                response=response_text,
                success=result.get('success', True),
                travel_plan=result.get('travel_plan', {}),
                action_required=result.get('action_required'),
                error=result.get('error'),
                formatted_response=result.get('raw_state', {}).get('formatted_ui_response'),
                response_html=response_html,
                response_lines=response_lines,
                redirect_url=tool_results.get('redirect_url'),
                places=tool_results.get('places')
            )
        
        # LangGraph 사용 불가능 시 기존 RAG 시스템 사용
        else:
            print("⚠️ LangGraph 사용 불가능, 기존 RAG 시스템으로 폴백")
            response = get_travel_recommendation(chat_message.message, stream=False)
            print(f"✅ Got basic RAG response: {response[:100]}..." if len(response) > 100 else f"✅ Got response: {response}")
            
            response_html, response_lines = process_response_for_frontend(response)
            
            return ChatResponse(
                response=response,
                success=True,
                response_html=response_html,
                response_lines=response_lines
            )
        
    except Exception as e:
        print(f"❌ Chat API error: {e}")
        import traceback
        traceback.print_exc()
        error_message = "죄송합니다. 현재 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        error_html, error_lines = process_response_for_frontend(error_message)
        
        return ChatResponse(
            response=error_message,
            success=False,
            error=str(e),
            response_html=error_html,
            response_lines=error_lines
        )

@router.get("/chat/health")
async def chat_health():
    """
    챗봇 서비스의 상태를 확인합니다.
    """
    try:
        if get_travel_recommendation is None:
            return {
                "status": "unhealthy", 
                "message": "LLM RAG 시스템이 초기화되지 않음"
            }
        
        # 간단한 테스트 쿼리로 시스템 상태 확인
        test_response = get_travel_recommendation("서울", stream=False)
        
        return {
            "status": "healthy",
            "message": "LLM RAG 시스템이 정상 작동 중"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy", 
            "message": f"LLM RAG 시스템 오류: {str(e)}"
        }

class ScheduleItem(BaseModel):
    """일정 항목 모델"""
    time: str
    place_name: str
    description: str
    category: Optional[str] = None
    place_info: Optional[dict] = None

class DayItinerary(BaseModel):
    """하루 일정 모델"""
    day: int
    schedule: List[ScheduleItem] = []

class PlaceInfo(BaseModel):
    """장소 정보 모델"""
    name: str
    category: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    description: Optional[str] = None
    similarity_score: Optional[float] = None

class TravelPlanData(BaseModel):
    """확장된 여행 일정 데이터 모델"""
    region: str
    cities: List[str] = []
    duration: str
    categories: List[str] = []
    itinerary: List[DayItinerary] = []
    places: List[PlaceInfo] = []
    raw_response: str
    status: str
    plan_id: Optional[str] = None
    created_at: Optional[str] = None
    total_places: Optional[int] = None
    confidence_score: Optional[float] = None

class TravelPlanResponse(BaseModel):
    """여행 일정 응답 모델"""
    success: bool
    message: str
    plan_id: Optional[str] = None
    redirect_url: Optional[str] = None
    error: Optional[str] = None

@router.post("/chat/confirm-plan", response_model=TravelPlanResponse)
async def confirm_travel_plan(plan_data: TravelPlanData):
    """
    확정된 여행 일정을 받아서 처리하고 일정 생성 페이지로 리다이렉트할 정보를 제공합니다.
    """
    try:
        print(f"🎉 여행 일정 확정 요청: {plan_data.region} {plan_data.duration}")
        
        # plan_id가 이미 있으면 사용, 없으면 새로 생성
        plan_id = plan_data.plan_id
        if not plan_id:
            import uuid
            import time
            timestamp = str(int(time.time()))[-6:]
            unique_id = str(uuid.uuid4())[:8]
            plan_id = f"plan_{timestamp}_{unique_id}"
        
        # 여행 일정 데이터 검증
        if not plan_data.region or not plan_data.duration:
            raise HTTPException(
                status_code=400, 
                detail="여행 지역과 기간은 필수입니다."
            )
        
        # 확정된 일정 데이터 구성
        confirmed_data = {
            "plan_id": plan_id,
            "region": plan_data.region,
            "duration": plan_data.duration,
            "itinerary": [item.dict() for item in plan_data.itinerary],
            "places": [place.dict() for place in plan_data.places],
            "categories": plan_data.categories,
            "status": "confirmed",
            "confirmed_at": plan_data.created_at,
            "total_places": plan_data.total_places,
            "confidence_score": plan_data.confidence_score
        }
        
        # URL 파라미터 구성
        url_params = f"plan_id={plan_id}&region={plan_data.region}&duration={plan_data.duration}"
        if plan_data.cities:
            url_params += f"&cities={','.join(plan_data.cities)}"
        
        redirect_url = f"/travel-planning?{url_params}"
        
        # 실제 구현에서는 여기서 데이터베이스에 일정 저장
        # save_travel_plan_to_db(confirmed_data, user_id)
        
        print(f"✅ 여행 일정 저장 완료. Plan ID: {plan_id}")
        
        # 상세 확정 메시지 생성
        places_summary = ""
        if plan_data.places:
            place_names = [place.name for place in plan_data.places[:3]]
            places_summary = f"주요 방문지: {', '.join(place_names)}"
            if len(plan_data.places) > 3:
                places_summary += f" 외 {len(plan_data.places) - 3}곳"
        
        confirmation_message = f"""
🎉 **{plan_data.region} {plan_data.duration} 여행 일정이 확정되었습니다!**

📋 **확정 정보:**
• 일정 수: {len(plan_data.itinerary)}일
• {places_summary}
• 신뢰도: {plan_data.confidence_score:.2f if plan_data.confidence_score else 'N/A'}

✈️ 여행 계획 페이지로 이동하여 세부 조정을 진행하세요!
        """.strip()
        
        return TravelPlanResponse(
            success=True,
            message=confirmation_message,
            plan_id=plan_id,
            redirect_url=redirect_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 여행 일정 확정 오류: {e}")
        import traceback
        traceback.print_exc()
        return TravelPlanResponse(
            success=False,
            message="여행 일정 확정 중 오류가 발생했습니다.",
            error=str(e)
        )

@router.get("/chat/travel-plan/{plan_id}")
async def get_travel_plan(plan_id: str):
    """
    저장된 여행 일정을 조회합니다.
    """
    try:
        # 실제로는 데이터베이스에서 조회
        # plan_data = get_travel_plan_from_db(plan_id)
        
        # 현재는 모의 데이터 반환
        mock_plan = {
            "plan_id": plan_id,
            "region": "제주도",
            "duration": "2박 3일",
            "locations": ["한라산", "성산일출봉", "협재해수욕장"],
            "status": "confirmed",
            "created_at": "2025-09-13",
            "message": "계획된 여행 일정입니다."
        }
        
        return {
            "success": True,
            "data": mock_plan
        }
        
    except Exception as e:
        print(f"❌ 여행 일정 조회 오류: {e}")
        raise HTTPException(
            status_code=404, 
            detail=f"여행 일정을 찾을 수 없습니다. Plan ID: {plan_id}"
        )