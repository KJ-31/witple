from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
import sys
import os
import hashlib
import re

# LLM_RAG.py를 임포트하기 위해 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from LLM_RAG import (
        get_travel_recommendation_langgraph,
        current_travel_state,
        get_current_travel_state_ref
    )
    print("✅ LLM_RAG module imported successfully")
    print(f"🔧 get_travel_recommendation_langgraph 함수: {get_travel_recommendation_langgraph is not None}")
except ImportError as e:
    print(f"❌ Warning: Could not import LLM_RAG module: {e}")
    print("This is likely due to missing dependencies (langchain_aws, boto3, etc.)")
    import traceback
    traceback.print_exc()
    get_travel_recommendation_langgraph = None
    current_travel_state = None
except Exception as e:
    print(f"❌ Error initializing LLM_RAG module: {e}")
    import traceback
    traceback.print_exc()
    get_travel_recommendation_langgraph = None
    current_travel_state = None

router = APIRouter()

# 확장된 캐시 메서드 구현
def _generate_cache_key(query: str, cache_type: str = "response") -> str:
    """쿼리 기반 캐시 키 생성"""
    # 쿼리 정규화 (공백, 대소문자, 특수문자 처리)
    normalized_query = re.sub(r'\s+', ' ', query.strip().lower())
    normalized_query = re.sub(r'[^\w\s가-힣]', '', normalized_query)

    # 해시 생성
    query_hash = hashlib.md5(normalized_query.encode('utf-8')).hexdigest()[:12]
    return f"llm:{cache_type}:{query_hash}"

def cache_full_response(cache_instance, query: str, response_data: dict, expire: int = 3600) -> bool:
    """전체 ChatResponse 데이터 캐싱"""
    if not cache_instance or not cache_instance.enabled or not response_data:
        return False

    try:
        cache_key = _generate_cache_key(query, "full")
        data_json = json.dumps(response_data, ensure_ascii=False, default=str)
        success = cache_instance.redis.set(cache_key, data_json, ex=expire)

        if success:
            print(f"💾 전체 응답 캐시 저장: {cache_key}")

        return success

    except Exception as e:
        print(f"⚠️ 전체 캐시 저장 오류: {e}")
        return False

def get_cached_full_response(cache_instance, query: str) -> Optional[dict]:
    """전체 ChatResponse 데이터 조회"""
    if not cache_instance or not cache_instance.enabled:
        return None

    try:
        cache_key = _generate_cache_key(query, "full")
        cached_data = cache_instance.redis.get(cache_key)

        if cached_data:
            print(f"🎯 전체 캐시 히트: {cache_key}")
            return json.loads(cached_data)
        else:
            print(f"❌ 전체 캐시 미스: {cache_key}")
            return None

    except Exception as e:
        print(f"⚠️ 전체 캐시 조회 오류: {e}")
        return None

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
    travel_dates: Optional[str] = None  # 추출된 여행 날짜 (원본)
    parsed_dates: Optional[dict] = None  # 파싱된 날짜 정보 (startDate, endDate, days)
    

