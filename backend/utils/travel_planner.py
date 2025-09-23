"""
여행 계획 관련 기능들
"""
import re
from datetime import datetime


def parse_travel_dates(travel_dates: str, duration: str = "미정") -> dict:
    """여행 날짜 정보를 구조화된 형태로 파싱"""
    try:
        parsed_result = {
            "startDate": "",
            "endDate": "",
            "days": ""
        }

        if not travel_dates or travel_dates == "미정":
            return parsed_result

        # 날짜 범위 패턴 (2025-10-04부터 2025-10-06까지)
        range_pattern = r'(\d{4}-\d{2}-\d{2})부터\s*(\d{4}-\d{2}-\d{2})까지'
        range_match = re.search(range_pattern, travel_dates)

        if range_match:
            start_date = range_match.group(1)
            end_date = range_match.group(2)
            parsed_result["startDate"] = start_date
            parsed_result["endDate"] = end_date

            # 일수 계산
            try:
                from datetime import datetime
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                days = (end - start).days + 1
                parsed_result["days"] = f"{days}일"
            except:
                parsed_result["days"] = duration if duration != "미정" else ""

            return parsed_result

        # 단일 날짜 패턴 (2025-10-04)
        single_pattern = r'(\d{4}-\d{2}-\d{2})'
        single_match = re.search(single_pattern, travel_dates)

        if single_match:
            date = single_match.group(1)
            parsed_result["startDate"] = date

            # duration이 있으면 종료일 계산
            if duration and duration != "미정":
                day_match = re.search(r'(\d+)', duration)
                if day_match:
                    days = int(day_match.group(1))
                    try:
                        start = datetime.strptime(date, "%Y-%m-%d")
                        from datetime import timedelta
                        end = start + timedelta(days=days-1)
                        parsed_result["endDate"] = end.strftime("%Y-%m-%d")
                        parsed_result["days"] = f"{days}일"
                    except:
                        pass

            return parsed_result

        # 상대적 날짜는 그대로 반환
        parsed_result["startDate"] = travel_dates
        parsed_result["days"] = duration if duration != "미정" else ""
        return parsed_result

    except Exception as e:
        print(f"❌ 날짜 파싱 오류: {e}")
        return {"startDate": "", "endDate": "", "days": ""}


