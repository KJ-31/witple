def parse_travel_dates(travel_dates: str, duration: str = "") -> dict:
    """여행 날짜 문자열을 파싱하여 startDate, endDate, days 반환"""
    import re
    from datetime import datetime, timedelta

    print(f"🔧 parse_travel_dates 호출: travel_dates='{travel_dates}', duration='{duration}'")

    result = {
        "startDate": "",
        "endDate": "",
        "days": ""
    }

    if not travel_dates or travel_dates == "미정":
        print(f"📅 날짜 정보 없음, duration에서 일수 추출 시도")
        # duration에서 일수 추출 시도
        if duration:
            duration_match = re.search(r'(\d+)박', duration)
            if duration_match:
                nights = int(duration_match.group(1))
                result["days"] = str(nights + 1)  # 박 + 1 = 일
                print(f"📅 duration에서 추출: {nights}박 → {result['days']}일")
            else:
                print(f"📅 duration에서 박수 추출 실패: '{duration}'")
        else:
            print(f"📅 duration도 없음")
        return result

    try:
        # 1. YYYY-MM-DD 형태의 날짜들 먼저 추출
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        dates = re.findall(date_pattern, travel_dates)
        print(f"📅 YYYY-MM-DD 형태 추출: {dates}")

        # 2. 자연어 날짜 추출 및 변환
        if not dates:
            print(f"📅 자연어 날짜 파싱 시도")
            current_year = datetime.now().year
            current_month = datetime.now().month

            # "N월 N일" 패턴 추출
            month_day_pattern = r'(\d{1,2})월\s*(\d{1,2})일'
            month_day_matches = re.findall(month_day_pattern, travel_dates)
            if month_day_matches:
                for month, day in month_day_matches:
                    formatted_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
                    dates.append(formatted_date)
                    print(f"📅 {month}월 {day}일 → {formatted_date}")

            # "N일부터" 패턴 (현재 월 기준)
            if not dates:
                day_pattern = r'(\d{1,2})일부터'
                day_matches = re.findall(day_pattern, travel_dates)
                if day_matches:
                    day = day_matches[0]
                    formatted_date = f"{current_year}-{current_month:02d}-{int(day):02d}"
                    dates.append(formatted_date)
                    print(f"📅 {day}일부터 → {formatted_date}")

            # "내일" 처리
            if "내일" in travel_dates and not dates:
                tomorrow = datetime.now() + timedelta(days=1)
                formatted_date = tomorrow.strftime('%Y-%m-%d')
                dates.append(formatted_date)
                print(f"📅 내일 → {formatted_date}")

        print(f"📅 최종 추출된 날짜들: {dates}")

        if len(dates) >= 2:
            # 시작일과 종료일이 모두 있는 경우
            print(f"📅 시작일과 종료일 모두 있음: {dates[0]} ~ {dates[1]}")
            start_date = datetime.strptime(dates[0], '%Y-%m-%d')
            end_date = datetime.strptime(dates[1], '%Y-%m-%d')

            result["startDate"] = dates[0]
            result["endDate"] = dates[1]
            result["days"] = str((end_date - start_date).days + 1)
            print(f"📅 계산된 일수: {result['days']}일")

        elif len(dates) == 1:
            # 시작일만 있는 경우 - duration에서 종료일 계산
            print(f"📅 시작일만 있음: {dates[0]}, duration으로 종료일 계산")
            start_date = datetime.strptime(dates[0], '%Y-%m-%d')
            result["startDate"] = dates[0]

            # duration에서 일수 추출
            if duration:
                duration_match = re.search(r'(\d+)박', duration)
                if duration_match:
                    nights = int(duration_match.group(1))
                    days = nights + 1
                    end_date = start_date + timedelta(days=days-1)
                    result["endDate"] = end_date.strftime('%Y-%m-%d')
                    result["days"] = str(days)
                    print(f"📅 계산된 종료일: {result['endDate']}, 일수: {result['days']}")
                else:
                    print(f"📅 duration에서 박수 추출 실패: '{duration}'")

        # 상대적 날짜 처리 ("이번 주말", "다음 달" 등)
        elif "이번 주말" in travel_dates:
            print(f"📅 이번 주말 처리")
            today = datetime.now()
            # 이번 주 토요일 찾기
            days_until_saturday = (5 - today.weekday()) % 7
            if days_until_saturday == 0 and today.weekday() == 5:  # 오늘이 토요일
                saturday = today
            else:
                saturday = today + timedelta(days=days_until_saturday)
            sunday = saturday + timedelta(days=1)

            result["startDate"] = saturday.strftime('%Y-%m-%d')
            result["endDate"] = sunday.strftime('%Y-%m-%d')
            result["days"] = "2"
            print(f"📅 이번 주말: {result['startDate']} ~ {result['endDate']}")

        elif "다음 주말" in travel_dates:
            print(f"📅 다음 주말 처리")
            today = datetime.now()
            # 다음 주 토요일 찾기
            days_until_next_saturday = ((5 - today.weekday()) % 7) + 7
            saturday = today + timedelta(days=days_until_next_saturday)
            sunday = saturday + timedelta(days=1)

            result["startDate"] = saturday.strftime('%Y-%m-%d')
            result["endDate"] = sunday.strftime('%Y-%m-%d')
            result["days"] = "2"
            print(f"📅 다음 주말: {result['startDate']} ~ {result['endDate']}")

        else:
            print(f"📅 날짜 패턴 매칭 안됨, duration만으로 일수 추출 시도")
            if duration:
                duration_match = re.search(r'(\d+)박', duration)
                if duration_match:
                    nights = int(duration_match.group(1))
                    result["days"] = str(nights + 1)
                    print(f"📅 duration에서만 추출: {nights}박 → {result['days']}일")

        # 과거 날짜 검증 - 불가능한 날짜 안내
        today = datetime.now().date()
        if result.get("startDate"):
            try:
                start_date = datetime.strptime(result["startDate"], '%Y-%m-%d').date()
                if start_date < today:
                    print(f"❌ 과거 날짜 감지: {result['startDate']} - 불가능한 날짜")
                    # 과거 날짜인 경우 결과를 초기화하고 에러 메시지 추가
                    result = {
                        "startDate": "",
                        "endDate": "",
                        "days": "",
                        "error": f"선택하신 날짜 {result['startDate']}는 과거 날짜입니다. 오늘 이후의 날짜를 선택해주세요."
                    }
                    print(f"📅 과거 날짜로 인한 파싱 실패")
                    return result
            except:
                pass

        # 날짜 파싱 결과 테스트 출력
        if any(result.values()):
            print(f"✅ 날짜 파싱 성공 - startDate: {result.get('startDate', 'N/A')}, endDate: {result.get('endDate', 'N/A')}, days: {result.get('days', 'N/A')}")
        else:
            print(f"❌ 날짜 파싱 실패 - 모든 필드 비어있음")

        print(f"📅 최종 날짜 파싱 결과: {result}")
        return result

    except Exception as e:
        print(f"⚠️ 날짜 파싱 오류: {e}")
        import traceback
        traceback.print_exc()
        # duration에서라도 일수 추출
        if duration:
            duration_match = re.search(r'(\d+)박', duration)
            if duration_match:
                nights = int(duration_match.group(1))
                result["days"] = str(nights + 1)
                print(f"📅 오류 발생, duration에서만 추출: {nights}박 → {result['days']}일")
        print(f"📅 오류 후 최종 결과: {result}")
        return result