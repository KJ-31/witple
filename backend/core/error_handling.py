"""
통합된 에러 처리 시스템
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
import logging
import traceback
from core.interfaces import ChatResponse


class ErrorType(Enum):
    """에러 타입 분류"""
    SYSTEM_ERROR = "system_error"      # 시스템 내부 오류
    USER_ERROR = "user_error"          # 사용자 입력 오류
    EXTERNAL_ERROR = "external_error"  # 외부 서비스 오류 (DB, LLM 등)
    VALIDATION_ERROR = "validation_error"  # 데이터 검증 오류


@dataclass
class TravelError:
    """여행 시스템 에러 모델"""
    error_type: ErrorType
    message: str
    user_message: str
    details: Optional[Dict[str, Any]] = None
    original_exception: Optional[Exception] = None
    context: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.context is None:
            self.context = {}


class ErrorHandler:
    """중앙화된 에러 처리기"""

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self._error_templates = self._init_error_templates()

    def _init_error_templates(self) -> Dict[ErrorType, str]:
        """에러 타입별 사용자 메시지 템플릿"""
        return {
            ErrorType.SYSTEM_ERROR: "죄송합니다. 시스템에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            ErrorType.USER_ERROR: "입력하신 정보를 확인해주세요. {details}",
            ErrorType.EXTERNAL_ERROR: "외부 서비스와의 연결에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            ErrorType.VALIDATION_ERROR: "입력된 데이터에 문제가 있습니다. {details}"
        }

    def handle_error(self, error: TravelError, context: Dict[str, Any] = None) -> ChatResponse:
        """에러 처리 및 응답 생성"""
        # 로깅
        self._log_error(error, context)

        # 사용자 메시지 생성
        user_message = self._generate_user_message(error)

        # 응답 포맷팅
        from utils.response_formatter import process_response_for_frontend
        response_html, response_lines = process_response_for_frontend(user_message)

        return ChatResponse(
            response=user_message,
            success=False,
            error=error.message,
            response_html=response_html,
            response_lines=response_lines,
            session_id=context.get('session_id') if context else None
        )

    def _log_error(self, error: TravelError, context: Dict[str, Any] = None):
        """구조화된 로깅"""
        log_data = {
            "error_type": error.error_type.value,
            "message": error.message,
            "details": error.details,
            "user_id": context.get('user_id') if context else None,
            "session_id": context.get('session_id') if context else None,
            "context": error.context
        }

        if error.error_type == ErrorType.SYSTEM_ERROR:
            self.logger.error(
                f"System error: {error.message}",
                extra=log_data,
                exc_info=error.original_exception
            )
        elif error.error_type == ErrorType.EXTERNAL_ERROR:
            self.logger.warning(
                f"External service error: {error.message}",
                extra=log_data,
                exc_info=error.original_exception
            )
        elif error.error_type == ErrorType.USER_ERROR:
            self.logger.info(
                f"User error: {error.message}",
                extra=log_data
            )
        elif error.error_type == ErrorType.VALIDATION_ERROR:
            self.logger.warning(
                f"Validation error: {error.message}",
                extra=log_data
            )

    def _generate_user_message(self, error: TravelError) -> str:
        """사용자 친화적 메시지 생성"""
        if error.user_message:
            return error.user_message

        template = self._error_templates.get(error.error_type, "알 수 없는 오류가 발생했습니다.")

        # 템플릿에서 details 치환
        if "{details}" in template and error.details:
            details_str = ", ".join([f"{k}: {v}" for k, v in error.details.items()])
            return template.format(details=details_str)

        return template


class ErrorFactory:
    """에러 객체 생성 팩토리"""

    @staticmethod
    def create_system_error(message: str, exception: Exception = None, context: Dict[str, Any] = None) -> TravelError:
        """시스템 에러 생성"""
        return TravelError(
            error_type=ErrorType.SYSTEM_ERROR,
            message=message,
            user_message="시스템에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            original_exception=exception,
            context=context or {}
        )

    @staticmethod
    def create_user_error(message: str, user_message: str = None, details: Dict[str, Any] = None) -> TravelError:
        """사용자 에러 생성"""
        return TravelError(
            error_type=ErrorType.USER_ERROR,
            message=message,
            user_message=user_message or "입력하신 정보를 확인해주세요.",
            details=details or {}
        )

    @staticmethod
    def create_external_error(message: str, exception: Exception = None, service_name: str = None) -> TravelError:
        """외부 서비스 에러 생성"""
        details = {"service": service_name} if service_name else {}
        return TravelError(
            error_type=ErrorType.EXTERNAL_ERROR,
            message=message,
            user_message="외부 서비스와의 연결에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            details=details,
            original_exception=exception
        )

    @staticmethod
    def create_validation_error(message: str, field: str = None, value: Any = None) -> TravelError:
        """검증 에러 생성"""
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)

        return TravelError(
            error_type=ErrorType.VALIDATION_ERROR,
            message=message,
            user_message=f"입력된 데이터에 문제가 있습니다: {message}",
            details=details
        )

    @staticmethod
    def from_exception(exception: Exception, error_type: ErrorType = ErrorType.SYSTEM_ERROR, context: Dict[str, Any] = None) -> TravelError:
        """예외에서 에러 객체 생성"""
        message = str(exception)

        # 특정 예외 타입별 처리
        if isinstance(exception, ValueError):
            error_type = ErrorType.VALIDATION_ERROR
        elif isinstance(exception, ConnectionError):
            error_type = ErrorType.EXTERNAL_ERROR
        elif isinstance(exception, (FileNotFoundError, ImportError)):
            error_type = ErrorType.SYSTEM_ERROR

        if error_type == ErrorType.SYSTEM_ERROR:
            return ErrorFactory.create_system_error(message, exception, context)
        elif error_type == ErrorType.EXTERNAL_ERROR:
            return ErrorFactory.create_external_error(message, exception)
        elif error_type == ErrorType.VALIDATION_ERROR:
            return ErrorFactory.create_validation_error(message)
        else:
            return ErrorFactory.create_user_error(message)


def error_handler_decorator(error_handler: ErrorHandler):
    """에러 처리 데코레이터"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 컨텍스트 추출 (함수 인자에서)
                context = {}
                if args and hasattr(args[0], 'session_id'):
                    context['session_id'] = args[0].session_id
                if args and hasattr(args[0], 'user_id'):
                    context['user_id'] = args[0].user_id

                # 에러 객체 생성 및 처리
                travel_error = ErrorFactory.from_exception(e, context=context)
                return error_handler.handle_error(travel_error, context)

        return wrapper
    return decorator


# 전역 에러 핸들러 인스턴스
_global_error_handler: ErrorHandler = None


def get_error_handler() -> ErrorHandler:
    """전역 에러 핸들러 조회"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def set_error_handler(handler: ErrorHandler):
    """전역 에러 핸들러 설정"""
    global _global_error_handler
    _global_error_handler = handler