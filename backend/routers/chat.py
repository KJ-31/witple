from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator
import json
import asyncio
import sys
import os
import hashlib
import re

# LLM_RAG.py를 임포트하기 위해 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from LLM_RAG import (
        get_travel_recommendation,
        get_travel_recommendation_optimized,
        get_travel_recommendation_langgraph,
        get_travel_recommendation_stream_async,
        get_travel_recommendation_langgraph_stream,
        llm_cache,
        current_travel_state,
        get_current_travel_state_ref,
        LANGGRAPH_AVAILABLE
    )
    print("✅ LLM_RAG module imported successfully")
    print(f"🔧 LangGraph 사용 가능: {LANGGRAPH_AVAILABLE}")
    print(f"🔧 get_travel_recommendation 함수: {get_travel_recommendation is not None}")
    print(f"🔧 get_travel_recommendation_langgraph 함수: {get_travel_recommendation_langgraph is not None}")
    print(f"🔧 get_travel_recommendation_stream_async 함수: {get_travel_recommendation_stream_async is not None}")
    print(f"🔧 get_travel_recommendation_langgraph_stream 함수: {get_travel_recommendation_langgraph_stream is not None}")
except ImportError as e:
    print(f"❌ Warning: Could not import LLM_RAG module: {e}")
    print("This is likely due to missing dependencies (langchain_aws, boto3, etc.)")
    import traceback
    traceback.print_exc()
    get_travel_recommendation = None
    get_travel_recommendation_optimized = None
    get_travel_recommendation_langgraph = None
    get_travel_recommendation_stream_async = None
    get_travel_recommendation_langgraph_stream = None
    llm_cache = None
    current_travel_state = None
    LANGGRAPH_AVAILABLE = False
