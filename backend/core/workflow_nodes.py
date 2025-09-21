"""
워크플로우 노드 처리 함수들
"""
from typing import TypedDict, List
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

from core.travel_context import get_travel_context
from utils.intent_classifier import classify_query_intent
from utils.entity_extractor import detect_query_entities
from utils.travel_planner import (
    parse_travel_dates, parse_enhanced_travel_plan,
    create_formatted_ui_response, format_travel_response_with_linebreaks
)
from utils.simple_search import information_search_node as simple_information_search_node
from core.database import search_places_by_type
from utils.response_parser import extract_structured_places


class TravelState(TypedDict):
    """여행 상태 타입 정의"""
    messages: List[str]
    need_rag: bool
    need_search: bool
    need_confirmation: bool
    query_type: str
    travel_plan: dict
    user_preferences: dict
    conversation_context: str
    formatted_ui_response: dict
    rag_results: List[Document]
    travel_dates: str
    parsed_dates: dict
    tool_results: dict


def classify_query(state: TravelState) -> TravelState:
    """LLM 기반 쿼리 분류"""
    if not state.get("messages"):
        return state

    context = get_travel_context()
    user_input = state["messages"][-1] if state["messages"] else ""
    has_travel_plan = bool(state.get("travel_plan"))

    print(f"🔍 LLM 기반 쿼리 분류: '{user_input}'")

    try:
        # LLM 기반 의도 분류
        intent_result = classify_query_intent(
            user_input,
            has_travel_plan,
            context.llm,
            context.db_catalogs
        )

        # 새로운 여행 요청 감지 (개선된 로직)
        if (has_travel_plan and
            intent_result["primary_intent"] == "travel_planning" and
            intent_result.get("secondary_intent") == "reset_previous"):
            # 새로운 여행 일정 요청으로 판단되면 상태 초기화
            print("🔄 새로운 여행 일정 요청 감지 - 기존 상태 초기화")
            state["travel_plan"] = {}
            state["user_preferences"] = {}
            state["conversation_context"] = ""
            state["formatted_ui_response"] = {}
            has_travel_plan = False  # 상태 업데이트
        elif has_travel_plan and intent_result["primary_intent"] == "travel_planning":
            # 일반적인 여행 관련 질문이지만 새로운 요청이 아닌 경우도 상태 초기화
            print("🔄 여행 관련 질문 감지 - 기존 상태 초기화 (안전장치)")
            state["travel_plan"] = {}
            state["user_preferences"] = {}
            state["conversation_context"] = ""
            state["formatted_ui_response"] = {}
            has_travel_plan = False  # 상태 업데이트

        # LLM 결과를 기존 변수명으로 매핑
        need_rag = intent_result["requires_rag"]
        need_search = intent_result["requires_search"]
        need_confirmation = (intent_result["primary_intent"] == "confirmation" and
                            intent_result["confirmation_type"] != "none")

        print(f"🧠 LLM 분류 결과:")
        print(f"   - 주요 의도: {intent_result['primary_intent']}")
        print(f"   - 확정 유형: {intent_result['confirmation_type']}")
        print(f"   - RAG 필요: {need_rag}")
        print(f"   - 검색 필요: {need_search}")
        print(f"   - 확정 필요: {need_confirmation}")
        print(f"   - 기존 여행 계획 존재: {has_travel_plan}")

        # 확정 처리 디버깅
        if need_confirmation:
            print(f"🎯 확정 처리 활성화됨!")
        elif intent_result['primary_intent'] == 'confirmation':
            print(f"⚠️ 확정 의도 감지되었지만 need_confirmation이 False입니다.")

    except Exception as e:
        print(f"⚠️ LLM 분류 실패, 폴백 사용: {e}")
        # 폴백: 기본값
        need_rag = True
        need_search = False
        need_confirmation = False

    query_type = "complex" if sum([need_rag, need_search]) > 1 else "simple"

    print(f"   분류 결과 - RAG: {need_rag}, Search: {need_search}, 확정: {need_confirmation}")
    print(f"   여행 일정 존재: {has_travel_plan}")

    return {
        **state,
        "need_rag": need_rag,
        "need_search": need_search,
        "need_confirmation": need_confirmation,
        "query_type": query_type
    }