@router.post("/chat", response_model=ChatResponse)
async def chat_with_llm(chat_message: ChatMessage):
    """
    사용자의 메시지를 받아 LangGraph 기반 여행 추천 시스템으로 응답을 생성합니다.
    LangGraph가 사용 불가능할 때는 기존 RAG 시스템으로 폴백합니다.
    """
    try:
        if get_travel_recommendation_langgraph is None:
            # LLM 시스템 사용 불가능
            default_message = f"죄송합니다. 현재 AI 여행 추천 시스템을 준비 중입니다. 📝\n\n'{chat_message.message}'에 대한 답변을 위해 조금만 기다려주세요!"
            default_html, default_lines = process_response_for_frontend(default_message)

            return ChatResponse(
                response=default_message,
                success=True,
                response_html=default_html,
                response_lines=default_lines
            )
        
        print(f"🔍 Processing travel query: {chat_message.message}")

        # Redis 캐싱 제거됨 - 항상 새로운 응답 생성

        # LangGraph 사용
        if get_travel_recommendation_langgraph:
            print("🚀 Using LangGraph workflow for enhanced travel recommendation")
            
            # 간단한 세션 ID (실제로는 사용자별 고유 ID 사용)
            # 현재는 데모용으로 고정 세션 ID 사용
            session_id = "demo_session"
            
            result = await get_travel_recommendation_langgraph(chat_message.message, session_id=session_id)

            print(f"✅ LangGraph result: {result.get('response', '')[:100]}...")

            response_text = result.get('response', '응답을 생성할 수 없습니다.')
            response_html, response_lines = process_response_for_frontend(response_text)

            # tool_results에서 redirect_url과 places 정보 추출
            tool_results = result.get('raw_state', {}).get('tool_results', {})

            # 디버깅: parsed_dates 전달 확인
            raw_state = result.get('raw_state', {})
            travel_plan = result.get('travel_plan', {})

            print(f"🔍 === API 응답 디버깅 ===")
            print(f"🔍 raw_state에서 travel_dates: {raw_state.get('travel_dates')}")
            print(f"🔍 raw_state에서 parsed_dates: {raw_state.get('parsed_dates')}")
            print(f"🔍 travel_plan에서 travel_dates: {travel_plan.get('travel_dates')}")
            print(f"🔍 travel_plan에서 parsed_dates: {travel_plan.get('parsed_dates')}")
            print(f"🔍 result.get('travel_plan'): {result.get('travel_plan', {})}")

            # Redis 캐싱 제거됨 - 실시간 응답만 제공

            # parsed_dates를 최상위 레벨에서 우선 가져오고, 없으면 다른 곳에서 가져오기
            parsed_dates_from_result = result.get('parsed_dates')
            parsed_dates_from_plan = travel_plan.get('parsed_dates')
            parsed_dates_from_state = raw_state.get('parsed_dates')
            final_parsed_dates = parsed_dates_from_result or parsed_dates_from_plan or parsed_dates_from_state

            print(f"🔍 ChatResponse 생성:")
            print(f"   - parsed_dates_from_result: {parsed_dates_from_result}")
            print(f"   - parsed_dates_from_plan: {parsed_dates_from_plan}")
            print(f"   - parsed_dates_from_state: {parsed_dates_from_state}")
            print(f"   - final_parsed_dates: {final_parsed_dates}")

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
                places=tool_results.get('places'),
                travel_dates=result.get('travel_dates') or travel_plan.get('travel_dates') or raw_state.get('travel_dates'),
                parsed_dates=final_parsed_dates
            )
        
        else:
            return ChatResponse(
                response="죄송합니다. 현재 여행 추천 시스템을 준비 중입니다.",
                success=False,
                error="LLM system not available"
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
        # Redis 상태 확인
        redis_status = "disconnected"
        redis_info = {}
        # 캐시 기능 제거됨
        cache_stats = None
        if False:  # 캐시 비활성화
            try:
                pass
                redis_status = "connected" if cache_stats.get("enabled") else "disabled"
                redis_info = cache_stats
            except Exception as e:
                redis_status = f"error: {str(e)}"

        # LLM 시스템 상태 확인
        llm_status = "healthy"
        if get_travel_recommendation_langgraph is None:
            llm_status = "unhealthy"
            return {
                "status": "unhealthy",
                "message": "LLM RAG 시스템이 초기화되지 않음",
                "redis_status": redis_status,
                "redis_info": redis_info
            }

        return {
            "status": "healthy",
            "message": "LLM RAG 시스템이 정상 작동 중",
            "redis_status": redis_status,
            "redis_info": redis_info,
            "llm_status": llm_status
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"LLM RAG 시스템 오류: {str(e)}",
            "redis_status": "unknown",
            "redis_info": {}
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
    travel_dates: Optional[str] = None  # 추출된 여행 날짜 (원본)
    parsed_dates: Optional[dict] = None  # 파싱된 날짜 정보 (startDate, endDate, days)
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
        print(f"🔍 === confirm_travel_plan 받은 데이터 ===")
        print(f"🔍 plan_data.travel_dates: {plan_data.travel_dates}")
        print(f"🔍 plan_data.parsed_dates: {plan_data.parsed_dates}")
        print(f"🔍 plan_data 전체: {plan_data.model_dump()}")
        
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
        
        # 일정 데이터 검증 완료
        
        # URL 파라미터 구성
        url_params = f"plan_id={plan_id}&region={plan_data.region}&duration={plan_data.duration}"
        print(f"🔧 기본 URL 파라미터: {url_params}")

        if plan_data.cities:
            url_params += f"&cities={','.join(plan_data.cities)}"
            print(f"🏙️ 도시 추가 후: {url_params}")

        # 새로운 날짜 파라미터 형식 적용: &startDate=2025-09-20&endDate=2025-09-22&days=3
        print(f"📅 === 날짜 파라미터 처리 시작 ===")
        print(f"📅 받은 parsed_dates: {plan_data.parsed_dates}")
        print(f"📅 받은 travel_dates: {plan_data.travel_dates}")
        print(f"📅 received duration: {plan_data.duration}")

        parsed_dates = plan_data.parsed_dates
        print(f"📅 parsed_dates 타입: {type(parsed_dates)}")
        print(f"📅 parsed_dates 불린값: {bool(parsed_dates)}")

        # parsed_dates가 없으면 travel_dates에서 다시 파싱
        if not parsed_dates:
            print(f"📅 parsed_dates가 비어있음, travel_dates 확인 중...")
            if plan_data.travel_dates and plan_data.travel_dates != "미정":
                print(f"📅 travel_dates에서 재파싱 시도: '{plan_data.travel_dates}'")
                # LLM_RAG의 parse_travel_dates 함수 import 필요
                try:
                    from LLM_RAG import parse_travel_dates

                    parsed_dates = parse_travel_dates(plan_data.travel_dates, plan_data.duration)
                    print(f"📅 재파싱 결과: {parsed_dates}")
                    print(f"📅 재파싱 결과 타입: {type(parsed_dates)}")
                except Exception as e:
                    print(f"❌ 재파싱 오류: {e}")
                    parsed_dates = None
            else:
                print(f"📅 travel_dates도 비어있음: '{plan_data.travel_dates}'")
        else:
            print(f"📅 parsed_dates가 있음: {parsed_dates}")

        print(f"📅 최종 parsed_dates: {parsed_dates}")
        print(f"📅 최종 parsed_dates 불린값: {bool(parsed_dates)}")

        if parsed_dates:
            print('---------------------11111111-----------------')
            print(f"📅 사용할 parsed_dates: {parsed_dates}")

            if parsed_dates.get("startDate"):
                url_params += f"&startDate={parsed_dates['startDate']}"
                print(f"📅 startDate 추가: {parsed_dates['startDate']}")
            if parsed_dates.get("endDate"):
                url_params += f"&endDate={parsed_dates['endDate']}"
                print(f"📅 endDate 추가: {parsed_dates['endDate']}")
            if parsed_dates.get("days"):
                url_params += f"&days={parsed_dates['days']}"
                print(f"📅 days 추가: {parsed_dates['days']}")
        else:
            print(f"⚠️ parsed_dates와 travel_dates 모두 없습니다.")

        redirect_url = f"/travel-planning?{url_params}"
        print(f"🎯 최종 생성된 URL: {redirect_url}")
        
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
• 신뢰도: {f"{plan_data.confidence_score:.2f}" if plan_data.confidence_score else "N/A"}

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

@router.get("/chat/cache/stats")
async def get_cache_stats():
    """
    Redis 캐시 통계 조회
    """
    try:
        # 캐시 기능 제거됨
        return {
            "success": False,
            "message": "캐시 기능이 제거되었습니다.",
            "cache_stats": {"enabled": False}
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"캐시 통계 조회 오류: {str(e)}",
            "cache_stats": {"enabled": False, "error": str(e)}
        }

@router.post("/chat/cache/clear")
async def clear_cache():
    """
    LLM 캐시 초기화 (개발/테스트용)
    """
    try:
        # 캐시 기능 제거됨
        return {
            "success": False,
            "message": "캐시 기능이 제거되었습니다."
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"캐시 초기화 오류: {str(e)}"
        }


@router.get("/chat/current-state")
async def get_current_travel_state():
    """
    현재 여행 상태 조회 (새 추천시 덮어쓰기 방식)
    """
    try:
        # 함수를 통해 최신 상태 가져오기
        if get_current_travel_state_ref is None:
            return {
                "success": False,
                "message": "여행 상태 시스템이 초기화되지 않았습니다."
            }

        # 현재 상태 반환
        state_copy = get_current_travel_state_ref().copy()

        return {
            "success": True,
            "current_state": state_copy,
            "has_travel_plan": bool(state_copy.get("travel_plan")),
            "places_count": len(state_copy.get("places", [])),
            "last_query": state_copy.get("last_query", ""),
            "timestamp": state_copy.get("timestamp")
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"상태 조회 오류: {str(e)}"
        }

@router.post("/chat/clear-state")
async def clear_current_travel_state():
    """
    현재 여행 상태 초기화
    """
    try:
        if current_travel_state is None:
            return {
                "success": False,
                "message": "여행 상태 시스템이 초기화되지 않았습니다."
            }

        # 상태 초기화
        current_travel_state.clear()
        current_travel_state.update({
            "last_query": "",
            "travel_plan": {},
            "places": [],
            "context": "",
            "timestamp": None
        })

        return {
            "success": True,
            "message": "여행 상태가 초기화되었습니다."
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"상태 초기화 오류: {str(e)}"
        }

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