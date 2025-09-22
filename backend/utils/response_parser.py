"""
응답 파싱 및 장소 데이터 처리 관련 기능들
"""
import re
import json
from typing import List, Dict, Any
from langchain_core.documents import Document
from sqlalchemy import text
from database import engine as shared_engine


def extract_structured_places(docs: List[Document]) -> List[dict]:
    """문서에서 구조화된 장소 데이터 추출"""
    structured_places = []

    for doc in docs:
        try:
            content = doc.page_content
            metadata = doc.metadata

            # 기본 정보 추출
            place_info = {
                "name": "",
                "category": metadata.get("category", ""),
                "region": metadata.get("region", ""),
                "city": metadata.get("city", ""),
                "description": "",
                "address": "",
                "phone": "",
                "hours": "",
                "website": "",
                "rating": "",
                "price_range": "",
                "tags": [],
                "coordinates": metadata.get("coordinates", ""),
                "similarity_score": metadata.get("similarity_score", 0),
                "search_method": metadata.get("search_method", ""),
                "place_id": metadata.get("place_id", ""),
                "table_name": metadata.get("table_name", "")
            }

            # 장소명 추출 (첫 번째 줄 또는 "이름:" 필드)
            lines = content.split('\n')
            if lines:
                first_line = lines[0].strip()
                if "이름:" in first_line:
                    place_info["name"] = first_line.split("이름:")[-1].strip()
                else:
                    place_info["name"] = first_line

            # 각 줄에서 정보 추출
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue

                # 다양한 정보 패턴 매칭
                if line.startswith("주소:") or "주소:" in line:
                    place_info["address"] = line.split("주소:")[-1].strip()
                elif line.startswith("전화:") or "전화:" in line:
                    place_info["phone"] = line.split("전화:")[-1].strip()
                elif line.startswith("운영시간:") or "운영시간:" in line:
                    place_info["hours"] = line.split("운영시간:")[-1].strip()
                elif line.startswith("웹사이트:") or "홈페이지:" in line:
                    place_info["website"] = line.split(":")[-1].strip()
                elif line.startswith("평점:") or "별점:" in line:
                    place_info["rating"] = line.split(":")[-1].strip()
                elif line.startswith("가격:") or "요금:" in line:
                    place_info["price_range"] = line.split(":")[-1].strip()
                elif not any(keyword in line for keyword in ["이름:", "주소:", "전화:", "운영시간:", "웹사이트:", "평점:", "가격:"]):
                    # 설명으로 추가
                    if place_info["description"]:
                        place_info["description"] += " " + line
                    else:
                        place_info["description"] = line

            # 설명 길이 제한
            if len(place_info["description"]) > 200:
                place_info["description"] = place_info["description"][:200] + "..."

            # 태그 추출 (카테고리 기반)
            category = place_info["category"].lower()
            if "맛집" in category or "음식" in category:
                place_info["tags"].append("맛집")
            if "카페" in category:
                place_info["tags"].append("카페")
            if "관광" in category or "명소" in category:
                place_info["tags"].append("관광지")
            if "자연" in category:
                place_info["tags"].append("자연")

            structured_places.append(place_info)

        except Exception as e:
            print(f"⚠️ 장소 데이터 파싱 오류: {e}")
            # 최소한의 정보라도 저장
            structured_places.append({
                "name": doc.page_content.split('\n')[0] if doc.page_content else "알 수 없는 장소",
                "category": doc.metadata.get("category", ""),
                "region": doc.metadata.get("region", ""),
                "city": doc.metadata.get("city", ""),
                "description": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content,
                "similarity_score": doc.metadata.get("similarity_score", 0)
            })

    print(f"🏗️ 구조화된 장소 데이터 추출 완료: {len(structured_places)}개")
    return structured_places


def extract_places_from_response(response: str, structured_places: List[dict]) -> List[dict]:
    """LLM 응답에서 언급된 장소들을 구조화된 데이터와 매칭"""
    mentioned_places = []

    try:
        # 응답에서 장소명 패턴 추출
        patterns = [
            r'- \d{2}:\d{2} - ([^(]+)',  # - 09:00 - 장소명
            r'[•\-\*] ([^(]+)',  # • 장소명
            r'\*\*([^*]+)\*\*',  # **장소명** (기존 호환)
            r'<strong>([^<]+)</strong>',  # <strong>장소명</strong>
        ]

        found_names = set()
        for pattern in patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                clean_name = match.strip()
                if len(clean_name) > 1 and clean_name not in found_names:
                    found_names.add(clean_name)

        print(f"🔍 응답에서 추출된 장소명: {list(found_names)[:5]}...")

        # 구조화된 데이터와 매칭
        for place_name in found_names:
            best_match = None
            best_score = 0

            for place in structured_places:
                place_data_name = place.get("name", "")

                # 정확한 매칭
                if place_name == place_data_name:
                    best_match = place
                    break

                # 부분 매칭
                if place_name in place_data_name or place_data_name in place_name:
                    score = len(set(place_name) & set(place_data_name)) / len(set(place_name) | set(place_data_name))
                    if score > best_score and score > 0.5:
                        best_match = place
                        best_score = score

            if best_match:
                mentioned_places.append(best_match)

        print(f"🎯 매칭된 장소: {len(mentioned_places)}개")
        return mentioned_places

    except Exception as e:
        print(f"❌ 장소 매칭 오류: {e}")
        return structured_places[:10]  # 폴백: 상위 10개 반환