def rag_processing_node(state: TravelState) -> TravelState:
    """RAG 기반 여행지 추천 처리 노드"""
    if not state.get("messages"):
        return {
            **state,
            "conversation_context": "처리할 메시지가 없습니다."
        }

    context = get_travel_context()
    user_query = state["messages"][-1]
    print(f"🧠 RAG 처리 시작: '{user_query}'")

    try:
        # 엔티티 추출
        entities = detect_query_entities(user_query, context.llm, context.db_catalogs)
        travel_dates = entities.get("travel_dates", "미정")
        duration = entities.get("duration", "미정")
        print(f"📅 추출된 여행 날짜: '{travel_dates}', 기간: '{duration}'")

        # 날짜 파싱
        parsed_dates = parse_travel_dates(travel_dates, duration)
        print(f"🗓️ 파싱된 날짜 정보: {parsed_dates}")

        # 하이브리드 검색으로 실제 장소 데이터 가져오기
        print(f"\n=== RAG 디버깅 2단계: 벡터 검색 ===")
        print(f"🔍 검색 쿼리: '{user_query}'")
        docs = context.retriever._get_relevant_documents(user_query)
        print(f"📄 초기 검색 결과: {len(docs)}개 문서")

        # 지역 필터링 적용
        target_regions = entities.get('regions', []) + entities.get('cities', [])
        if target_regions:
            print(f"\n🎯 지역 필터링 대상: {target_regions}")
            filtered_docs = []

            for doc in docs:
                doc_region = doc.metadata.get('region', '').lower()
                doc_city = doc.metadata.get('city', '').lower()

                # 지역/도시 매칭 확인
                is_relevant = False
                for region in target_regions:
                    region_lower = region.lower()

                    # 지역명 매칭
                    if region_lower in doc_region:
                        is_relevant = True
                        break

                    # 도시명 매칭
                    if region_lower in doc_city:
                        is_relevant = True
                        break

                    # 약어 매칭
                    region_short = region_lower.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '')
                    if region_short and (region_short in doc_region or region_short in doc_city):
                        is_relevant = True
                        break

                if is_relevant:
                    filtered_docs.append(doc)

            if filtered_docs:
                docs = filtered_docs
                print(f"✅ 지역 필터링 완료: {len(docs)}개 문서 선별")
            else:
                print(f"⚠️ 지역 필터링 결과 없음, 전체 결과 사용")

        # 문서 수 제한
        docs = docs[:35]
        print(f"📄 최종 문서 수: {len(docs)}개 (상위 35개로 제한)")

        # 구조화된 장소 데이터 추출
        structured_places = extract_structured_places(docs)
        print(f"🏗️ 구조화된 장소 추출 완료: {len(structured_places)}개")

        # 컨텍스트 생성
        context_parts = []
        available_places = []

        for doc in docs:
            context_parts.append(doc.page_content)

        for doc in docs:
            place_name = doc.page_content.split('\n')[0] if doc.page_content else "알 수 없는 장소"
            if "이름:" in place_name:
                place_name = place_name.split("이름:")[-1].strip()
            available_places.append(place_name)

        # 지역 제약 조건 추가
        region_constraint = ""
        if target_regions:
            region_constraint = f"\n\n⚠️ 중요: 반드시 다음 지역의 장소들만 추천해주세요: {', '.join(target_regions)}\n"

        search_context = "\n\n".join(context_parts)

        # 사용 가능한 장소 목록을 컨텍스트에 명시적으로 추가
        places_list = "\n".join([f"• {place}" for place in available_places])
        enhanced_context = f"""
사용 가능한 장소 목록 (총 {len(available_places)}개):
{places_list}

상세 정보:
{search_context}
"""

        print(f"\n=== RAG 디버깅 4단계: LLM 프롬프트 준비 ===")
        print(f"📝 컨텍스트 길이: {len(enhanced_context)} 문자")
        print(f"🔗 사용 가능한 장소 수: {len(available_places)}개")
        print(f"📍 장소 목록 샘플: {available_places[:3]}")
        print(f"🎯 지역 제약 조건: {region_constraint.strip() if region_constraint else '없음'}")

        # 향상된 프롬프트 생성
        enhanced_prompt = ChatPromptTemplate.from_template("""
당신은 한국 여행 전문가입니다. 사용자의 여행 요청에 대해 구체적이고 실용적인 여행 일정을 작성해주세요.

다음 여행지 정보를 참고하여 답변하세요:
{context}

{region_constraint}

사용자 질문: {question}

다음 형식으로 답변해주세요:

<strong>[지역명] [기간] 여행 일정</strong><br>

<strong>[1일차]</strong>
• 09:00-XX:XX <strong>장소명</strong> - 간단한 설명 (1줄) <br>
• 12:00-13:00 <strong>식당명</strong> - 음식 종류 점심 <br>
• XX:XX-XX:XX <strong>장소명</strong> - 간단한 설명 (1줄) <br>
• 18:00-19:00 <strong>식당명</strong> - 음식 종류 저녁 <br><br>

<strong>[2일차]</strong> (기간에 따라 추가)
...

시간 표시 규칙:
- 시작시간은 명시하되, 종료시간은 활동 특성에 따라 유동적으로 설정
- 각 활동 옆에 예상 소요시간을 괄호로 표시
- 다음 활동 시작 전 충분한 여유시간 확보

💡 <strong>여행 팁</strong>: 지역 특색이나 주의사항

이 일정으로 확정하시겠어요?

주의사항:
1. 반드시 제공된 장소 목록에서만 선택하세요
2. 시간대별로 논리적인 동선을 고려하세요
3. 식사 시간을 포함하여 현실적인 일정을 짜세요
4. 각 장소에 대한 간단한 설명을 포함하세요
5. 사용자 확정 질문을 마지막에 포함하세요
""")

        # LLM으로 구조화된 응답 생성
        prompt_value = enhanced_prompt.invoke({
            "context": enhanced_context,
            "question": user_query,
            "region_constraint": region_constraint
        })
        print(f"\n=== RAG 디버깅 5단계: LLM 응답 생성 ===")
        raw_response = context.llm.invoke(prompt_value).content
        print(f"🤖 LLM 응답 길이: {len(raw_response)} 문자")
        print(f"📝 LLM 응답 샘플 (300자): {raw_response[:300]}...")

        # 가독성을 위한 개행 처리
        formatted_response = format_travel_response_with_linebreaks(raw_response)

        # 상세한 여행 일정 파싱 (실제 장소 데이터 포함)
        print(f"🔧 parse_enhanced_travel_plan 호출 전:")
        print(f"   - travel_dates: '{travel_dates}'")
        print(f"   - parsed_dates: {parsed_dates}")
        travel_plan = parse_enhanced_travel_plan(formatted_response, user_query, structured_places, travel_dates)
        print(f"🔧 parse_enhanced_travel_plan 호출 후:")
        print(f"   - travel_plan에 포함된 parsed_dates: {travel_plan.get('parsed_dates')}")

        # UI용 구조화된 응답 생성
        formatted_ui_response = create_formatted_ui_response(travel_plan, formatted_response)

        print(f"✅ RAG 처리 완료. 결과 길이: {len(formatted_response)}")
        print(f"   추출된 장소 수: {len(structured_places)}")

        # 디버깅: travel_plan 상태 확인
        print(f"🔍 RAG 처리 완료 - travel_plan 상태:")
        print(f"   - travel_plan 타입: {type(travel_plan)}")
        print(f"   - travel_plan 길이: {len(travel_plan) if isinstance(travel_plan, dict) else 'N/A'}")
        if isinstance(travel_plan, dict):
            print(f"   - travel_plan keys: {list(travel_plan.keys())}")
            print(f"   - days 존재: {'days' in travel_plan}")
            print(f"   - days 길이: {len(travel_plan.get('days', []))}")
            print(f"   - places 존재: {'places' in travel_plan}")
            print(f"   - places 길이: {len(travel_plan.get('places', []))}")

        # 최종 state 반환
        final_state = {
            **state,
            "rag_results": docs,
            "travel_plan": travel_plan,
            "travel_dates": travel_dates,
            "parsed_dates": parsed_dates,
            "conversation_context": formatted_response,
            "formatted_ui_response": formatted_ui_response
        }

        print(f"✅ RAG 처리 최종 state 생성 - travel_plan이 포함됨: {'travel_plan' in final_state}")
        return final_state

    except Exception as e:
        print(f"❌ RAG 처리 오류: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "rag_results": [],
            "conversation_context": f"여행 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"
        }