def parse_enhanced_travel_plan(response: str, user_query: str, structured_places: list, travel_dates: str = "미정") -> dict:
    """LLM 응답에서 향상된 여행 계획 추출 (구조화된 장소 데이터 포함)"""
    try:
        # 날짜 파싱
        duration = extract_duration(user_query)
        parsed_dates = parse_travel_dates(travel_dates, duration)

        plan = {
            "query": user_query,
            "response": response,
            "travel_dates": travel_dates,
            "parsed_dates": parsed_dates,
            "duration": duration,
            "status": "pending",
            "plan_id": generate_plan_id(),
            "created_at": datetime.now().isoformat(),
            "days": [],
            "places": []
        }

        # 일차별 구조 파싱 (더 유연한 패턴 - LLM_RAG_backup.py에서 가져옴)
        day_patterns = [
            r'<strong>\[(\d+)일차\]</strong>',  # <strong>[1일차]</strong>
            r'\[(\d+)일차\]',                    # [1일차]
            r'(\d+)일차',                        # 1일차
            r'<strong>(\d+)일차</strong>',       # <strong>1일차</strong>
            r'\*\*(\d+일차|Day\s*\d+)\*\*',     # 기존 패턴도 포함
            r'(\d+일차:|Day\s*\d+:)'            # 기존 패턴도 포함
        ]

        # 가장 많이 매칭되는 패턴 사용
        best_pattern = None
        best_matches = []
        for pattern in day_patterns:
            matches = re.findall(pattern, response)
            if len(matches) > len(best_matches):
                best_matches = matches
                best_pattern = pattern

        print(f"🔍 일차 패턴 매칭 결과:")
        for i, pattern in enumerate(day_patterns):
            matches = re.findall(pattern, response)
            print(f"   패턴 {i+1}: {pattern} -> {len(matches)}개 매칭")

        if best_pattern and best_matches:
            print(f"🗓️ 일차 패턴 인식: {len(best_matches)}개 일차 발견 (패턴: {best_pattern})")

            # 응답을 일차별로 분할
            day_sections = re.split(best_pattern, response)
            print(f"📊 day_sections 분할 결과: {len(day_sections)}개 섹션")

            for i, section in enumerate(day_sections):
                print(f"   섹션 {i}: '{section[:100]}{'...' if len(section) > 100 else ''}'")

            # re.split 결과 분석: [텍스트, 그룹1, 텍스트, 그룹2, 텍스트, ...]
            # 매칭된 그룹들과 그 다음 텍스트를 올바르게 매핑
            for i in range(1, len(day_sections), 2):  # 홀수 인덱스가 매칭된 일차 번호
                if i + 1 < len(day_sections):
                    day_num_str = day_sections[i].strip()
                    day_content = day_sections[i + 1].strip()

                    print(f"🔍 처리 중: 섹션 {i} (일차번호) = '{day_num_str}', 섹션 {i+1} (내용) = '{day_content[:200]}{'...' if len(day_content) > 200 else ''}'")

                    # 일차 번호 추출 (숫자만)
                    day_num_match = re.search(r'(\d+)', day_num_str)
                    if not day_num_match:
                        print(f"   ❌ 일차 번호 추출 실패: '{day_num_str}'")
                        continue

                    try:
                        day_num = int(day_num_match.group(1))
                    except ValueError:
                        print(f"   ❌ 일차 번호 변환 실패: '{day_num_str}'")
                        continue

                    print(f"📅 {day_num}일차 파싱 중... (내용 길이: {len(day_content)})")

                    # 내용이 비어있으면 스킵
                    if not day_content or len(day_content.strip()) < 10:
                        print(f"   ⚠️ {day_num}일차: 내용이 비어있어서 스킵")
                        continue

                    # 해당 일차의 일정 파싱
                    day_schedule = parse_day_schedule(day_content, structured_places)
                    print(f"   🔧 parse_day_schedule 결과: {len(day_schedule) if day_schedule else 0}개 일정")

                    if day_schedule:  # 일정이 있을 때만 추가
                        plan["days"].append({
                            "day": day_num,
                            "schedule": day_schedule
                        })
                        print(f"   ✅ {day_num}일차: {len(day_schedule)}개 일정 파싱됨")
                        # 개별 장소도 places 배열에 추가
                        for item in day_schedule:
                            if item.get("place_info"):
                                plan["places"].append(item["place_info"])
                    else:
                        print(f"   ⚠️ {day_num}일차: 파싱된 일정이 없어서 추가하지 않음")
                else:
                    print(f"   ⚠️ 섹션 {i}: 다음 섹션이 없어서 스킵")

            print(f"🏁 최종 파싱 결과: {len(plan['days'])}개 일차 생성됨")
        else:
            print(f"⚠️ 일차 패턴 인식 실패, 단일 일정으로 처리")
            # 일차 구분 없이 전체를 하나의 일정으로 처리
            single_day_schedule = parse_day_schedule(response, structured_places)
            if single_day_schedule:
                plan["days"].append({
                    "day": 1,
                    "schedule": single_day_schedule
                })
                # 개별 장소도 places 배열에 추가
                for item in single_day_schedule:
                    if item.get("place_info"):
                        plan["places"].append(item["place_info"])

        # 장소가 없으면 전체 응답에서 추출
        if not plan["places"] and structured_places:
            plan["places"] = structured_places[:10]  # 상위 10개만

        return plan

    except Exception as e:
        print(f"❌ 여행 계획 파싱 오류: {e}")
        return {
            "query": user_query,
            "response": response,
            "travel_dates": travel_dates,
            "parsed_dates": {"startDate": "", "endDate": "", "days": ""},
            "duration": "미정",
            "status": "pending",
            "plan_id": generate_plan_id(),
            "created_at": datetime.now().isoformat(),
            "days": [],
            "places": structured_places[:5] if structured_places else []
        }


