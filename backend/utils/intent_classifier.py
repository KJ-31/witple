"""
의도 분류 관련 유틸리티 함수들
"""
from utils.entity_extractor import detect_query_entities


def classify_query_intent(query: str, has_travel_plan: bool = False, llm=None, _db_catalogs: dict = None) -> dict:
    """엔티티 추출 기반 쿼리 의도 분류"""
    print(f"🔧 엔티티 추출 기반 의도 분류 사용")

    try:
        # 엔티티 추출로 의도 분류
        entities = detect_query_entities(query, llm, _db_catalogs)
        intent = entities.get("intent", "general")

        print(f"🧠 엔티티 추출된 의도: {intent}")

        # 확정 관련 처리 (has_travel_plan 체크 제거하여 항상 확정 키워드 체크)
        confirmation_keywords = [
            "확정", "결정", "좋아", "이걸로", "ok", "오케이", "맞아", "네", "응", "그래",
            "좋다", "좋네", "좋아요", "좋습니다", "괜찮아", "괜찮다", "괜찮네", "괜찮습니다",
            "이거", "이것", "이걸", "이거로", "이것으로", "이걸로", "확인", "yes"
        ]
        query_lower = query.lower().strip()

        if any(word in query_lower for word in confirmation_keywords):
            print(f"🎯 확정 키워드 감지: '{query}' (has_travel_plan: {has_travel_plan})")
            return {
                "primary_intent": "confirmation",
                "secondary_intent": "none",
                "confidence_level": "high",
                "confirmation_type": "strong",
                "requires_rag": False,
                "requires_search": False
            }

        # 엔티티 추출 기반 의도 매핑
        if intent == "place_search":
            return {
                "primary_intent": "information_search",
                "secondary_intent": "none",
                "confidence_level": "high",
                "confirmation_type": "none",
                "requires_rag": True,
                "requires_search": False
            }
        elif intent == "travel_planning":
            # 기존 여행 계획이 있고 새로운 여행 요청인 경우
            if has_travel_plan:
                return {
                    "primary_intent": "travel_planning",
                    "secondary_intent": "reset_previous",
                    "confidence_level": "high",
                    "confirmation_type": "none",
                    "requires_rag": True,
                    "requires_search": False
                }
            else:
                return {
                    "primary_intent": "travel_planning",
                    "secondary_intent": "none",
                    "confidence_level": "high",
                    "confirmation_type": "none",
                    "requires_rag": True,
                    "requires_search": False
                }
        elif intent == "weather":
            return {
                "primary_intent": "weather",
                "secondary_intent": "none",
                "confidence_level": "high",
                "confirmation_type": "none",
                "requires_rag": False,
                "requires_search": True
            }
        else:  # general
            return {
                "primary_intent": "general_chat",
                "secondary_intent": "none",
                "confidence_level": "medium",
                "confirmation_type": "none",
                "requires_rag": False,
                "requires_search": False
            }

    except Exception as e:
        print(f"⚠️ 엔티티 기반 분류 실패, 폴백 사용: {e}")
        return _fallback_intent_classification(query, has_travel_plan)


def _fallback_intent_classification(query: str, has_travel_plan: bool = False) -> dict:
    """폴백: 개선된 키워드 기반 의도 분류"""
    query_lower = query.lower()

    # 확정 관련 키워드 (더 포괄적으로)
    confirmation_keywords = [
        "확정", "결정", "좋아", "이걸로", "ok", "오케이", "맞아", "네", "응", "그래",
        "좋다", "좋네", "좋아요", "좋습니다", "괜찮아", "괜찮다", "괜찮네", "괜찮습니다",
        "이거", "이것", "이걸", "이거로", "이것으로", "이걸로", "이거로 해", "이것으로 해",
        "그래", "그래요", "그래요", "그렇다", "그렇네", "그렇습니다",
        "맞다", "맞네", "맞습니다", "맞아요", "맞아", "맞습니다",
        "네", "네요", "네", "예", "예요", "예", "예스", "yes", "y",
        "확인", "확인해", "확인해요", "확인합니다", "확인됐어", "확인됐습니다"
    ]
    strong_confirmation = ["확정", "결정", "이걸로", "ok", "오케이", "확인", "yes"]

    if has_travel_plan and any(word in query_lower for word in confirmation_keywords):
        confirmation_type = "strong" if any(word in query_lower for word in strong_confirmation) else "weak"
        matched_keywords = [word for word in confirmation_keywords if word in query_lower]
        print(f"🎯 확정 키워드 감지: {matched_keywords} (타입: {confirmation_type})")
        return {
            "primary_intent": "confirmation",
            "secondary_intent": "none",
            "confidence_level": "high" if confirmation_type == "strong" else "medium",
            "confirmation_type": confirmation_type,
            "requires_rag": False,
            "requires_search": False
        }

    # 새로운 여행 요청 감지 (개선된 로직)
    travel_keywords = ["추천", "여행", "일정", "계획", "가고싶어", "놀러", "구경", "관광"]
    duration_keywords = ["박", "일", "당일", "하루", "이틀", "사흘"]
    region_keywords = ["서울", "부산", "제주", "강릉", "경주", "전주", "대구", "광주", "인천", "춘천", "여수"]
    question_patterns = ["어디", "뭐", "뭘", "어떤", "추천해", "알려줘", "가볼만한"]

    has_travel_keywords = any(keyword in query_lower for keyword in travel_keywords)
    has_duration_keywords = any(keyword in query_lower for keyword in duration_keywords)
    has_region_keywords = any(keyword in query_lower for keyword in region_keywords)
    has_question_patterns = any(pattern in query_lower for pattern in question_patterns)

    is_new_travel_request = has_travel_keywords or has_duration_keywords or has_region_keywords or has_question_patterns

    # 기존 여행 계획이 있고 새로운 여행 요청인 경우
    if has_travel_plan and is_new_travel_request:
        print("🔄 기존 계획 있지만 새로운 여행 요청 감지 - travel_planning으로 분류")
        return {
            "primary_intent": "travel_planning",
            "secondary_intent": "reset_previous",
            "confidence_level": "high",
            "confirmation_type": "none",
            "requires_rag": True,
            "requires_search": False
        }

    # 기본 여행 계획
    return {
        "primary_intent": "travel_planning",
        "secondary_intent": "none",
        "confidence_level": "medium",
        "confirmation_type": "none",
        "requires_rag": True,
        "requires_search": False
    }