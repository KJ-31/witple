"""
여행 추천 시스템의 공통 컨텍스트 및 파라미터 관리
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from langchain_core.retrievers import BaseRetriever


@dataclass
class TravelContext:
    """여행 추천 시스템의 공통 컨텍스트"""

    # 핵심 모델들
    llm: Any = None
    retriever: BaseRetriever = None

    # 데이터베이스 관련
    db_catalogs: Dict[str, List[str]] = None
    vectorstore: Any = None

    # 설정
    aws_region: str = None
    model_name: str = None

    # 캐시 및 상태
    current_travel_state: Dict[str, Any] = None

    def __post_init__(self):
        """초기화 후 기본값 설정"""
        if self.db_catalogs is None:
            self.db_catalogs = {"regions": [], "cities": [], "categories": []}
        if self.current_travel_state is None:
            self.current_travel_state = {}

    def is_ready(self) -> bool:
        """컨텍스트가 사용 준비되었는지 확인"""
        return (self.llm is not None and
                self.retriever is not None and
                self.db_catalogs is not None)

    def get_entity_extraction_params(self) -> Dict[str, Any]:
        """엔티티 추출용 파라미터 반환"""
        return {
            "llm": self.llm,
            "_db_catalogs": self.db_catalogs
        }

    def get_search_params(self) -> Dict[str, Any]:
        """검색용 파라미터 반환"""
        return {
            "retriever": self.retriever,
            "db_catalogs": self.db_catalogs
        }

    def get_workflow_params(self) -> Dict[str, Any]:
        """워크플로우용 파라미터 반환"""
        return {
            "llm": self.llm,
            "retriever": self.retriever,
            "db_catalogs": self.db_catalogs
        }

    def update_travel_state(self, state: Dict[str, Any]):
        """여행 상태 업데이트"""
        self.current_travel_state.update(state)

    def reset_travel_state(self):
        """여행 상태 초기화"""
        self.current_travel_state = {}


# 전역 컨텍스트 인스턴스 (싱글톤 패턴)
_global_context: Optional[TravelContext] = None


def get_travel_context() -> TravelContext:
    """전역 여행 컨텍스트 반환"""
    global _global_context
    if _global_context is None:
        print("⚠️ 컨텍스트가 초기화되지 않음, 빈 컨텍스트 생성")
        _global_context = TravelContext()

    # 디버깅: 컨텍스트 상태 확인
    print(f"🔍 컨텍스트 상태 - llm: {type(_global_context.llm)}, retriever: {type(_global_context.retriever)}")
    return _global_context


def initialize_travel_context(llm=None, retriever=None, db_catalogs=None, **kwargs) -> TravelContext:
    """여행 컨텍스트 초기화"""
    global _global_context
    _global_context = TravelContext(
        llm=llm,
        retriever=retriever,
        db_catalogs=db_catalogs,
        **kwargs
    )
    return _global_context


def reset_travel_context():
    """전역 컨텍스트 리셋"""
    global _global_context
    _global_context = None