def parse_day_schedule(day_content: str, structured_places: list) -> list:
    """일별 스케줄 파싱"""
    print(f"🔧 parse_day_schedule 시작")
    print(f"   📝 day_content 길이: {len(day_content)}")
    print(f"   📝 day_content 내용: '{day_content[:300]}{'...' if len(day_content) > 300 else ''}'")
    print(f"   🏛️ structured_places 수: {len(structured_places)}")

    schedule = []

    # 시간-장소-설명 패턴 매칭 개선
    patterns = [
        r'(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})?\s*[:\-]?\s*([^(\n]+?)(?:\(([^)]+)\))?(?:\n|$)',
        r'(\d{1,2}:\d{2})\s*[:\-]?\s*([^(\n]+?)(?:\(([^)]+)\))?(?:\n|$)',
        r'[•\-\*]\s*(\d{1,2}:\d{2})\s*[-~]?\s*(\d{1,2}:\d{2})?\s*[:\-]?\s*([^(\n]+?)(?:\(([^)]+)\))?(?:\n|$)',
        r'[•\-\*]\s*([^(\n]+?)(?:\(([^)]+)\))?(?:\n|$)'
    ]

    print(f"🔍 패턴 매칭 시작:")
    for j, pattern in enumerate(patterns):
        matches = re.findall(pattern, day_content, re.MULTILINE)
        print(f"   패턴 {j+1}: {pattern[:50]}{'...' if len(pattern) > 50 else ''} -> {len(matches)}개 매칭")

        if matches:
            print(f"     매칭 결과: {matches}")
            for match in matches:
                if len(match) >= 3:
                    time_start = match[0] if match[0] else ""
                    time_end = match[1] if len(match) > 1 and match[1] else ""
                    place_name = match[2] if len(match) > 2 else match[0]
                    description = match[3] if len(match) > 3 and match[3] else ""

                    if time_end:
                        time_range = f"{time_start} - {time_end}"
                    elif time_start and re.match(r'\d{1,2}:\d{2}', time_start):
                        time_range = time_start
                    else:
                        time_range = ""
                        if not re.match(r'\d{1,2}:\d{2}', place_name):
                            place_name = time_start
                        else:
                            continue

                    # 장소명 정리
                    place_name_clean = normalize_place_name(place_name)
                    print(f"     🏛️ 장소 '{place_name}' -> 정규화: '{place_name_clean}'")

                    # 구조화된 장소에서 매칭되는 정보 찾기
                    matched_place = None
                    for place in structured_places:
                        place_name_normalized = normalize_place_name(place.get("name", ""))

                        if (place_name_clean == place_name_normalized or
                            (place_name_clean and place_name_normalized and
                             (place_name_clean in place_name_normalized or
                              place_name_normalized in place_name_clean))):
                            matched_place = place
                            print(f"       ✅ 매칭 성공: '{place_name_clean}' <-> '{place_name_normalized}'")
                            break

                    if not matched_place:
                        print(f"       ❌ 매칭 실패: '{place_name_clean}' (structured_places에서 찾을 수 없음)")

                    schedule_item = {
                        "time": time_range.strip() if time_range else "",
                        "place_name": place_name.strip(),
                        "description": description.strip(),
                        "category": matched_place.get("category", "") if matched_place else "",
                        "place_info": matched_place
                    }
                    schedule.append(schedule_item)
                    print(f"     ➕ schedule_item 추가: {schedule_item['place_name']} ({schedule_item['time']})")

    # 중복 제거
    seen = set()
    unique_schedule = []
    print(f"🧹 중복 제거 전: {len(schedule)}개 일정")
    for item in schedule:
        key = (item["place_name"], item["time"])
        if key not in seen:
            seen.add(key)
            unique_schedule.append(item)
        else:
            print(f"   🔄 중복 제거: {item['place_name']} ({item['time']})")

    print(f"✅ parse_day_schedule 완료: {len(unique_schedule)}개 일정 반환")
    for i, item in enumerate(unique_schedule):
        print(f"   {i+1}. {item['place_name']} ({item['time']}) - place_info: {'있음' if item['place_info'] else '없음'}")

    return unique_schedule


