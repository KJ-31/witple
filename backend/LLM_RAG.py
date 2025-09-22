"""
여행 추천 시스템 메인 진입점 (리팩토링 버전)
"""
from typing import List, Dict, Any
from system_config.settings import initialize_system
from core.database import initialize_retriever
from core.workflow_manager import get_workflow_manager, initialize_workflow_manager
from core.travel_context import get_travel_context
import sys


def initialize_travel_system():
    """여행 추천 시스템 전체 초기화"""
    print("🚀 여행 추천 시스템 초기화 시작...")

    try:
        # 1. 시스템 설정 및 기본 컴포넌트 초기화
        context = initialize_system()
        print("✅ 기본 컴포넌트 초기화 완료")

        # 2. 데이터베이스 및 검색 시스템 초기화
        retriever = initialize_retriever(context.vectorstore)
        print("✅ 검색 시스템 초기화 완료")

        # 3. 워크플로우 관리자 초기화
        workflow_manager = initialize_workflow_manager()
        print("✅ 워크플로우 관리자 초기화 완료")

        print("🎉 여행 추천 시스템 초기화 성공!")
        return True

    except Exception as e:
        print(f"❌ 시스템 초기화 실패: {e}")
        return False


async def get_travel_recommendation_langgraph(
    query: str,
    conversation_history: List[str] = None,
    session_id: str = "default",
    user_id: str = None
) -> Dict[str, Any]:
    """
    여행 추천 메인 API 함수

    Args:
        query: 사용자 질문
        conversation_history: 대화 기록 (선택사항)
        session_id: 세션 ID (선택사항)

    Returns:
        Dict containing:
        - content: 응답 텍스트
        - type: 응답 타입
        - travel_plan: 여행 계획 데이터 (있는 경우)
        - formatted_ui_response: UI용 포맷된 응답 (있는 경우)
    """
    print(f"🔍 여행 추천 요청: '{query}'")

    try:
        # 컨텍스트 확인
        context = get_travel_context()
        if not context.is_ready():
            print("⚠️ 시스템이 초기화되지 않음, 자동 초기화 시도")
            if not initialize_travel_system():
                return {
                    "content": "시스템 초기화 실패. 관리자에게 문의하세요.",
                    "type": "error"
                }

        # 워크플로우 매니저로 쿼리 처리
        workflow_manager = get_workflow_manager()
        result = await workflow_manager.process_query(query, conversation_history, user_id=user_id, session_id=session_id)

        print(f"✅ 여행 추천 완료: {result.get('type', 'unknown')}")
        return result

    except Exception as e:
        print(f"❌ 여행 추천 처리 오류: {e}")
        import traceback
        traceback.print_exc()

        return {
            "content": f"처리 중 오류가 발생했습니다: {str(e)}",
            "type": "error"
        }


# 시스템 자동 초기화 (모듈 로드시)
def auto_initialize():
    """모듈 로드시 자동 초기화"""
    try:
        print("🔄 자동 초기화 시작...")
        success = initialize_travel_system()
        if success:
            print("✅ 자동 초기화 성공")
        else:
            print("⚠️ 자동 초기화 실패 - 수동 초기화 필요")
    except Exception as e:
        print(f"⚠️ 자동 초기화 중 오류: {e}")


# 호환성을 위한 기존 함수명 유지
get_travel_recommendation = get_travel_recommendation_langgraph


# 스크립트로 직접 실행시
if __name__ == "__main__":
    print("🧪 여행 추천 시스템 테스트 모드")

    # 초기화
    if initialize_travel_system():
        print("\n✅ 시스템 준비 완료")

        # 간단한 테스트
        import asyncio

        async def test_query():
            test_queries = [
                "안녕하세요",
                "강릉 맛집 추천해주세요",
                "부산 2박3일 여행 일정 짜주세요"
            ]

            for query in test_queries:
                print(f"\n🧪 테스트 쿼리: '{query}'")
                result = await get_travel_recommendation_langgraph(query)
                print(f"📝 응답 타입: {result.get('type')}")
                print(f"📄 응답 길이: {len(result.get('content', ''))} 문자")
                print("---")

        asyncio.run(test_query())
    else:
        print("❌ 시스템 초기화 실패")
        sys.exit(1)


# 모듈 로드시 자동 초기화 실행
# auto_initialize()  # 필요시 주석 해제