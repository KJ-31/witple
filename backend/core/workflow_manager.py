"""
워크플로우 관리 및 라우팅
"""
from typing import Literal, Dict, Any, List
from datetime import datetime, timedelta
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from core.travel_context import get_travel_context
from core.workflow_nodes import (
    TravelState, classify_query, rag_processing_node, information_search_node,
    search_processing_node, general_chat_node, confirmation_processing_node,
    integrate_response_node
)
from utils.entity_extractor import detect_query_entities

# LangGraph 의존성 임포트 (선택적)
try:
    from langgraph.graph import StateGraph, START, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("⚠️ LangGraph를 사용할 수 없습니다. 기본 처리 모드로 실행됩니다.")
    StateGraph = None
    START = None
    END = None
    LANGGRAPH_AVAILABLE = False


def route_execution(state: TravelState) -> str:
    """단일 노드 실행을 위한 라우팅 결정 (우선순위 기반)"""

    # 확정 요청이 최고 우선순위
    if state.get("need_confirmation"):
        return "confirmation_processing"

    # 의도별 라우팅
    if state.get("need_rag"):
        # 의도 분류 결과 확인
        user_query = state.get("messages", [""])[-1] if state.get("messages") else ""
        try:
            context = get_travel_context()
            entities = detect_query_entities(user_query, context.llm, context.db_catalogs)
            intent = entities.get("intent", "general")

            if intent == "place_search":
                return "information_search"
            else:
                return "rag_processing"  # travel_planning 등
        except:
            return "rag_processing"  # 폴백

    # 장소 검색
    if state.get("need_search"):
        return "search_processing"

    # 기본: 일반 채팅
    return "general_chat"


def check_completion(state: TravelState) -> Literal["continue", "end"]:
    """대화 완료 여부 확인"""
    # 확정된 일정이 있고 도구 실행 결과가 있으면 종료
    if (state.get("travel_plan", {}).get("status") == "confirmed" and
        state.get("tool_results", {}).get("action") == "redirect_to_planning_page"):
        return "end"

    # 기본적으로 대화 지속
    return "continue"


def create_travel_workflow():
    """여행 추천 LangGraph 워크플로우 생성"""
    if not LANGGRAPH_AVAILABLE:
        return None

    workflow = StateGraph(TravelState)

    # 노드 추가
    workflow.add_node("classify", classify_query)
    workflow.add_node("rag_processing", rag_processing_node)
    workflow.add_node("information_search", information_search_node)
    workflow.add_node("search_processing", search_processing_node)
    workflow.add_node("general_chat", general_chat_node)
    workflow.add_node("confirmation_processing", confirmation_processing_node)
    workflow.add_node("integrate_response", integrate_response_node)

    # 엣지 구성
    workflow.add_edge(START, "classify")
    workflow.add_conditional_edges("classify", route_execution)

    # 모든 처리 노드들이 통합 노드로 수렴
    workflow.add_edge("rag_processing", "integrate_response")
    workflow.add_edge("information_search", "integrate_response")
    workflow.add_edge("search_processing", "integrate_response")
    workflow.add_edge("general_chat", "integrate_response")
    workflow.add_edge("confirmation_processing", "integrate_response")

    # 완료 확인
    workflow.add_conditional_edges(
        "integrate_response",
        check_completion,
        {
            "continue": END,  # 추가 대화 없이 종료로 변경
            "end": END
        }
    )

    return workflow.compile()


