"""
날씨 정보 처리 모듈
기상청 API를 통한 날씨 정보 조회 및 처리
"""

import os
import requests
import datetime
import re
from typing import Optional

# 기상청 API 키 (환경변수에서 읽기)
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')

def get_weather_info(region_name):
    """기상청 API로 날씨 정보 가져오기"""
    if not WEATHER_API_KEY:
        return "❌ 기상청 API 키가 설정되지 않았습니다. .env 파일에 WEATHER_API_KEY를 추가해주세요."

    try:
        print(f"🌤️ {region_name} 날씨 정보 조회 중...")

        # 현재 날짜와 다음 날짜 계산
        now = datetime.datetime.now()
        travel_date = now + datetime.timedelta(days=0)  # 오늘 날짜
        date_str = travel_date.strftime('%Y%m%d')
        time_str = (now + datetime.timedelta(hours=1)).strftime('%H00')  # 1시간 후

        print(f"📅 여행일: {date_str}, 현재로부터 0일 후")

        # 지역별 좌표 매핑
        region_coords = {
            '서울': {'nx': 60, 'ny': 127},
            '부산': {'nx': 98, 'ny': 76},
            '대구': {'nx': 89, 'ny': 90},
            '인천': {'nx': 55, 'ny': 124},
            '광주': {'nx': 58, 'ny': 74},
            '대전': {'nx': 67, 'ny': 100},
            '울산': {'nx': 102, 'ny': 84},
            '경기': {'nx': 60, 'ny': 120},
            '강원': {'nx': 73, 'ny': 134},
            '충북': {'nx': 69, 'ny': 107},
            '충남': {'nx': 68, 'ny': 100},
            '전북': {'nx': 63, 'ny': 89},
            '전남': {'nx': 51, 'ny': 67},
            '경북': {'nx': 87, 'ny': 106},
            '경남': {'nx': 91, 'ny': 77},
            '제주': {'nx': 52, 'ny': 38},
            '제주특별자치도': {'nx': 52, 'ny': 38},
            '제주도': {'nx': 52, 'ny': 38}
        }

        coords = region_coords.get(region_name, region_coords['서울'])

        print(f"🌤️ {region_name} 단기예보 조회 중... (0일 후)")

        base_date = (now - datetime.timedelta(hours=1)).strftime('%Y%m%d')
        base_time = "0500"  # 05:00 발표 기준

        if now.hour >= 23:
            base_time = "2300"
        elif now.hour >= 20:
            base_time = "2000"
        elif now.hour >= 17:
            base_time = "1700"
        elif now.hour >= 14:
            base_time = "1400"
        elif now.hour >= 11:
            base_time = "1100"
        elif now.hour >= 8:
            base_time = "0800"
        else:
            base_time = "0500"

        # 3번 재시도
        for attempt in range(3):
            try:
                print(f"🌤️ 기상청 API 호출 시도 {attempt + 1}/3")

                params = {
                    'serviceKey': WEATHER_API_KEY,
                    'pageNo': '1',
                    'numOfRows': '1000',
                    'dataType': 'JSON',
                    'base_date': base_date,
                    'base_time': base_time,
                    'nx': coords['nx'],
                    'ny': coords['ny']
                }

                response = requests.get(
                    'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst',
                    params=params,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    if 'response' in data and 'body' in data['response'] and 'items' in data['response']['body']:
                        items = data['response']['body']['items']['item']
                        return parse_weather_data(items, region_name)
                    else:
                        print(f"❌ API 응답 구조 오류 (시도 {attempt + 1})")
                        if attempt < 2:
                            continue
                else:
                    print(f"❌ API 호출 실패: {response.status_code} (시도 {attempt + 1})")
                    if attempt < 2:
                        continue

            except Exception as api_error:
                print(f"❌ API 호출 중 오류 (시도 {attempt + 1}): {api_error}")
                if attempt < 2:
                    continue

        return f"📍 <strong>{region_name}</strong>\n날씨 정보를 가져올 수 없어 일반적인 계절 정보를 제공합니다.\n\n{get_seasonal_weather_info(region_name, now.month)}"

    except Exception as e:
        print(f"❌ 전체 날씨 조회 오류: {e}")
        return f"❌ 날씨 정보 조회 오류: {e}"

def parse_weather_data(items, region_name):
    """기상청 API 응답 데이터 파싱"""
    try:
        # 오늘과 내일 날씨 데이터 분류
        today = datetime.datetime.now().strftime('%Y%m%d')
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y%m%d')

        today_data = {}
        tomorrow_data = {}

        for item in items:
            fcst_date = item['fcstDate']
            fcst_time = item['fcstTime']
            category = item['category']
            fcst_value = item['fcstValue']

            if fcst_date == today and fcst_time in ['1200', '1500', '1800']:
                if category not in today_data:
                    today_data[category] = fcst_value
            elif fcst_date == tomorrow and fcst_time in ['1200', '1500']:
                if category not in tomorrow_data:
                    tomorrow_data[category] = fcst_value

        # 날씨 정보 포맷팅
        weather_text = f"📍 <strong>{region_name} 날씨 정보</strong>\n\n"

        # 오늘 날씨
        if today_data:
            weather_text += "📅 <strong>오늘 날씨</strong>\n"
            weather_text += format_weather_detail(today_data)
            weather_text += "\n"

        # 내일 날씨
        if tomorrow_data:
            weather_text += "📅 <strong>내일 날씨</strong>\n"
            weather_text += format_weather_detail(tomorrow_data)
            weather_text += "\n"

        weather_text += "💡 <em>실시간 기상청 데이터를 기반으로 한 정보입니다.</em>"

        return weather_text

    except Exception as e:
        print(f"❌ 날씨 데이터 파싱 오류: {e}")
        return f"❌ 날씨 데이터 파싱 오류: {e}"

def format_weather_detail(data):
    """날씨 상세 정보 포맷팅"""
    try:
        # 기상청 코드 매핑
        sky_codes = {
            '1': '맑음 ☀️',
            '3': '구름많음 ⛅',
            '4': '흐림 ☁️'
        }

        pty_codes = {
            '0': '없음',
            '1': '비 🌧️',
            '2': '비/눈 🌨️',
            '3': '눈 ❄️',
            '4': '소나기 🌦️'
        }

        detail_text = ""

        # 기온 정보
        if 'TMP' in data:
            detail_text += f"🌡️ <strong>기온</strong>: {data['TMP']}°C\n"

        # 하늘 상태
        if 'SKY' in data:
            sky_desc = sky_codes.get(data['SKY'], f"코드 {data['SKY']}")
            detail_text += f"☁️ <strong>하늘</strong>: {sky_desc}\n"

        # 강수 형태
        if 'PTY' in data:
            pty_desc = pty_codes.get(data['PTY'], f"코드 {data['PTY']}")
            if data['PTY'] != '0':
                detail_text += f"🌧️ <strong>강수</strong>: {pty_desc}\n"

        # 강수 확률
        if 'POP' in data:
            detail_text += f"☔ <strong>강수확률</strong>: {data['POP']}%\n"

        # 습도
        if 'REH' in data:
            detail_text += f"💧 <strong>습도</strong>: {data['REH']}%\n"

        # 풍속
        if 'WSD' in data:
            detail_text += f"💨 <strong>풍속</strong>: {data['WSD']}m/s\n"

        return detail_text

    except Exception as e:
        return f"상세 정보 처리 오류: {e}\n"

def get_smart_weather_info(region_name, travel_date=None):
    """스마트 날씨 조회: 단기예보 우선, 실패 시 과거 데이터 폴백"""
    import datetime

    try:
        # 1. 먼저 단기예보(미래 날씨) 시도 - 현재 시간 기준 3일 이내
        current_weather = get_weather_info(region_name)

        # 기상청 API 오류가 아닌 경우 (정상 응답 또는 계절 정보)
        if not current_weather.startswith("❌"):
            return current_weather

        # 2. 단기예보 실패 시 과거 데이터 폴백
        print(f"⚠️ 단기예보 실패, 과거 데이터로 폴백: {region_name}")

        if travel_date:
            # 특정 날짜가 지정된 경우
            try:
                # 다양한 날짜 형식 처리
                if isinstance(travel_date, str):
                    # YYYY-MM-DD 형식
                    if '-' in travel_date:
                        date_obj = datetime.datetime.strptime(travel_date, '%Y-%m-%d')
                    # YYYYMMDD 형식
                    elif len(travel_date) == 8:
                        date_obj = datetime.datetime.strptime(travel_date, '%Y%m%d')
                    else:
                        date_obj = datetime.datetime.now()
                else:
                    date_obj = travel_date

                # 과거 데이터 조회 (작년 동일 시기)
                past_date = date_obj.replace(year=date_obj.year - 1)
                past_date_str = past_date.strftime('%Y%m%d')

                historical_weather = get_historical_weather_info(region_name, past_date_str)

                if historical_weather and not historical_weather.startswith("❌"):
                    simplified_weather = simplify_historical_weather(historical_weather, region_name, past_date_str)
                    return f"📍 <strong>{region_name}</strong>\n(참고: 작년 동일 시기 날씨 기록)\n\n{simplified_weather}"

            except Exception as date_error:
                print(f"⚠️ 날짜 처리 오류: {date_error}")

        # 3. 모든 방법 실패 시 계절별 일반 정보
        current_month = datetime.datetime.now().month
        return f"📍 <strong>{region_name}</strong>\n날씨 정보를 가져올 수 없어 일반적인 계절 정보를 제공합니다.\n\n{get_seasonal_weather_info(region_name, datetime.datetime.now().month)}"

    except Exception as e:
        print(f"❌ 스마트 날씨 조회 오류: {e}")
        return f"📍 <strong>{region_name}</strong>\n날씨 정보를 가져올 수 없어 일반적인 계절 정보를 제공합니다.\n\n{get_seasonal_weather_info(region_name, datetime.datetime.now().month)}"

def get_seasonal_weather_info(region_name, month):
    """계절별 일반적인 날씨 정보 제공"""
    seasonal_data = {
        1: {"temp": "영하~5°C", "desc": "춥고 건조", "clothes": "두꺼운 외투, 목도리 필수"},
        2: {"temp": "0~8°C", "desc": "추위가 절정", "clothes": "패딩, 장갑 권장"},
        3: {"temp": "5~15°C", "desc": "봄의 시작, 일교차 큼", "clothes": "얇은 외투, 레이어드"},
        4: {"temp": "10~20°C", "desc": "따뜻한 봄날씨", "clothes": "가디건, 얇은 재킷"},
        5: {"temp": "15~25°C", "desc": "화창하고 쾌적", "clothes": "반팔, 긴팔 셔츠"},
        6: {"temp": "20~28°C", "desc": "더워지기 시작", "clothes": "반팔, 선크림 필수"},
        7: {"temp": "23~32°C", "desc": "무덥고 습함, 장마", "clothes": "시원한 옷, 우산 준비"},
        8: {"temp": "25~33°C", "desc": "가장 더운 시기", "clothes": "통풍 잘되는 옷"},
        9: {"temp": "20~28°C", "desc": "선선해지기 시작", "clothes": "반팔~얇은 긴팔"},
        10: {"temp": "15~23°C", "desc": "쾌적한 가을", "clothes": "긴팔, 얇은 외투"},
        11: {"temp": "8~18°C", "desc": "쌀쌀한 날씨", "clothes": "두꺼운 외투"},
        12: {"temp": "0~8°C", "desc": "추위 시작", "clothes": "코트, 목도리"}
    }

    season_info = seasonal_data.get(month, seasonal_data[6])

    return f"""🌡️ <strong>평균 기온</strong>: {season_info['temp']}
🌤️ <strong>날씨 특징</strong>: {season_info['desc']}
👔 <strong>권장 복장</strong>: {season_info['clothes']}

💡 <em>일반적인 {month}월 날씨 정보입니다. 여행 전 최신 예보를 확인해주세요!</em>"""

def is_weather_query(query):
    """쿼리가 날씨 관련 질문인지 판단"""
    weather_keywords = [
        '날씨', '기온', '온도', '비', '눈', '바람', '습도', '맑음', '흐림',
        '강수', '기상', '일기예보', '예보', '우천', '강우', '폭우', '태풍',
        'weather', '온도가', '덥', '춥', '시원', '따뜻'
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in weather_keywords)

def is_historical_weather_query(query):
    """쿼리가 과거 날씨 관련 질문인지 판단"""
    import re

    historical_keywords = [
        '지난', '작년', '전년', '과거', '예전', '이전', '지난주', '지난달', '지난해',
        '전에', '했을 때', '당시', '그때', '옛날'
    ]

    weather_keywords = [
        '날씨', '기온', '온도', '비', '눈', '바람'
    ]

    # 구체적인 날짜 패턴 (YYYY년, MM월, DD일 등)
    date_patterns = [
        r'\d{4}년',  # 2023년
        r'\d{1,2}월',  # 12월, 3월
        r'\d{1,2}일',  # 25일, 5일
        r'\d{4}-\d{1,2}-\d{1,2}',  # 2023-12-25
        r'\d{1,2}/\d{1,2}/\d{4}',  # 12/25/2023
    ]

    query_lower = query.lower()

    # 과거 키워드 검사
    has_historical = any(keyword in query_lower for keyword in historical_keywords)

    # 날씨 키워드 검사
    has_weather = any(keyword in query_lower for keyword in weather_keywords)

    # 구체적인 날짜 패턴 검사
    has_specific_date = any(re.search(pattern, query) for pattern in date_patterns)

    return (has_historical or has_specific_date) and has_weather

def get_historical_weather_info(region_name, date_str):
    """기상청 API로 과거 날씨 정보 가져오기 (지상관측 일자료)"""
    if not WEATHER_API_KEY:
        return "❌ 기상청 API 키가 설정되지 않았습니다."

    try:
        print(f"📅 {region_name} 과거 날씨 조회: {date_str}")

        # 지역별 관측소 코드 매핑
        station_code = get_station_code(region_name)

        params = {
            'serviceKey': WEATHER_API_KEY,
            'pageNo': '1',
            'numOfRows': '1',
            'dataType': 'JSON',
            'dataCd': 'ASOS',  # 종관기상관측
            'dateCd': 'DAY',   # 일자료
            'startDt': date_str,
            'endDt': date_str,
            'stnIds': station_code
        }

        response = requests.get(
            'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList',
            params=params,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()

            if ('response' in data and
                'body' in data['response'] and
                'items' in data['response']['body'] and
                'item' in data['response']['body']['items'] and
                len(data['response']['body']['items']['item']) > 0):

                weather_data = data['response']['body']['items']['item'][0]
                return format_historical_weather_data(weather_data, region_name, date_str)
            else:
                return f"❌ {region_name}의 {date_str} 날씨 데이터를 찾을 수 없습니다."
        else:
            return f"❌ 기상청 API 호출 실패: {response.status_code}"

    except Exception as e:
        print(f"❌ 과거 날씨 조회 오류: {e}")
        return f"❌ 과거 날씨 정보 조회 오류: {e}"

def get_station_code(region_name):
    """지역명을 기상청 관측소 코드로 변환"""
    station_mapping = {
        '서울': '108',
        '부산': '159',
        '대구': '143',
        '인천': '112',
        '광주': '156',
        '대전': '133',
        '울산': '152',
        '세종': '239',
        '경기': '108',  # 서울 코드 사용
        '강원': '101',  # 춘천
        '충북': '131',  # 청주
        '충남': '129',  # 서산
        '전북': '146',  # 전주
        '전남': '165',  # 목포
        '경북': '138',  # 포항
        '경남': '155',  # 창원
        '제주': '184',
        '제주특별자치도': '184',
        '제주도': '184'
    }

    return station_mapping.get(region_name, '108')  # 기본값: 서울

def format_historical_weather_data(data, region_name, date_str):
    """과거 날씨 데이터 포맷팅"""
    try:
        # 날짜 포맷팅
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        formatted_date = f"{year}년 {month}월 {day}일"

        weather_text = f"📅 <strong>{region_name} {formatted_date} 날씨 기록</strong>\n\n"

        # 기온 정보
        if 'avgTa' in data and data['avgTa']:
            weather_text += f"🌡️ <strong>평균기온</strong>: {data['avgTa']}°C\n"
        if 'maxTa' in data and data['maxTa']:
            weather_text += f"🔥 <strong>최고기온</strong>: {data['maxTa']}°C\n"
        if 'minTa' in data and data['minTa']:
            weather_text += f"❄️ <strong>최저기온</strong>: {data['minTa']}°C\n"

        # 강수량 정보
        if 'sumRn' in data and data['sumRn']:
            if float(data['sumRn']) > 0:
                weather_text += f"🌧️ <strong>강수량</strong>: {data['sumRn']}mm\n"
            else:
                weather_text += f"☀️ <strong>강수량</strong>: 없음\n"

        # 습도 정보
        if 'avgRhm' in data and data['avgRhm']:
            weather_text += f"💧 <strong>평균습도</strong>: {data['avgRhm']}%\n"

        # 풍속 정보
        if 'avgWs' in data and data['avgWs']:
            weather_text += f"💨 <strong>평균풍속</strong>: {data['avgWs']}m/s\n"

        weather_text += f"\n💡 <em>기상청 공식 관측 데이터입니다.</em>"

        return weather_text

    except Exception as e:
        print(f"❌ 과거 날씨 데이터 포맷팅 오류: {e}")
        return f"❌ 과거 날씨 데이터 포맷팅 오류: {e}"

def simplify_historical_weather(historical_weather_text, region_name, date_str):
    """과거 날씨 데이터에서 평균 기온만 추출하여 단순화"""
    try:
        import re

        # 평균기온 정보 추출
        avg_temp_match = re.search(r'평균기온.*?(\d+(?:\.\d+)?)°C', historical_weather_text)
        max_temp_match = re.search(r'최고기온.*?(\d+(?:\.\d+)?)°C', historical_weather_text)
        min_temp_match = re.search(r'최저기온.*?(\d+(?:\.\d+)?)°C', historical_weather_text)
        rain_match = re.search(r'강수량.*?(\d+(?:\.\d+)?)mm|강수량.*?없음', historical_weather_text)

        # 날짜 포맷팅
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]

        simple_weather = f"📊 <strong>작년 동일 시기 날씨 참고</strong> ({year}년 {month}월 {day}일)\n\n"

        if avg_temp_match:
            simple_weather += f"🌡️ 평균기온: {avg_temp_match.group(1)}°C\n"

        if max_temp_match and min_temp_match:
            simple_weather += f"📈 기온 범위: {min_temp_match.group(1)}°C ~ {max_temp_match.group(1)}°C\n"

        if rain_match:
            if "없음" in rain_match.group(0):
                simple_weather += f"☀️ 강수: 없음\n"
            else:
                simple_weather += f"🌧️ 강수량: {rain_match.group(1)}mm\n"

        simple_weather += f"\n💡 <em>참고용 과거 데이터이며, 실제 여행일 날씨는 다를 수 있습니다.</em>"

        return simple_weather

    except Exception as e:
        print(f"❌ 과거 날씨 단순화 오류: {e}")
        return historical_weather_text  # 원본 반환