"""
리팩토링된 채팅 라우터 - 명령 패턴과 통합 에러 처리 적용
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from database import get_db
from auth_utils import get_current_user
from models import User
import uuid

# 새로운 구조 임포트
from core.interfaces import ChatContext
from core.command_handlers import create_default_chat_processor
from core.error_handling import get_error_handler, ErrorFactory, error_handler_decorator
from utils.demo_mode import get_demo_manager

router = APIRouter()

# 전역 인스턴스들
chat_processor = create_default_chat_processor()
error_handler = get_error_handler()

# 요청 처리 상태 관리 (간단한 메모리 기반)
processing_requests = set()


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    success: bool
    error: Optional[str] = None
    travel_plan: Optional[dict] = None
    action_required: Optional[str] = None
    formatted_response: Optional[dict] = None
    response_html: Optional[str] = None
    response_lines: Optional[List[str]] = None
    redirect_url: Optional[str] = None
    places: Optional[List[dict]] = None
    travel_dates: Optional[str] = None
    parsed_dates: Optional[dict] = None
    session_id: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_llm_refactored(
    chat_message: ChatMessage,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    리팩토링된 채팅 엔드포인트 - 명령 패턴과 통합 에러 처리 적용
    """
    # 세션 ID 처리
    session_id = chat_message.session_id or str(uuid.uuid4())
    print(f"🔑 Session ID: {session_id}")

    # 중복 요청 방지
    request_key = f"{session_id}_{chat_message.message[:50]}_{hash(chat_message.message)}"
    if request_key in processing_requests:
        print(f"⚠️ 중복 요청 감지, 무시: {request_key}")
        error = ErrorFactory.create_user_error(
            "Duplicate request",
            "이미 처리 중인 요청입니다. 잠시만 기다려주세요."
        )
        return error_handler.handle_error(error, {"session_id": session_id}).to_dict()

    processing_requests.add(request_key)

    try:
        # ChatContext 생성
        context = ChatContext(
            user_id=current_user.user_id,
            session_id=session_id,
            db_session=db
        )

        # 서비스들 설정
        context.set_service('demo_manager', get_demo_manager())

        print(f"🔍 Processing message: {chat_message.message}")

        # 명령 패턴으로 메시지 처리
        response = await chat_processor.process(chat_message.message, context)

        return response.to_dict()

    except Exception as e:
        print(f"❌ Chat API error: {e}")
        import traceback
        traceback.print_exc()

        # 통합 에러 처리
        error = ErrorFactory.create_system_error(
            f"Chat processing failed: {str(e)}",
            e,
            {"session_id": session_id, "user_id": current_user.user_id}
        )

        return error_handler.handle_error(error, {"session_id": session_id}).to_dict()

    finally:
        # 요청 처리 완료 후 키 제거
        processing_requests.discard(request_key)


@router.get("/chat/health")
async def chat_health_refactored():
    """
    리팩토링된 헬스체크 엔드포인트
    """
    try:
        # LLM 시스템 상태 확인
        try:
            from LLM_RAG import get_travel_recommendation_langgraph
            llm_available = get_travel_recommendation_langgraph is not None
        except ImportError:
            llm_available = False

        if not llm_available:
            error = ErrorFactory.create_external_error(
                "LLM RAG system not initialized",
                service_name="LLM"
            )
            response = error_handler.handle_error(error).to_dict()
            return {
                "status": "unhealthy",
                "message": response["response"],
                "llm_status": "unavailable"
            }

        return {
            "status": "healthy",
            "message": "리팩토링된 LLM RAG 시스템이 정상 작동 중",
            "llm_status": "available",
            "processors": [
                {"name": handler.name, "priority": handler.priority}
                for handler in chat_processor.handlers
            ]
        }

    except Exception as e:
        error = ErrorFactory.create_system_error(
            f"Health check failed: {str(e)}",
            e
        )
        response = error_handler.handle_error(error).to_dict()
        return {
            "status": "unhealthy",
            "message": response["response"],
            "error": str(e)
        }


# 기존 엔드포인트들을 리팩토링된 에러 처리로 감싸기

@router.get("/chat/current-state")
async def get_current_travel_state_refactored():
    """
    현재 여행 상태 조회 - 리팩토링된 에러 처리 적용
    """
    try:
        from core.workflow_manager import get_workflow_manager

        workflow_manager = get_workflow_manager()
        get_current_travel_state_ref = workflow_manager.get_current_travel_state_ref

        if get_current_travel_state_ref is None:
            error = ErrorFactory.create_system_error(
                "Travel state system not initialized",
                context={"component": "workflow_manager"}
            )
            response = error_handler.handle_error(error).to_dict()
            return {
                "success": False,
                "message": response["response"]
            }

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
        error = ErrorFactory.create_system_error(
            f"State retrieval failed: {str(e)}",
            e
        )
        response = error_handler.handle_error(error).to_dict()
        return {
            "success": False,
            "message": response["response"]
        }


@router.post("/chat/clear-state")
async def clear_current_travel_state_refactored():
    """
    현재 여행 상태 초기화 - 리팩토링된 에러 처리 적용
    """
    try:
        from core.workflow_manager import get_workflow_manager

        workflow_manager = get_workflow_manager()
        get_current_travel_state_ref = workflow_manager.get_current_travel_state_ref

        if get_current_travel_state_ref is None:
            error = ErrorFactory.create_system_error(
                "Travel state system not initialized",
                context={"component": "workflow_manager"}
            )
            response = error_handler.handle_error(error).to_dict()
            return {
                "success": False,
                "message": response["response"]
            }

        # 워크플로우 매니저를 통해 상태 초기화
        workflow_manager.reset_travel_state()

        return {
            "success": True,
            "message": "여행 상태가 초기화되었습니다."
        }

    except Exception as e:
        error = ErrorFactory.create_system_error(
            f"State clearing failed: {str(e)}",
            e
        )
        response = error_handler.handle_error(error).to_dict()
        return {
            "success": False,
            "message": response["response"]
        }