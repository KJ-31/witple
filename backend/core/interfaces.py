"""
서비스 인터페이스 정의
"""
from typing import Protocol, List, Dict, Any, Optional
from abc import ABC, abstractmethod


class LLMService(Protocol):
    """LLM 서비스 인터페이스"""
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """LLM 응답 생성"""
        ...


class DatabaseService(Protocol):
    """데이터베이스 서비스 인터페이스"""
    async def search_places(self, query: str) -> List[Dict]:
        """장소 검색"""
        ...

    async def get_filtered_documents(self, filters: Dict) -> List[Dict]:
        """필터링된 문서 조회"""
        ...


class SessionService(Protocol):
    """세션 서비스 인터페이스"""
    async def get_session(self, session_id: str) -> Optional[Dict]:
        """세션 조회"""
        ...

    async def save_session(self, session_id: str, data: Dict) -> bool:
        """세션 저장"""
        ...


# 채팅 명령 처리를 위한 인터페이스와 모델들

class ChatContext:
    """채팅 처리 컨텍스트"""
    def __init__(self, user_id: str, session_id: str, db_session=None):
        self.user_id = user_id
        self.session_id = session_id
        self.db_session = db_session
        self._services = {}

    def get_service(self, service_name: str):
        """서비스 인스턴스 조회"""
        return self._services.get(service_name)

    def set_service(self, service_name: str, service):
        """서비스 인스턴스 설정"""
        self._services[service_name] = service

    def get_demo_manager(self):
        """데모 매니저 조회"""
        return self._services.get('demo_manager')


class ChatResponse:
    """채팅 응답 모델"""
    def __init__(self, response: str, success: bool = True, **kwargs):
        self.response = response
        self.success = success
        self.error = kwargs.get('error')
        self.travel_plan = kwargs.get('travel_plan')
        self.action_required = kwargs.get('action_required')
        self.formatted_response = kwargs.get('formatted_response')
        self.response_html = kwargs.get('response_html')
        self.response_lines = kwargs.get('response_lines')
        self.redirect_url = kwargs.get('redirect_url')
        self.places = kwargs.get('places')
        self.travel_dates = kwargs.get('travel_dates')
        self.parsed_dates = kwargs.get('parsed_dates')
        self.session_id = kwargs.get('session_id')

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'response': self.response,
            'success': self.success,
            'error': self.error,
            'travel_plan': self.travel_plan,
            'action_required': self.action_required,
            'formatted_response': self.formatted_response,
            'response_html': self.response_html,
            'response_lines': self.response_lines,
            'redirect_url': self.redirect_url,
            'places': self.places,
            'travel_dates': self.travel_dates,
            'parsed_dates': self.parsed_dates,
            'session_id': self.session_id
        }


class CommandHandler(ABC):
    """명령 처리기 추상 클래스"""

    @abstractmethod
    async def can_handle(self, message: str, context: ChatContext) -> bool:
        """메시지를 처리할 수 있는지 확인"""
        pass

    @abstractmethod
    async def handle(self, message: str, context: ChatContext) -> ChatResponse:
        """메시지 처리"""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """핸들러 우선순위 (낮을수록 높은 우선순위)"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """핸들러 이름"""
        pass