def normalize_place_name(place_name: str) -> str:
    """장소명 정규화"""
    if not place_name:
        return ""

    # 불필요한 문자 제거
    cleaned = re.sub(r'[^\w\s가-힣]', '', place_name)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # 공통 접미사 제거
    suffixes = ['카페', '레스토랑', '식당', '박물관', '미술관', '공원', '해변', '시장']
    for suffix in suffixes:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
            base_name = cleaned[:-len(suffix)].strip()
            if base_name:
                return base_name

    return cleaned


def extract_duration(query: str) -> str:
    """쿼리에서 여행 기간 추출"""
    duration_patterns = [
        r'(\d+박\s*\d+일)',
        r'(\d+일\s*\d+박)',
        r'(\d+일)',
        r'(당일)',
        r'(하루)',
    ]

    for pattern in duration_patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(0)

    return "미정"


def parse_duration_to_days(duration: str) -> int:
    """기간 문자열을 실제 일수로 변환"""
    if not duration or duration == "미정":
        return 1

    # "1박2일" -> 2일, "2박3일" -> 3일
    night_day_match = re.search(r'(\d+)박\s*(\d+)일', duration)
    if night_day_match:
        return int(night_day_match.group(2))  # 일수 반환

    # "2일1박" -> 2일
    day_night_match = re.search(r'(\d+)일\s*(\d+)박', duration)
    if day_night_match:
        return int(day_night_match.group(1))  # 일수 반환

    # "3일" -> 3일
    day_match = re.search(r'(\d+)일', duration)
    if day_match:
        return int(day_match.group(1))

    # "당일" 또는 "하루" -> 1일
    if "당일" in duration or "하루" in duration:
        return 1

    return 1  # 기본값


def generate_plan_id() -> str:
    """여행 계획 ID 생성"""
    import uuid
    return str(uuid.uuid4())[:8]


def create_formatted_ui_response(travel_plan: dict, raw_response: str) -> dict:
    """UI용 구조화된 응답 생성"""
    try:
        return {
            "content": raw_response,
            "type": "travel_plan",
            "plan_id": travel_plan.get("plan_id", ""),
            "travel_dates": travel_plan.get("travel_dates", "미정"),
            "parsed_dates": travel_plan.get("parsed_dates", {}),
            "duration": travel_plan.get("duration", "미정"),
            "days": travel_plan.get("days", []),
            "places": travel_plan.get("places", []),
            "status": travel_plan.get("status", "pending")
        }
    except Exception as e:
        print(f"❌ UI 응답 포맷팅 오류: {e}")
        return {
            "content": raw_response,
            "type": "text",
            "error": str(e)
        }


def is_meal_activity(description: str) -> bool:
    """식사 활동 여부 판단"""
    meal_keywords = ["식사", "점심", "저녁", "아침", "브런치", "식당", "맛집", "먹기"]
    return any(keyword in description for keyword in meal_keywords)


def format_travel_response_with_linebreaks(response: str) -> str:
    """여행 응답에 적절한 개행 추가"""
    lines = response.split('\n')
    formatted_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 제목 형태 (**, ##으로 시작)
        if stripped.startswith('**') or stripped.startswith('#'):
            if formatted_lines and not formatted_lines[-1] == '':
                formatted_lines.append('')
            formatted_lines.append(stripped)
            formatted_lines.append('')
        # 리스트 형태 (-, *, •, 숫자.로 시작)
        elif re.match(r'^[\-\*•]\s|^\d+\.\s|^\d+:\d+', stripped):
            formatted_lines.append(stripped)
        else:
            formatted_lines.append(stripped)

    return '\n'.join(formatted_lines)