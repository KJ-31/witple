"""
채팅 명령 핸들러들
"""
from typing import List, Optional
from core.interfaces import CommandHandler, ChatContext, ChatResponse
from utils.response_formatter import process_response_for_frontend


class DemoCommandHandler(CommandHandler):
    """데모 명령 처리기"""

    @property
    def priority(self) -> int:
        return 1  # 높은 우선순위

    @property
    def name(self) -> str:
        return "demo_command"

    async def can_handle(self, message: str, context: ChatContext) -> bool:
        """데모 명령인지 확인"""
        return message.strip().lower().startswith('demo:')

    async def handle(self, message: str, context: ChatContext) -> ChatResponse:
        """데모 명령 처리"""
        try:
            demo_manager = context.get_demo_manager()
            if not demo_manager:
                return ChatResponse(
                    response="데모 매니저를 사용할 수 없습니다.",
                    success=False,
                    error="Demo manager not available",
                    session_id=context.session_id
                )

            message_lower = message.strip().lower()
            demo_command = message_lower.split('demo:')[1].strip()

            if demo_command == 'true':
                response_text = demo_manager.enable_demo_mode()
            elif demo_command == 'false':
                response_text = demo_manager.disable_demo_mode()
            elif demo_command == 'status':
                status = demo_manager.get_status()
                response_text = self._format_status_message(status)
            else:
                response_text = self._format_help_message()

            response_html, response_lines = process_response_for_frontend(response_text)

            return ChatResponse(
                response=response_text,
                success=True,
                response_html=response_html,
                response_lines=response_lines,
                session_id=context.session_id
            )

        except Exception as e:
            error_message = f"데모 명령 처리 중 오류가 발생했습니다: {str(e)}"
            response_html, response_lines = process_response_for_frontend(error_message)

            return ChatResponse(
                response=error_message,
                success=False,
                error=str(e),
                response_html=response_html,
                response_lines=response_lines,
                session_id=context.session_id
            )

    def _format_status_message(self, status: dict) -> str:
        """상태 메시지 포맷"""
        response_text = f"📊 **데모 모드 상태**\n\n"
        response_text += f"• 현재 상태: {'🎭 활성화' if status['demo_mode'] else '✅ 비활성화'}\n"
        response_text += f"• 데모용 장소 수: {status['demo_places_count']}개\n"
        if status['demo_mode']:
            demo_places = status.get('demo_places', [])
            response_text += f"• 데모용 장소들: {', '.join(demo_places[:5])}{'...' if len(demo_places) > 5 else ''}"
        return response_text

    def _format_help_message(self) -> str:
        """도움말 메시지 포맷"""
        return (f"❌ 잘못된 데모 명령입니다.\n\n"
                f"사용법:\n"
                f"• `DEMO:true` - 데모 모드 활성화\n"
                f"• `DEMO:false` - 데모 모드 비활성화\n"
                f"• `DEMO:status` - 현재 상태 확인")


