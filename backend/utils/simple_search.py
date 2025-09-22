"""
단순 정보 검색 관련 기능들
"""
from utils.entity_extractor import detect_query_entities


def information_search_node(state, retriever, detect_query_entities_wrapper):
    """단순 정보 검색 처리 노드 (리스트 형태 응답)"""
    if not state.get("messages"):
        return {
            **state,
            "conversation_context": "검색할 메시지가 없습니다."
        }

    user_query = state["messages"][-1]
    print(f"📋 단순 정보 검색 처리: '{user_query}'")

    try:
        # 지역/카테고리 정보 추출
        try:
            entities = detect_query_entities_wrapper(user_query)
            regions = entities.get('regions', [])
            cities = entities.get('cities', [])
            categories = entities.get('categories', [])
        except Exception as e:
            print(f"⚠️ 엔티티 추출 실패, 키워드 기반 폴백 사용: {e}")
            # 키워드 기반 폴백 로직
            regions, cities, categories = _extract_entities_from_keywords(user_query)

        print(f"📋 추출된 정보 - 지역: {regions}, 도시: {cities}, 카테고리: {categories}")

        # 벡터 검색으로 관련 장소 정보 수집
        docs = retriever._get_relevant_documents(user_query)

        # 지역 필터링
        target_regions = regions + cities
        if target_regions:
            filtered_docs = []
            for doc in docs:
                doc_region = doc.metadata.get('region', '').lower()
                doc_city = doc.metadata.get('city', '').lower()

                for region in target_regions:
                    region_lower = region.lower()
                    if (region_lower in doc_region or region_lower in doc_city or
                        region_lower.replace('특별시', '').replace('광역시', '').replace('도', '') in doc_region or
                        region_lower.replace('특별시', '').replace('광역시', '').replace('도', '') in doc_city):
                        filtered_docs.append(doc)
                        break

            if filtered_docs:
                docs = filtered_docs

        # 카테고리 필터링 추가
        if categories:
            category_filtered_docs = []
            for doc in docs:
                doc_category = doc.metadata.get('category', '').lower()

                # 카테고리 매칭 확인
                for category in categories:
                    category_lower = category.lower()

                    # 숙박 관련 카테고리 처리
                    if category_lower in ['숙박', '호텔', '펜션', '민박', '게스트하우스']:
                        accommodation_keywords = ['호텔', '펜션', '민박', '게스트하우스', '리조트', '모텔', '한옥']
                        if any(keyword in doc_category for keyword in accommodation_keywords):
                            category_filtered_docs.append(doc)
                            break
                    # 맛집 관련 카테고리 처리
                    elif category_lower in ['맛집', '음식', '식당', '레스토랑']:
                        food_keywords = ['맛집', '음식', '식당', '레스토랑', '카페', '한식', '중식', '일식', '양식']
                        if any(keyword in doc_category for keyword in food_keywords):
                            category_filtered_docs.append(doc)
                            break
                    # 기타 카테고리는 직접 매칭
                    elif category_lower in doc_category:
                        category_filtered_docs.append(doc)
                        break

            if category_filtered_docs:
                docs = category_filtered_docs
                print(f"📋 카테고리 필터링 완료: {len(docs)}개 ({categories}) 결과 선별")
            else:
                print(f"⚠️ 카테고리 '{categories}' 필터링 결과 없음")

        # 상위 20개로 제한
        docs = docs[:20]

        if docs:
            # 장소 정보를 리스트 형태로 추출
            places_info = []
            for doc in docs:
                content = doc.page_content

                # 장소명 추출
                place_name = content.split('\n')[0] if content else "알 수 없는 장소"
                if "이름:" in place_name:
                    place_name = place_name.split("이름:")[-1].strip()

                # 메타데이터에서 추가 정보 추출
                region = doc.metadata.get('region', '')
                city = doc.metadata.get('city', '')
                category = doc.metadata.get('category', '')

                # 간단한 설명 추출 (첫 3줄 정도)
                lines = content.split('\n')
                description_lines = [line.strip() for line in lines[1:4] if line.strip()]
                description = ' '.join(description_lines)[:100] + "..." if description_lines else ""

                places_info.append({
                    'name': place_name,
                    'region': region,
                    'city': city,
                    'category': category,
                    'description': description
                })

            # 리스트 형태 응답 생성
            response_lines = [f"<strong>{user_query} 검색 결과</strong>\n"]

            for i, place in enumerate(places_info, 1):
                location_info = f"{place['city']}" if place['city'] else f"{place['region']}"
                response_lines.append(f"{i}. <strong>{place['name']}</strong> ({location_info})")
                if place['description']:
                    response_lines.append(f"   {place['description']}")
                response_lines.append("")  # 빈 줄

            response = "\n".join(response_lines)

        else:
            response = f"'{user_query}'에 대한 검색 결과를 찾을 수 없습니다."

        print(f"✅ 단순 정보 검색 완료. 결과: {len(docs)}개 장소")

        return {
            **state,
            "rag_results": docs,
            "conversation_context": response,
            "formatted_ui_response": {"content": response, "type": "simple_list"}
        }

    except Exception as e:
        print(f"❌ 단순 정보 검색 오류: {e}")
        return {
            **state,
            "conversation_context": f"정보 검색 중 오류가 발생했습니다: {str(e)}"
        }


def search_places(query, target_categories=None):
    """장소 검색 기본 함수 (기존 로직 유지)"""
    # 기존 search_places 함수 내용을 여기에 이동할 수 있음
    pass


def search_places_by_type(query, regions, cities):
    """타입별 장소 검색 함수 (기존 로직 유지)"""
    # 기존 search_places_by_type 함수 내용을 여기에 이동할 수 있음
    pass


def search_places_with_filter(query, regions, cities, target_categories):
    """필터를 적용한 장소 검색 함수 (기존 로직 유지)"""
    # 기존 search_places_with_filter 함수 내용을 여기에 이동할 수 있음
    pass