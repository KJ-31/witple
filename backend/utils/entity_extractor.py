from langchain_core.prompts import ChatPromptTemplate


def detect_query_entities(query: str, llm, _db_catalogs: dict) -> dict:
    """LLM을 사용하여 쿼리에서 구조화된 엔티티 및 여행 인텐트 추출"""
    try:
        # 디버깅: llm 타입 확인
        print(f"🔍 detect_query_entities 호출 - llm 타입: {type(llm)}")
        if isinstance(llm, str) or llm is None:
            print(f"❌ ERROR: LLM이 올바르지 않음: {llm}")
            raise ValueError(f"Invalid LLM object: {type(llm)}")
        entity_extraction_prompt = ChatPromptTemplate.from_template("""
당신은 한국 여행 쿼리를 분석하는 전문가입니다.
주어진 쿼리에서 지역명, 도시명, 카테고리, 키워드와 여행 인텐트를 추출해주세요.

쿼리: "{query}"

다음 JSON 형태로 정확히 응답해주세요:
{{
    "regions": ["지역명들"],
    "cities": ["도시명들"],
    "categories": ["카테고리들"],
    "keywords": ["기타 키워드들"],
    "intent": "여행 인텐트",
    "travel_type": "여행 유형",
    "duration": "여행 기간",
    "travel_dates": "여행 날짜"
}}

추출 규칙:
1. 지역명: 경기도, 서울특별시, 부산광역시 등의 광역 행정구역
2. 도시명: 강릉, 제주, 부산, 서울 등의 구체적 도시/지역
3. 카테고리: 맛집, 관광지, 자연, 쇼핑, 레포츠, 카페, 한식, 일식, 중식, 양식 등
4. 키워드: 2박3일, 가족여행, 데이트, 혼자, 친구 등의 부가 정보
5. intent: "travel_planning"(여행 일정), "place_search"(장소 검색), "weather"(날씨), "general"(일반)
6. travel_type: "family"(가족), "couple"(커플), "friends"(친구), "solo"(혼자), "business"(출장), "general"(일반)
7. duration: "당일", "1박2일", "2박3일", "3박4일", "장기", "미정" 등
8. travel_dates: 구체적인 날짜를 YYYY-MM-DD 형식으로 변환, 상대적 날짜, 또는 "미정"

**날짜 변환 규칙**:
- "10월 4일" → "2025-10-04" (현재 연도 기준)
- "4일부터" → "2025-09-04" (현재 월 기준)
- "내일" → 내일 날짜로 계산
- "이번 주말" → "이번 주말" (그대로 유지)
- "다음 달" → "다음 달" (그대로 유지)
- "2025-10-04" → "2025-10-04" (이미 형식화된 경우 그대로)

예시:
- "부산 2박3일 10월 4일부터" → {{"regions": ["부산광역시"], "cities": ["부산"], "categories": [], "keywords": ["2박3일"], "intent": "travel_planning", "travel_type": "general", "duration": "2박3일", "travel_dates": "2025-10-04"}}
- "제주도 이번 주말" → {{"regions": ["제주특별자치도"], "cities": ["제주"], "categories": [], "keywords": [], "intent": "travel_planning", "travel_type": "general", "duration": "미정", "travel_dates": "이번 주말"}}
- "강릉 3일간 여행" → {{"regions": ["강원도"], "cities": ["강릉"], "categories": [], "keywords": ["3일간"], "intent": "travel_planning", "travel_type": "general", "duration": "3일", "travel_dates": "미정"}}
- "서울 12월 25일부터 27일까지" → {{"regions": ["서울특별시"], "cities": ["서울"], "categories": [], "keywords": [], "intent": "travel_planning", "travel_type": "general", "duration": "미정", "travel_dates": "2025-12-25부터 2025-12-27까지"}}
""")

        entity_chain = entity_extraction_prompt | llm

        response = entity_chain.invoke({"query": query})

        # JSON 파싱 시도
        import json
        import re

        # 응답에서 JSON 부분만 추출
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if json_match:
            entities = json.loads(json_match.group())

            # 기본 구조 보장 (새로운 필드 추가)
            result = {
                "regions": entities.get("regions", []),
                "cities": entities.get("cities", []),
                "categories": entities.get("categories", []),
                "keywords": entities.get("keywords", []),
                "intent": entities.get("intent", "general"),
                "travel_type": entities.get("travel_type", "general"),
                "duration": entities.get("duration", "미정"),
                "travel_dates": entities.get("travel_dates", "미정")
            }

            print(f"🧠 LLM 엔티티 추출 성공: {result}")
            print(f"🧠 추출된 travel_dates: '{result.get('travel_dates', 'N/A')}'")
            return result
        else:
            print(f"⚠️ LLM 응답에서 JSON 파싱 실패: {response.content}")
            return {"regions": [], "cities": [], "categories": [], "keywords": [], "intent": "general", "travel_type": "general", "duration": "미정", "travel_dates": "미정"}

    except Exception as e:
        print(f"❌ LLM 엔티티 추출 오류: {e}")
        # 폴백: 기존 하드코딩 방식 사용
        return _fallback_entity_extraction(query, _db_catalogs)


def _fallback_entity_extraction(query: str, _db_catalogs: dict) -> dict:
    """폴백: DB 카탈로그 기반 단순 문자열 매칭 (LLM 실패시)"""
    found_regions = []
    found_cities = []
    found_categories = []

    # DB 카탈로그가 로드되지 않은 경우 빈 결과 반환
    if not _db_catalogs.get("regions"):
        print("⚠️ DB 카탈로그가 로드되지 않음, 빈 결과 반환")
        return {"regions": [], "cities": [], "categories": [], "keywords": []}

    # DB 카탈로그 기반 단순 문자열 매칭
    for region in _db_catalogs.get("regions", []):
        if region in query or region.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '') in query:
            found_regions.append(region)

    for city in _db_catalogs.get("cities", []):
        if city in query:
            found_cities.append(city)

    for category in _db_catalogs.get("categories", []):
        if category in query:
            found_categories.append(category)

    return {
        "regions": found_regions,
        "cities": found_cities,
        "categories": found_categories,
        "keywords": [],
        "intent": "general",
        "travel_type": "general",
        "duration": "미정",
        "travel_dates": "미정"
    }