def information_search_node(state: TravelState) -> TravelState:
    """단순 정보 검색 처리 노드 (리스트 형태 응답) - 래퍼 함수"""
    context = get_travel_context()

    def detect_query_entities_wrapper(query: str) -> dict:
        return detect_query_entities(query, context.llm, context.db_catalogs)

    return simple_information_search_node(state, context.retriever, detect_query_entities_wrapper)


def search_processing_node(state: TravelState) -> TravelState:
    """장소 검색 처리 노드"""
    if not state.get("messages"):
        return {
            **state,
            "conversation_context": "검색할 메시지가 없습니다."
        }

    user_query = state["messages"][-1]
    print(f"📍 장소 검색 처리: '{user_query}'")

    try:
        context = get_travel_context()

        # 지역/도시 정보 추출
        entities = detect_query_entities(user_query, context.llm, context.db_catalogs)
        regions = entities.get('regions', [])
        cities = entities.get('cities', [])

        print(f"📍 추출된 정보 - 지역: {regions}, 도시: {cities}")

        # 여행지와 음식점 분리 검색 사용
        docs = search_places_by_type(user_query, regions, cities)

        # 검색 결과를 간단하게 포맷팅
        if docs:
            places = []
            for doc in docs[:20]:  # 상위 20개만
                place_name = doc.page_content.split('\n')[0] if doc.page_content else "알 수 없는 장소"
                if "이름:" in place_name:
                    place_name = place_name.split("이름:")[-1].strip()
                region = doc.metadata.get('region', '')
                city = doc.metadata.get('city', '')
                places.append(f"• {place_name} ({city or region})")

            response = f"<strong>'{user_query}' 검색 결과</strong>\n\n" + "\n".join(places)
        else:
            response = f"'{user_query}'에 대한 검색 결과를 찾을 수 없습니다."

        print(f"✅ 장소 검색 완료. 결과: {len(docs)}개 장소")

        return {
            **state,
            "rag_results": docs,
            "conversation_context": response
        }

    except Exception as e:
        print(f"❌ 장소 검색 오류: {e}")
        return {
            **state,
            "conversation_context": f"장소 검색 중 오류가 발생했습니다: {str(e)}"
        }