def find_place_in_itinerary(place_name: str, itinerary: list) -> int:
    """일정에서 장소가 속한 일차 찾기"""
    from utils.travel_planner import normalize_place_name

    normalized_place = normalize_place_name(place_name)

    for day_info in itinerary:
        day_num = day_info.get('day', 0)
        schedule = day_info.get('schedule', [])

        for item in schedule:
            item_place = normalize_place_name(item.get('place_name', ''))
            if normalized_place == item_place or normalized_place in item_place or item_place in normalized_place:
                return day_num

    return -1


def get_place_from_recommendations(place_id: str, table_name: str) -> dict:
    """추천 테이블에서 특정 장소 정보 조회"""
    try:
        engine = shared_engine

        # 테이블명 보안 검증
        allowed_tables = ['travel_recommendations', 'restaurant_recommendations', 'accommodation_recommendations']
        if table_name not in allowed_tables:
            print(f"⚠️ 허용되지 않은 테이블명: {table_name}")
            return {}

        # 파라미터 바인딩을 사용한 안전한 쿼리
        query = text(f"""
            SELECT *
            FROM {table_name}
            WHERE id = :place_id
            LIMIT 1
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"place_id": place_id}).fetchone()

            if result:
                # 결과를 딕셔너리로 변환
                return dict(result._mapping)
            else:
                print(f"⚠️ 장소를 찾을 수 없음: {place_id} in {table_name}")
                return {}

    except Exception as e:
        print(f"❌ 장소 조회 오류: {e}")
        return {}


def find_place_in_recommendations(place_name: str) -> dict:
    """추천 테이블들에서 장소명으로 검색"""
    try:
        engine = shared_engine
        tables = ['travel_recommendations', 'restaurant_recommendations']

        for table_name in tables:
            query = text(f"""
                SELECT *
                FROM {table_name}
                WHERE name ILIKE :place_name
                ORDER BY
                    CASE
                        WHEN name = :exact_name THEN 1
                        WHEN name ILIKE :place_name THEN 2
                        ELSE 3
                    END
                LIMIT 1
            """)

            with engine.connect() as conn:
                result = conn.execute(query, {
                    "place_name": f"%{place_name}%",
                    "exact_name": place_name
                }).fetchone()

                if result:
                    place_data = dict(result._mapping)
                    place_data['source_table'] = table_name
                    return place_data

        print(f"⚠️ 추천 테이블에서 장소를 찾을 수 없음: {place_name}")
        return {}

    except Exception as e:
        print(f"❌ 장소 검색 오류: {e}")
        return {}


def find_real_place_id(place_name: str, table_name: str, region: str = "") -> str:
    """실제 DB에서 장소 ID 찾기"""
    try:
        engine = shared_engine

        # 테이블명 검증
        allowed_tables = ['travel_recommendations', 'restaurant_recommendations', 'accommodation_recommendations']
        if table_name not in allowed_tables:
            return ""

        # 지역 조건 추가
        region_condition = ""
        params = {"place_name": f"%{place_name}%"}

        if region:
            region_condition = "AND (region ILIKE :region OR city ILIKE :region)"
            params["region"] = f"%{region}%"

        query = text(f"""
            SELECT id
            FROM {table_name}
            WHERE name ILIKE :place_name
            {region_condition}
            ORDER BY
                CASE
                    WHEN name = :place_name THEN 1
                    ELSE 2
                END
            LIMIT 1
        """)

        with engine.connect() as conn:
            result = conn.execute(query, params).fetchone()

            if result:
                return str(result.id)
            else:
                return ""

    except Exception as e:
        print(f"❌ 실제 장소 ID 검색 오류: {e}")
        return ""


def parse_travel_plan(response: str, user_query: str) -> dict:
    """응답에서 여행 일정 구조 추출 (기본 파싱)"""
    from utils.travel_planner import extract_duration

    try:
        # 지역 추출
        from utils.entity_extractor import detect_query_entities
        from core.travel_context import get_travel_context

        context = get_travel_context()
        entities = detect_query_entities(user_query, context.llm, context.db_catalogs)
        regions = entities.get('regions', [])
        cities = entities.get('cities', [])

        # 시간 패턴 찾기
        time_pattern = r'\d{2}:\d{2}'
        times = re.findall(time_pattern, response)

        # 장소 패턴 찾기
        place_patterns = [
            r'- \d{2}:\d{2} - ([^(\n]+)',
            r'[•\-] ([^(\n]+)',
        ]

        places = []
        for pattern in place_patterns:
            matches = re.findall(pattern, response)
            places.extend([match.strip() for match in matches])

        # 기본 계획 구조 반환
        return {
            "query": user_query,
            "response": response,
            "regions": regions,
            "cities": cities,
            "duration": extract_duration(user_query),
            "times": times,
            "places": places[:10],  # 상위 10개
            "status": "pending"
        }

    except Exception as e:
        print(f"❌ 기본 여행 계획 파싱 오류: {e}")
        return {
            "query": user_query,
            "response": response,
            "status": "error",
            "error": str(e)
        }