class TravelWorkflowManager:
    """여행 워크플로우 관리자 (세션별 상태 관리)"""

    def __init__(self):
        self.workflow = create_travel_workflow() if LANGGRAPH_AVAILABLE else None
        # 세션별 상태 관리 (스레드 안전성 보장)
        self.session_states = {}  # session_id: state_dict
        self.session_timestamps = {}  # session_id: last_access_time
        self.session_timeout = timedelta(hours=2)  # 2시간 타임아웃
        self._session_lock = threading.Lock()  # 레이스 컨디션 방지

        # 안전한 세션 정리를 위한 스케줄러
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            func=self._cleanup_expired_sessions,
            trigger='interval',
            minutes=10,
            max_instances=1,  # 중복 실행 방지
            coalesce=True,    # 지연된 작업 합치기
            id='session_cleanup'
        )
        self._scheduler.start()

        # 앱 종료시 안전한 정리
        atexit.register(self._safe_shutdown)

        # 호환성을 위한 기본 상태 (기존 코드와의 호환성)
        self.current_travel_state = {
            "last_query": "",
            "travel_plan": {},
            "places": [],
            "context": "",
            "timestamp": None
        }

    def get_current_travel_state_ref(self) -> Dict[str, Any]:
        """현재 여행 상태 참조 반환 (호환성)"""
        return self.current_travel_state

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """세션별 여행 상태 조회 (스레드 안전)"""
        with self._session_lock:
            if session_id not in self.session_states:
                self.session_states[session_id] = {
                    "last_query": "",
                    "travel_plan": {},
                    "places": [],
                    "context": "",
                    "timestamp": None
                }

            # 세션 접근 시간 업데이트
            self.session_timestamps[session_id] = datetime.now()
            return self.session_states[session_id].copy()  # 깊은 복사로 반환

    def reset_travel_state(self, session_id: str = None):
        """여행 상태 초기화 (스레드 안전)"""
        if session_id:
            # 특정 세션 초기화
            with self._session_lock:
                self.session_states[session_id] = {
                    "last_query": "",
                    "travel_plan": {},
                    "places": [],
                    "context": "",
                    "timestamp": None
                }
                self.session_timestamps[session_id] = datetime.now()
        else:
            # 기본 상태 초기화 (호환성)
            self.current_travel_state.clear()
            self.current_travel_state.update({
                "last_query": "",
                "travel_plan": {},
                "places": [],
                "context": "",
                "timestamp": None
            })

    def update_travel_state(self, new_state: Dict[str, Any], session_id: str = None):
        """여행 상태 업데이트 (스레드 안전)"""
        if session_id:
            with self._session_lock:
                if session_id not in self.session_states:
                    # 상태 초기화 (락 내부에서)
                    self.session_states[session_id] = {
                        "last_query": "",
                        "travel_plan": {},
                        "places": [],
                        "context": "",
                        "timestamp": None
                    }
                self.session_states[session_id].update(new_state)
                self.session_timestamps[session_id] = datetime.now()
        else:
            # 기본 상태 업데이트 (호환성)
            self.current_travel_state.update(new_state)

    def _cleanup_expired_sessions(self):
        """만료된 세션 정리 (스케줄러 기반 - 스레드 안전)"""
        try:
            current_time = datetime.now()
            expired_sessions = []

            # 만료된 세션 식별 (락으로 보호)
            with self._session_lock:
                for session_id, last_access in list(self.session_timestamps.items()):
                    if current_time - last_access > self.session_timeout:
                        expired_sessions.append(session_id)

                # 만료된 세션 정리
                for session_id in expired_sessions:
                    print(f"🧹 만료된 세션 정리: {session_id}")
                    self.session_states.pop(session_id, None)
                    self.session_timestamps.pop(session_id, None)

            if expired_sessions:
                print(f"✅ {len(expired_sessions)}개 만료 세션 정리 완료")

        except Exception as e:
            print(f"❌ 세션 정리 중 오류: {e}")
            # 예외 발생해도 스케줄러는 계속 작동

    def _safe_shutdown(self):
        """안전한 종료 처리"""
        try:
            if hasattr(self, '_scheduler') and self._scheduler.running:
                print("🛑 워크플로우 매니저 스케줄러 종료 중...")
                self._scheduler.shutdown(wait=False)
                print("✅ 워크플로우 매니저 안전하게 종료됨")
        except Exception as e:
            print(f"❌ 워크플로우 매니저 종료 중 오류: {e}")

    def get_session_count(self) -> int:
        """현재 활성 세션 수 조회 (스레드 안전)"""
        with self._session_lock:
            return len(self.session_states)

    def process_simple_fallback(self, query: str, conversation_history: List[str] = None) -> Dict[str, Any]:
        """LangGraph 없이 단순 처리"""
        print("🔄 단순 처리 모드 (LangGraph 없음)")

        context = get_travel_context()

        # 초기 상태 생성
        state: TravelState = {
            "messages": [query],
            "need_rag": True,  # 기본값
            "need_search": False,
            "need_confirmation": False,
            "query_type": "simple",
            "travel_plan": {},
            "user_preferences": {},
            "conversation_context": "",
            "formatted_ui_response": {},
            "rag_results": [],
            "travel_dates": "",
            "parsed_dates": {}
        }

        try:
            # 1. 분류
            state = classify_query(state)

            # 2. 라우팅에 따른 처리
            route = route_execution(state)
            print(f"🛤️ 라우팅 결과: {route}")

            if route == "rag_processing":
                state = rag_processing_node(state)
            elif route == "information_search":
                state = information_search_node(state)
            elif route == "search_processing":
                state = search_processing_node(state)
            elif route == "confirmation_processing":
                state = confirmation_processing_node(state)
            else:
                state = general_chat_node(state)

            # 3. 응답 통합
            state = integrate_response_node(state)

            # 상태 업데이트
            if state.get("travel_plan"):
                self.update_travel_state({
                    "last_query": query,
                    "travel_plan": state["travel_plan"],
                    "context": state.get("conversation_context", ""),
                    "timestamp": "auto"
                })

            # tool_results 정보 추출 (리다이렉트 등의 액션 처리용)
            tool_results = state.get("tool_results", {})

            return {
                "content": state.get("final_response", state.get("conversation_context", "응답을 생성할 수 없습니다.")),
                "type": "text",
                "travel_plan": state.get("travel_plan", {}),
                "formatted_ui_response": state.get("formatted_ui_response", {}),
                "rag_results": state.get("rag_results", []),
                "action_required": tool_results.get("action"),
                "redirect_url": tool_results.get("redirect_url"),
                "tool_results": tool_results
            }

        except Exception as e:
            print(f"❌ 단순 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                "content": f"처리 중 오류가 발생했습니다: {str(e)}",
                "type": "error"
            }

    async def process_query(self, query: str, conversation_history: List[str] = None, user_id: str = None, session_id: str = None) -> Dict[str, Any]:
        """쿼리 처리 (LangGraph 또는 단순 처리)"""
        print(f"🔍 쿼리 처리 시작: '{query}' (session: {session_id})")

        # 세션별 상태 관리
        if session_id:
            session_state = self.get_session_state(session_id)
            existing_travel_plan = session_state.get("travel_plan", {})
            print(f"🔍 세션 {session_id} 기존 상태: {bool(existing_travel_plan)}")

            # 새로운 여행 요청인지 확인하여 상태 초기화
            travel_keywords = ["추천", "여행", "일정", "계획", "가고싶어", "놀러"]
            if any(keyword in query for keyword in travel_keywords):
                print(f"🔄 새로운 여행 요청 감지 - 세션 {session_id} 상태 초기화")
                self.reset_travel_state(session_id)
                existing_travel_plan = {}
            else:
                # 기존 상태 유지
                session_state["last_query"] = query
                session_state["timestamp"] = "auto"
        else:
            # 기본 상태 사용 (호환성)
            existing_travel_plan = self.current_travel_state.get("travel_plan", {})
            print(f"🔍 기본 상태: {bool(existing_travel_plan)}")

            travel_keywords = ["추천", "여행", "일정", "계획", "가고싶어", "놀러"]
            if any(keyword in query for keyword in travel_keywords):
                print("🔄 새로운 여행 요청 감지 - 기본 상태 초기화")
                self.reset_travel_state()
            else:
                self.current_travel_state["last_query"] = query
                self.current_travel_state["timestamp"] = "auto"

        # LangGraph 사용 가능하면 워크플로우 실행, 아니면 단순 처리
        if self.workflow:
            try:
                # 초기 상태 구성
                initial_state: TravelState = {
                    "messages": [query],
                    "need_rag": False,
                    "need_search": False,
                    "need_confirmation": False,
                    "query_type": "simple",
                    "travel_plan": existing_travel_plan,
                    "user_preferences": {},
                    "conversation_context": "",
                    "formatted_ui_response": {},
                    "rag_results": [],
                    "travel_dates": "",
                    "parsed_dates": {},
                    "tool_results": {},
                    "user_id": user_id or "guest_user",
                    "session_id": session_id or "default_session"
                }

                # 워크플로우 실행
                print("🔄 LangGraph 워크플로우 실행")
                result = await self.workflow.ainvoke(initial_state)

                # 상태 업데이트
                if result.get("travel_plan"):
                    self.update_travel_state({
                        "last_query": query,
                        "travel_plan": result["travel_plan"],
                        "context": result.get("conversation_context", ""),
                        "timestamp": "auto"
                    })

                # tool_results에서 redirect_url 추출
                tool_results = result.get("tool_results", {})
                redirect_url = tool_results.get("redirect_url") if tool_results else None

                response_data = {
                    "content": result.get("final_response", result.get("conversation_context", "응답을 생성할 수 없습니다.")),
                    "type": "text",
                    "travel_plan": result.get("travel_plan", {}),
                    "formatted_ui_response": result.get("formatted_ui_response", {}),
                    "rag_results": result.get("rag_results", []),
                    "tool_results": tool_results
                }

                # redirect_url이 있으면 응답에 포함
                if redirect_url:
                    response_data["redirect_url"] = redirect_url
                    print(f"🗺️ 리다이렉트 URL 포함: {redirect_url}")

                return response_data

            except Exception as e:
                print(f"❌ LangGraph 워크플로우 오류: {e}")
                # 폴백: 단순 처리
                return self.process_simple_fallback(query, conversation_history)
        else:
            # 단순 처리
            return self.process_simple_fallback(query, conversation_history)


# 전역 워크플로우 관리자 인스턴스
_workflow_manager: TravelWorkflowManager = None


def get_workflow_manager() -> TravelWorkflowManager:
    """전역 워크플로우 관리자 반환"""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = TravelWorkflowManager()
    return _workflow_manager


def initialize_workflow_manager() -> TravelWorkflowManager:
    """워크플로우 관리자 초기화"""
    global _workflow_manager
    _workflow_manager = TravelWorkflowManager()
    print("✅ 워크플로우 관리자 초기화 완료")
    return _workflow_manager