def general_chat_node(state: TravelState) -> TravelState:
    """일반 채팅 처리 노드"""
    if not state.get("messages"):
        return {
            **state,
            "conversation_context": "안녕하세요! 여행 계획을 도와드릴게요."
        }

    user_query = state["messages"][-1]
    print(f"💬 일반 채팅 처리: '{user_query}'")

    try:
        context = get_travel_context()

        # 간단한 일반 대화 프롬프트
        general_prompt = ChatPromptTemplate.from_template("""
당신은 친근한 한국 여행 도우미입니다. 사용자의 질문에 간단하고 도움이 되는 답변을 해주세요.

사용자 질문: {question}

답변 가이드:
- 여행과 관련된 질문이면 구체적인 도움을 제안하세요
- 여행과 관련 없는 질문이면 친근하게 여행 계획을 도와드릴 수 있다고 안내하세요
- 간단하고 친근한 톤으로 답변하세요
""")

        prompt_value = general_prompt.invoke({"question": user_query})
        response = context.llm.invoke(prompt_value).content

        print(f"✅ 일반 채팅 완료")

        return {
            **state,
            "conversation_context": response
        }

    except Exception as e:
        print(f"❌ 일반 채팅 처리 오류: {e}")
        return {
            **state,
            "conversation_context": "죄송합니다. 일시적인 오류가 발생했습니다."
        }