class TravelRecommendationHandler(CommandHandler):
    """여행 추천 처리기"""

    @property
    def priority(self) -> int:
        return 10  # 낮은 우선순위 (기본 처리)

    @property
    def name(self) -> str:
        return "travel_recommendation"

    async def can_handle(self, message: str, context: ChatContext) -> bool:
        """여행 관련 메시지인지 확인"""
        travel_keywords = ["추천", "여행", "일정", "계획", "가고싶어", "놀러"]
        return any(keyword in message for keyword in travel_keywords)

    async def handle(self, message: str, context: ChatContext) -> ChatResponse:
        """여행 추천 처리"""
        try:
            # LangGraph 함수 가져오기
            from LLM_RAG import get_travel_recommendation_langgraph

            if not get_travel_recommendation_langgraph:
                return ChatResponse(
                    response="현재 AI 여행 추천 시스템을 준비 중입니다. 📝\n\n잠시만 기다려주세요!",
                    success=True,
                    session_id=context.session_id
                )

            print(f"🚀 Using LangGraph workflow for enhanced travel recommendation")

            # LangGraph로 처리
            result = await get_travel_recommendation_langgraph(
                message,
                session_id=context.session_id,
                user_id=context.user_id
            )

            print(f"✅ LangGraph result: {result.get('content', '')[:100]}...")

            response_text = result.get('content', '응답을 생성할 수 없습니다.')
            response_html, response_lines = process_response_for_frontend(response_text)

            # 구조화된 데이터 추출
            travel_plan = result.get('travel_plan', {})
            formatted_ui_response = result.get('formatted_ui_response', {})
            tool_results = result.get('tool_results', {})
            redirect_url = tool_results.get('redirect_url')

            # 날짜 정보 추출
            travel_dates = travel_plan.get('travel_dates', '')
            parsed_dates = travel_plan.get('parsed_dates', {})

            return ChatResponse(
                response=response_text,
                success=result.get('type') != 'error',
                travel_plan=travel_plan,
                error=result.get('content') if result.get('type') == 'error' else None,
                formatted_response=formatted_ui_response,
                response_html=response_html,
                response_lines=response_lines,
                redirect_url=redirect_url,
                places=travel_plan.get('places', []),
                travel_dates=travel_dates,
                parsed_dates=parsed_dates,
                session_id=context.session_id
            )

        except Exception as e:
            print(f"❌ Travel recommendation error: {e}")
            import traceback
            traceback.print_exc()

            error_message = "죄송합니다. 현재 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
            error_html, error_lines = process_response_for_frontend(error_message)

            return ChatResponse(
                response=error_message,
                success=False,
                error=str(e),
                response_html=error_html,
                response_lines=error_lines,
                session_id=context.session_id
            )


class GeneralChatHandler(CommandHandler):
    """일반 채팅 처리기 (폴백)"""

    @property
    def priority(self) -> int:
        return 100  # 가장 낮은 우선순위

    @property
    def name(self) -> str:
        return "general_chat"

    async def can_handle(self, message: str, context: ChatContext) -> bool:
        """모든 메시지를 처리할 수 있음 (폴백)"""
        return True

    async def handle(self, message: str, context: ChatContext) -> ChatResponse:
        """일반 채팅 처리"""
        try:
            # 기본 응답 생성
            default_message = f"안녕하세요! 여행 추천을 원하시면 '부산 여행 추천해주세요' 같은 방식으로 말씀해주세요. 📝\n\n'{message}'에 대해 더 구체적으로 알려주시면 도움을 드릴 수 있습니다!"
            default_html, default_lines = process_response_for_frontend(default_message)

            return ChatResponse(
                response=default_message,
                success=True,
                response_html=default_html,
                response_lines=default_lines,
                session_id=context.session_id
            )

        except Exception as e:
            error_message = "죄송합니다. 메시지 처리 중 오류가 발생했습니다."
            error_html, error_lines = process_response_for_frontend(error_message)

            return ChatResponse(
                response=error_message,
                success=False,
                error=str(e),
                response_html=error_html,
                response_lines=error_lines,
                session_id=context.session_id
            )


class ChatCommandProcessor:
    """채팅 명령 처리기"""

    def __init__(self, handlers: List[CommandHandler]):
        # 우선순위 순으로 정렬
        self.handlers = sorted(handlers, key=lambda h: h.priority)

    async def process(self, message: str, context: ChatContext) -> ChatResponse:
        """메시지를 적절한 핸들러로 처리"""
        print(f"🔍 메시지 처리 시작: '{message[:50]}...' (session: {context.session_id})")

        for handler in self.handlers:
            try:
                if await handler.can_handle(message, context):
                    print(f"✅ 핸들러 선택: {handler.name} (우선순위: {handler.priority})")
                    return await handler.handle(message, context)
            except Exception as e:
                print(f"❌ 핸들러 {handler.name} 처리 중 오류: {e}")
                # 다음 핸들러로 계속

        # 여기에 도달하면 안 되지만, 안전장치
        error_message = "죄송합니다. 메시지를 처리할 수 없습니다."
        error_html, error_lines = process_response_for_frontend(error_message)

        return ChatResponse(
            response=error_message,
            success=False,
            error="No handler could process the message",
            response_html=error_html,
            response_lines=error_lines,
            session_id=context.session_id
        )


def create_default_chat_processor() -> ChatCommandProcessor:
    """기본 채팅 처리기 생성"""
    handlers = [
        DemoCommandHandler(),
        TravelRecommendationHandler(),
        GeneralChatHandler()  # 폴백 핸들러
    ]
    return ChatCommandProcessor(handlers)