except Exception as e:
    print(f"❌ Error initializing LLM_RAG module: {e}")
    import traceback
    traceback.print_exc()
    get_travel_recommendation = None
    get_travel_recommendation_optimized = None
    get_travel_recommendation_langgraph = None
    get_travel_recommendation_stream_async = None
    get_travel_recommendation_langgraph_stream = None
    llm_cache = None
    current_travel_state = None
    LANGGRAPH_AVAILABLE = False

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

        # 🚀 Redis 캐시 확인 (우선순위 1) - 확정 키워드 제외
        confirmation_keywords = ["확정", "확정해줘", "확정할게", "이 일정으로 확정", "네 확정", "yes", "ok"]
        is_confirmation = any(keyword in chat_message.message.lower() for keyword in confirmation_keywords)

        if llm_cache and llm_cache.enabled and not is_confirmation:
            # 확장된 캐시 데이터 조회
            cached_data = get_cached_full_response(llm_cache, chat_message.message)
            if cached_data:
                print("⚡ 캐시된 전체 응답 반환!")

                # 캐시된 데이터에서 여행 상태 복원
                if cached_data.get('travel_plan') and current_travel_state is not None:
                    import time
                    current_travel_state.update({
                        "last_query": chat_message.message,
                        "travel_plan": cached_data['travel_plan'],
                        "places": cached_data.get('places', []),
                        "context": cached_data.get('response', ''),
                        "timestamp": time.time()
                    })
                    print("📋 캐시된 응답으로 여행 상태 업데이트 완료")

                return ChatResponse(
                    response=cached_data.get('response', ''),
                    success=True,
                    travel_plan=cached_data.get('travel_plan'),
                    action_required=cached_data.get('action_required'),
                    formatted_response=cached_data.get('formatted_response'),
                    response_html=cached_data.get('response_html', ''),
                    response_lines=cached_data.get('response_lines', []),
                    redirect_url=cached_data.get('redirect_url'),
                    places=cached_data.get('places')
                )

            # 기존 단순 텍스트 캐시 폴백
            cached_response = llm_cache.get_cached_response(chat_message.message)
            if cached_response:
                print("⚡ 캐시된 기본 응답 반환!")
                response_html, response_lines = process_response_for_frontend(cached_response)

                return ChatResponse(
                    response=cached_response,
                    success=True,
                    response_html=response_html,
                    response_lines=response_lines
                )

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

            # 💾 응답 캐싱 (LangGraph 결과 - 확장된 데이터)
            if llm_cache and llm_cache.enabled and response_text and result.get('success', True):
                # 전체 ChatResponse 데이터 구성
                full_response_data = {
                    'response': response_text,
                    'travel_plan': result.get('travel_plan', {}),
                    'action_required': result.get('action_required'),
                    'formatted_response': result.get('raw_state', {}).get('formatted_ui_response'),
                    'response_html': response_html,
                    'response_lines': response_lines,
                    'redirect_url': tool_results.get('redirect_url'),
                    'places': tool_results.get('places')
                }

                # 확장된 캐시 저장
                cache_full_response(llm_cache, chat_message.message, full_response_data, expire=3600)  # 1시간

                # 기존 단순 텍스트 캐시도 호환성을 위해 저장
                llm_cache.cache_response(chat_message.message, response_text, expire=3600)  # 1시간
                print("💾 LangGraph 확장 응답 캐시 저장 완료")

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
        
        # LangGraph 사용 불가능 시 기존 RAG 시스템 사용 (성능 최적화)
        else:
            print("⚠️ LangGraph 사용 불가능, 고속 RAG 시스템으로 폴백")

            # 타임아웃과 함께 빠른 RAG 호출
            import asyncio
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(get_travel_recommendation, chat_message.message, False),
                    timeout=60.0  # 60초 타임아웃 (초기 로딩 고려)
                )
                print(f"✅ Got fast RAG response: {response[:100]}..." if len(response) > 100 else f"✅ Got response: {response}")

                # 💾 응답 캐싱 (기존 RAG 결과)
                if llm_cache and llm_cache.enabled and response:
                    llm_cache.cache_response(chat_message.message, response, expire=3600)  # 1시간
                    print("💾 RAG 응답 캐시 저장 완료")

            except asyncio.TimeoutError:
                response = "⏰ 요청 처리 시간이 초과되었습니다. 더 간단한 질문으로 다시 시도해주세요."
                print("❌ RAG response timeout")

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
        # Redis 상태 확인
        redis_status = "disconnected"
        redis_info = {}
        if llm_cache:
            try:
                cache_stats = llm_cache.get_cache_stats()
                redis_status = "connected" if cache_stats.get("enabled") else "disabled"
                redis_info = cache_stats
            except Exception as e:
                redis_status = f"error: {str(e)}"

        # LLM 시스템 상태 확인
        llm_status = "healthy"
        if get_travel_recommendation is None:
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
            "llm_status": llm_status,
            "langgraph_available": LANGGRAPH_AVAILABLE
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
        if llm_cache and llm_cache.enabled:
            stats = llm_cache.get_cache_stats()
            return {
                "success": True,
                "cache_stats": stats
            }
        else:
            return {
                "success": False,
                "message": "캐시가 비활성화되어 있습니다.",
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
        if llm_cache and llm_cache.enabled:
            # LLM 관련 키만 삭제
            llm_keys = llm_cache.redis.keys("llm:*")
            if llm_keys:
                deleted_count = llm_cache.redis.delete(*llm_keys)
                return {
                    "success": True,
                    "message": f"{deleted_count}개의 캐시 키가 삭제되었습니다."
                }
            else:
                return {
                    "success": True,
                    "message": "삭제할 캐시가 없습니다."
                }
        else:
            return {
                "success": False,
                "message": "캐시가 비활성화되어 있습니다."
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"캐시 초기화 오류: {str(e)}"
        }

@router.post("/chat/cache/benchmark")
async def benchmark_cache_performance():
    """
    캐시 성능 벤치마크 테스트
    """
    try:
        if not llm_cache or not llm_cache.enabled:
            return {
                "success": False,
                "message": "캐시가 비활성화되어 있습니다."
            }

        import time

        # 테스트 쿼리들
        test_queries = [
            "부산 2박 3일 여행 추천",
            "제주도 맛집 추천",
            "서울 핫플레이스",
            "강릉 바다 여행",
            "경주 역사 여행"
        ]

        benchmark_results = {
            "cache_enabled": True,
            "test_results": [],
            "summary": {}
        }

        total_cache_hits = 0
        total_cache_misses = 0
        cache_time_total = 0
        miss_time_total = 0

        for query in test_queries:
            # 캐시 미스 테스트 (캐시 초기화 후)
            cache_key = llm_cache._generate_cache_key(query)
            llm_cache.redis.delete(cache_key)

            miss_start = time.time()
            cached_response = llm_cache.get_cached_response(query)
            miss_time = time.time() - miss_start

            # 테스트 응답 캐싱
            test_response = f"테스트 응답: {query}에 대한 샘플 여행 추천입니다."
            llm_cache.cache_response(query, test_response, expire=300)  # 5분

            # 캐시 히트 테스트
            hit_start = time.time()
            cached_response = llm_cache.get_cached_response(query)
            hit_time = time.time() - hit_start

            if cached_response:
                total_cache_hits += 1
                cache_time_total += hit_time
            else:
                total_cache_misses += 1
                miss_time_total += miss_time

            benchmark_results["test_results"].append({
                "query": query,
                "cache_hit": cached_response is not None,
                "hit_time_ms": round(hit_time * 1000, 2),
                "miss_time_ms": round(miss_time * 1000, 2),
                "speedup": round(miss_time / hit_time, 1) if hit_time > 0 else 0
            })

        # 요약 통계
        avg_cache_time = (cache_time_total / total_cache_hits) if total_cache_hits > 0 else 0
        avg_miss_time = (miss_time_total / total_cache_misses) if total_cache_misses > 0 else 0

        benchmark_results["summary"] = {
            "total_tests": len(test_queries),
            "cache_hits": total_cache_hits,
            "cache_misses": total_cache_misses,
            "avg_cache_time_ms": round(avg_cache_time * 1000, 2),
            "avg_miss_time_ms": round(avg_miss_time * 1000, 2),
            "average_speedup": round(avg_miss_time / avg_cache_time, 1) if avg_cache_time > 0 else 0,
            "cache_hit_rate": f"{(total_cache_hits / len(test_queries)) * 100:.1f}%"
        }

        return {
            "success": True,
            "benchmark": benchmark_results
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"벤치마크 테스트 오류: {str(e)}"
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