def confirmation_processing_node(state: TravelState) -> TravelState:
    """확정 처리 노드"""
    print(f"🎯 여행 일정 확정 처리 시작")

    # 디버깅: state 내용 확인
    print(f"🔍 확정 처리 state 디버깅:")
    print(f"   - state keys: {list(state.keys())}")
    print(f"   - travel_plan 존재: {'travel_plan' in state}")

    if 'travel_plan' in state:
        travel_plan = state['travel_plan']
        print(f"   - travel_plan 타입: {type(travel_plan)}")
        print(f"   - travel_plan 길이: {len(travel_plan) if isinstance(travel_plan, dict) else 'N/A'}")
        print(f"   - travel_plan keys: {list(travel_plan.keys()) if isinstance(travel_plan, dict) else 'N/A'}")
    else:
        print(f"   - travel_plan이 state에 없음!")

    travel_plan = state.get("travel_plan", {})
    if not travel_plan:
        print(f"❌ travel_plan이 비어있습니다!")
        return {
            **state,
            "conversation_context": "확정할 여행 일정이 없습니다. 먼저 여행 일정을 요청해주세요."
        }

    try:
        # 여행 일정 확정 처리
        travel_plan["status"] = "confirmed"
        travel_plan["confirmed_at"] = datetime.now().isoformat()

        # 확정 완료 메시지 생성 (일수 정보 수정)
        parsed_dates = travel_plan.get("parsed_dates", {})
        actual_days = parsed_dates.get("days", travel_plan.get('duration', '미정'))
        total_itinerary_days = len(travel_plan.get('days', travel_plan.get('itinerary', [])))

        response = f"""
✅ <strong>여행 일정이 확정되었습니다!</strong>

📋 <strong>확정된 일정 요약</strong>
- 🗓️ 여행 날짜: {travel_plan.get('travel_dates', '미정')}
- ⏰ 여행 기간: {actual_days}
- 📍 총 {total_itinerary_days}일 일정
- 🏛️ 방문 장소: {len(travel_plan.get('places', []))}곳

🎉 즐거운 여행 되세요!<br>
잠시후 지도 페이지로 이동합니다.<br>
더 궁금한 점이 있으시면 언제든 말씀해주세요.
"""

        # 도구 실행 결과 추가 (리다이렉트용)
        # 지도 페이지로 리다이렉트할 URL 생성 (실제 지도 페이지 형식에 맞춰)
        import urllib.parse
        from datetime import timedelta
        import re

        # 지도 표시를 위한 장소 파라미터 구성
        places_list = []
        day_numbers_list = []
        source_tables_list = []

        # 백업 파일의 정확한 일차 배분 로직 적용
        if travel_plan.get("places"):
            print(f"🗓️ 장소 기반 일차 배분 시작: {len(travel_plan['places'])}개 장소")

            # 일정 정보 (days 우선, 그 다음 itinerary)
            itinerary = travel_plan.get("days", travel_plan.get("itinerary", []))
            total_days = len(itinerary) if itinerary else 1

            print(f"🔍 일정 구조 확인:")
            print(f"   - travel_plan.get('days'): {travel_plan.get('days')}")
            print(f"   - travel_plan.get('itinerary'): {travel_plan.get('itinerary')}")
            print(f"   - 사용할 itinerary: {itinerary}")
            print(f"   - total_days: {total_days}")

            # 추가: itinerary가 비어있다면 더 자세히 확인
            if not itinerary:
                print(f"❌ itinerary가 비어있습니다!")
                print(f"   - travel_plan 전체 키: {list(travel_plan.keys())}")
                for key, value in travel_plan.items():
                    if key in ['days', 'itinerary', 'schedule']:
                        print(f"   - {key}: {value}")

                # 혹시 다른 이름으로 저장되어 있는지 확인
                possible_keys = ['schedule', 'daily_schedule', 'day_schedule', 'plan']
                for key in possible_keys:
                    if travel_plan.get(key):
                        print(f"   - 발견된 대안 키 '{key}': {travel_plan[key]}")
                        itinerary = travel_plan[key]
                        total_days = len(itinerary) if itinerary else 1
                        break

            if total_days == 0:
                total_days = 1

            # 정규화 함수 (백업 파일에서 가져옴)
            def normalize_place_name(place_name: str) -> str:
                if not place_name:
                    return ""
                import re
                cleaned = re.sub(r'[^\w\s가-힣]', '', place_name)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                suffixes = ['카페', '레스토랑', '식당', '박물관', '미술관', '공원', '해변', '시장']
                for suffix in suffixes:
                    if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
                        base_name = cleaned[:-len(suffix)].strip()
                        if base_name:
                            return base_name
                return cleaned

            # 일정에서 장소가 속한 일차 찾기 (백업 파일에서 가져옴)
            def find_place_in_itinerary(place_name: str, itinerary: list) -> int:
                normalized_place = normalize_place_name(place_name)
                print(f"   🔍 '{place_name}' 매칭 시도 (정규화: '{normalized_place}')")

                for day_info in itinerary:
                    day_num = day_info.get("day", 1)
                    print(f"      📅 {day_num}일차 스케줄 확인: {day_info.get('schedule', [])}")

                    for schedule in day_info.get("schedule", []):
                        # 여러 필드에서 장소명 찾기
                        possible_place_names = [
                            schedule.get("place_name", ""),
                            schedule.get("place", ""),  # 다른 가능한 필드명
                            schedule.get("name", ""),   # 또 다른 가능한 필드명
                        ]

                        # place_info 내부도 확인
                        if schedule.get("place_info"):
                            place_info = schedule["place_info"]
                            possible_place_names.extend([
                                place_info.get("name", ""),
                                place_info.get("place_name", ""),
                            ])

                        for schedule_place_raw in possible_place_names:
                            if not schedule_place_raw:
                                continue

                            schedule_place = normalize_place_name(schedule_place_raw)
                            print(f"         🏛️ 비교: '{schedule_place_raw}' (정규화: '{schedule_place}')")

                            # 정확한 매칭
                            if normalized_place == schedule_place:
                                print(f"         ✅ 정확 매칭! -> {day_num}일차")
                                return day_num

                            # 포함 관계 매칭
                            if len(normalized_place) >= 2 and len(schedule_place) >= 2:
                                if (normalized_place in schedule_place and len(normalized_place) >= len(schedule_place) * 0.5) or \
                                   (schedule_place in normalized_place and len(schedule_place) >= len(normalized_place) * 0.5):
                                    print(f"         ✅ 포함 매칭! -> {day_num}일차")
                                    return day_num

                print(f"   ❌ 매칭 실패: '{place_name}'")
                return 0

            # 일차별 장소 목록 추출
            def extract_places_by_day(itinerary: list) -> dict:
                places_by_day = {}
                for day_info in itinerary:
                    day_num = day_info.get("day", 1)
                    places_by_day[day_num] = []
                    for schedule in day_info.get("schedule", []):
                        # 여러 필드에서 장소명 찾기
                        possible_place_names = [
                            schedule.get("place_name", ""),
                            schedule.get("place", ""),
                            schedule.get("name", ""),
                        ]

                        # place_info 내부도 확인
                        if schedule.get("place_info"):
                            place_info = schedule["place_info"]
                            possible_place_names.extend([
                                place_info.get("name", ""),
                                place_info.get("place_name", ""),
                            ])

                        for place_name_raw in possible_place_names:
                            if place_name_raw:
                                place_name = normalize_place_name(place_name_raw)
                                if place_name and place_name not in places_by_day[day_num]:
                                    places_by_day[day_num].append(place_name)
                                    break  # 첫 번째 유효한 장소명만 사용

                return places_by_day

            places_by_day = extract_places_by_day(itinerary)
            print(f"🗓️ 일차별 장소 분석: {places_by_day}")

            # 장소를 일차별로 정확하게 배치
            for idx, place in enumerate(travel_plan["places"]):
                place_id = place.get("place_id")
                table_name = place.get("table_name", "general_attraction")

                # place_id가 없거나 "1"이면 스킵
                if not place_id or place_id == "1":
                    print(f"⚠️ place_id 없음 - 장소 '{place.get('name', 'Unknown')}' 스킵")
                    continue

                place_identifier = f"{table_name}_{place_id}"
                places_list.append(place_identifier)
                source_tables_list.append(table_name)

                # 개선된 일차 매칭
                place_name = place.get("name", "")
                day_num = find_place_in_itinerary(place_name, itinerary)

                # 매칭되지 않은 경우 처리
                if day_num == 0:
                    print(f"⚠️ '{place_name}' 매칭 실패, 대안 방법 시도")
                    category = place.get("category", "")

                    # 식사 장소는 기존 식사 시간대가 있는 일차에 배치
                    if "식당" in category or "맛집" in category or "음식" in category:
                        for day_info in itinerary:
                            for schedule in day_info.get("schedule", []):
                                if any(keyword in schedule.get("description", "") for keyword in ["점심", "저녁", "식사"]):
                                    day_num = day_info.get("day", 1)
                                    break
                            if day_num > 0:
                                break

                    # 여전히 매칭되지 않으면 최소 장소가 있는 일차에 배치
                    if day_num == 0:
                        if places_by_day:
                            min_places_day = min(places_by_day.keys(), key=lambda x: len(places_by_day[x]))
                            day_num = min_places_day
                        else:
                            # 매칭 실패 - 이 경우는 파싱이 제대로 안 된 것
                            print(f"   ❌ 파싱된 일정이 없어서 매칭 불가!")
                            day_num = 1

                    print(f"📍 '{place_name}' -> {day_num}일차 배치")

                day_numbers_list.append(str(day_num))
                print(f"✅ 장소 처리: {place_name} -> {place_identifier} (day {day_num})")


        else:
            print(f"❌ 처리할 장소 정보가 없습니다:")
            print(f"   - travel_plan.get('places'): {travel_plan.get('places')}")
            print(f"   - travel_plan keys: {list(travel_plan.keys()) if travel_plan else 'None'}")

        if places_list:
            print(f"🗺️ 지도 표시용 장소 구성 완료:")
            print(f"   장소 목록: {places_list[:5]}{'...' if len(places_list) > 5 else ''}")
            print(f"   일차 배정: {day_numbers_list[:5]}{'...' if len(day_numbers_list) > 5 else ''}")
            print(f"   테이블 목록: {source_tables_list[:5]}{'...' if len(source_tables_list) > 5 else ''}")

        # 날짜 계산
        start_date = ""
        end_date = ""
        days = 2  # 기본값

        if travel_plan.get("parsed_dates") and travel_plan["parsed_dates"].get("startDate"):
            parsed_dates = travel_plan["parsed_dates"]
            start_date = parsed_dates.get("startDate", "")
            end_date = parsed_dates.get("endDate", "")

            # days 필드 안전 처리 (빈 문자열이나 None인 경우 기본값 사용)
            days_value = parsed_dates.get("days", 2)
            if isinstance(days_value, str) and days_value.strip() == "":
                days = 2  # 기본값
            else:
                try:
                    days = int(days_value)
                except (ValueError, TypeError):
                    days = 2  # 변환 실패시 기본값

            print(f"✅ parsed_dates 사용: {start_date} ~ {end_date} ({days}일)")
        else:
            # 기본 방식: 오늘 기준으로 생성
            duration_str = travel_plan.get("duration", "2박3일")
            days_match = re.search(r'(\d+)일', duration_str)
            days = int(days_match.group(1)) if days_match else 2

            start_date = datetime.now().strftime('%Y-%m-%d')
            # 수정: days-1이 아니라 days로 정확한 종료일 계산
            end_date = (datetime.now() + timedelta(days=days-1)).strftime('%Y-%m-%d')
            print(f"⚠️ 기본 날짜 사용 (오늘 기준): {start_date} ~ {end_date} ({days}일)")
            print(f"🔍 날짜 계산 확인: {days}일간 = {start_date} ~ {end_date}")

        # URL 파라미터 생성
        if places_list:
            places_param = ','.join(places_list)
            day_numbers_param = ','.join(day_numbers_list)
            source_tables_param = ','.join(source_tables_list)
            redirect_url = f"/map?places={urllib.parse.quote(places_param)}&dayNumbers={urllib.parse.quote(day_numbers_param)}&sourceTables={urllib.parse.quote(source_tables_param)}&startDate={start_date}&endDate={end_date}&days={days}&baseAttraction=general"
        else:
            # 장소가 없으면 기본 지도 페이지로
            redirect_url = f"/map?startDate={start_date}&endDate={end_date}&days={days}&baseAttraction=general"

        print(f"🔗 생성된 redirect_url: {redirect_url[:100]}{'...' if len(redirect_url) > 100 else ''}")
        print(f"🔍 URL 파라미터 디버깅 - places: {len(places_list)}개, days: {days}")

        tool_results = {
            "action": "redirect_to_planning_page",
            "redirect_url": redirect_url,
            "travel_plan": travel_plan,
            "message": "여행 일정이 확정되었습니다."
        }

        print(f"✅ 여행 일정 확정 완료")

        return {
            **state,
            "travel_plan": travel_plan,
            "conversation_context": response,
            "tool_results": tool_results
        }

    except Exception as e:
        print(f"❌ 확정 처리 오류: {e}")
        return {
            **state,
            "conversation_context": f"여행 일정 확정 중 오류가 발생했습니다: {str(e)}"
        }


