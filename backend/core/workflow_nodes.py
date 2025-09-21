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

<strong>🗓️ [지역명] [기간] 여행 일정</strong>

<strong>1일차</strong>
- 09:00 - <strong>[장소명]</strong>  장소 설명
- 12:00 - <strong>[점심 장소]</strong>  음식 설명
- 14:00 - <strong>[오후 활동]</strong>  활동 설명
- 18:00 - <strong>[저녁 장소]</strong>  저녁 설명

<strong>2일차</strong> (기간에 따라)
...

<strong>💡 여행 팁</strong>
- [실용적인 팁 1]
- [실용적인 팁 2]
- [실용적인 팁 3]

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

    travel_plan = state.get("travel_plan", {})
    if not travel_plan:
        return {
            **state,
            "conversation_context": "확정할 여행 일정이 없습니다. 먼저 여행 일정을 요청해주세요."
        }

    try:
        # 여행 일정 확정 처리
        travel_plan["status"] = "confirmed"
        travel_plan["confirmed_at"] = datetime.now().isoformat()

        # 확정 완료 메시지 생성
        response = f"""
✅ <strong>여행 일정이 확정되었습니다!</strong>

📋 <strong>확정된 일정 요약</strong>
- 🗓️ 여행 날짜: {travel_plan.get('travel_dates', '미정')}
- ⏰ 여행 기간: {travel_plan.get('duration', '미정')}
- 📍 총 {len(travel_plan.get('days', []))}일 일정
- 🏛️ 방문 장소: {len(travel_plan.get('places', []))}곳

🎉 즐거운 여행 되세요!

더 궁금한 점이 있으시면 언제든 말씀해주세요.
"""

        # 도구 실행 결과 추가 (리다이렉트용)
        # 지도 페이지로 리다이렉트할 URL 생성
        redirect_url = "/map"

        # URL 파라미터 구성
        url_params = []

        # places 배열에서 region과 city 정보 추출
        region = None
        city = None
        if travel_plan.get("places"):
            # 첫 번째 장소에서 지역 정보 추출
            first_place = travel_plan["places"][0] if travel_plan["places"] else {}
            region = first_place.get("region")
            city = first_place.get("city")

        # 기본 파라미터
        if region:
            url_params.append(f"region={region}")
        if city:
            url_params.append(f"city={city}")
        if travel_plan.get("duration"):
            url_params.append(f"duration={travel_plan['duration']}")

        # 날짜 파라미터 (parsed_dates 형식 사용)
        if travel_plan.get("parsed_dates"):
            parsed_dates = travel_plan["parsed_dates"]
            if parsed_dates.get("startDate"):
                url_params.append(f"startDate={parsed_dates['startDate']}")
            if parsed_dates.get("endDate"):
                url_params.append(f"endDate={parsed_dates['endDate']}")
            if parsed_dates.get("days"):
                url_params.append(f"days={parsed_dates['days']}")
        elif travel_plan.get("travel_dates", "미정") != "미정":
            url_params.append(f"dates={travel_plan['travel_dates']}")

        # 장소 정보
        if travel_plan.get("places"):
            place_names = [place.get("name", "") for place in travel_plan["places"] if place.get("name")]
            if place_names:
                url_params.append(f"places={','.join(place_names[:5])}")  # 최대 5개만

        if url_params:
            redirect_url += "?" + "&".join(url_params)

        print(f"🔗 생성된 redirect_url: {redirect_url}")
        print(f"🔍 URL 파라미터 디버깅 - region: {region}, city: {city}, duration: {travel_plan.get('duration')}")

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
    if tool_results and tool_results.get("redirect_url"):
        redirect_url = tool_results["redirect_url"]
        print(f"🔗 리다이렉트 URL 포함됨: {redirect_url}")

    print(f"✅ 응답 통합 완료")

    response_state = {
        **state,
        "final_response": final_response
    }

    # redirect_url이 있으면 state에 포함
    if redirect_url:
        response_state["redirect_url"] = redirect_url

    return response_state