def integrate_response_node(state: TravelState) -> TravelState:
    """응답 통합 노드"""
    print(f"🔗 응답 통합 처리")

    # 기본적으로 conversation_context를 최종 응답으로 사용
    final_response = state.get("conversation_context", "응답을 생성할 수 없습니다.")

    # 여행 계획이 있으면 UI 응답도 포함
    formatted_ui_response = state.get("formatted_ui_response")
    if formatted_ui_response:
        print(f"📱 UI 응답 포함됨: {formatted_ui_response.get('type', 'unknown')}")

    # tool_results가 있으면 redirect_url 정보 추가
    tool_results = state.get("tool_results")
    redirect_url = None
    print(f"🔍 integrate_response - tool_results: {tool_results}")
    if tool_results and tool_results.get("redirect_url"):
        redirect_url = tool_results["redirect_url"]
        print(f"🔗 리다이렉트 URL 포함됨: {redirect_url}")
    else:
        print(f"⚠️ tool_results 없음 또는 redirect_url 없음")

    print(f"✅ 응답 통합 완료")

    response_state = {
        **state,
        "final_response": final_response
    }

    # redirect_url이 있으면 state에 포함
    if redirect_url:
        response_state["redirect_url"] = redirect_url

    # tool_results를 최종 state에 포함 (chat router에서 사용)
    if tool_results:
        response_state["tool_results"] = tool_results

    return response_state