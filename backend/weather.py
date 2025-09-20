"""
날씨 정보 처리 모듈
기상청 API를 사용한 실시간/과거 날씨 데이터 조회 및 처리
"""

import requests
import datetime
import json
import re
import os
from typing import Optional
from sqlalchemy import text
from database import engine as shared_engine

# 기상청 API 키 (환경변수에서 가져오기)
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')

def get_coordinates_for_region(region_name):
    """지역명을 기상청 API용 격자 좌표로 변환 (DB 기반 + 매핑)"""

    # 지역별 대표 좌표 매핑 (기상청 격자 좌표)
    region_coordinates = {
        # === 특별시/광역시/도 대표 좌표 ===
        '서울특별시': {'nx': 60, 'ny': 127},
        '서울': {'nx': 60, 'ny': 127},

        '부산광역시': {'nx': 98, 'ny': 76},
        '부산': {'nx': 98, 'ny': 76},

        '대구광역시': {'nx': 89, 'ny': 90},
        '대구': {'nx': 89, 'ny': 90},

        '인천광역시': {'nx': 55, 'ny': 124},
        '인천': {'nx': 55, 'ny': 124},

        '광주광역시': {'nx': 58, 'ny': 74},
        '광주': {'nx': 58, 'ny': 74},

        '대전광역시': {'nx': 67, 'ny': 100},
        '대전': {'nx': 67, 'ny': 100},

        '울산광역시': {'nx': 102, 'ny': 84},
        '울산': {'nx': 102, 'ny': 84},

        '세종특별자치시': {'nx': 66, 'ny': 103},
        '세종시': {'nx': 66, 'ny': 103},
        '세종': {'nx': 66, 'ny': 103},

        '경기도': {'nx': 60, 'ny': 121},  # 수원 기준
        '강원특별자치도': {'nx': 73, 'ny': 134},  # 춘천 기준
        '강원도': {'nx': 73, 'ny': 134},
        '충청북도': {'nx': 69, 'ny': 106},  # 청주 기준
        '충청남도': {'nx': 63, 'ny': 110},  # 천안 기준
        '전북특별자치도': {'nx': 63, 'ny': 89},  # 전주 기준
        '전라북도': {'nx': 63, 'ny': 89},
        '전라남도': {'nx': 58, 'ny': 74},  # 광주 기준
        '경상북도': {'nx': 89, 'ny': 90},  # 대구 기준
        '경상남도': {'nx': 90, 'ny': 77},  # 창원 기준
        '제주특별자치도': {'nx': 52, 'ny': 38},
        '제주도': {'nx': 52, 'ny': 38},
        '제주': {'nx': 52, 'ny': 38},

        # === 주요 도시 세부 좌표 ===
        # 서울 주요 구
        '강남구': {'nx': 61, 'ny': 126},
        '강남': {'nx': 61, 'ny': 126},
        '종로구': {'nx': 60, 'ny': 127},
        '종로': {'nx': 60, 'ny': 127},
        '마포구': {'nx': 59, 'ny': 126},
        '강북구': {'nx': 60, 'ny': 128},
        '강북': {'nx': 60, 'ny': 128},
        '송파구': {'nx': 62, 'ny': 126},
        '구로구': {'nx': 58, 'ny': 125},

        # 부산 주요 구
        '해운대구': {'nx': 99, 'ny': 75},
        '해운대': {'nx': 99, 'ny': 75},
        '사하구': {'nx': 96, 'ny': 76},
        '사하': {'nx': 96, 'ny': 76},
        '기장군': {'nx': 100, 'ny': 77},

        # 경기도 주요 도시
        '수원시': {'nx': 60, 'ny': 121},
        '수원': {'nx': 60, 'ny': 121},
        '성남시': {'nx': 63, 'ny': 124},
        '성남': {'nx': 63, 'ny': 124},
        '고양시': {'nx': 57, 'ny': 128},
        '고양': {'nx': 57, 'ny': 128},
        '용인시': {'nx': 64, 'ny': 119},
        '용인': {'nx': 64, 'ny': 119},
        '안양시': {'nx': 59, 'ny': 123},
        '안양': {'nx': 59, 'ny': 123},
        '파주시': {'nx': 56, 'ny': 131},
        '파주': {'nx': 56, 'ny': 131},
        '가평군': {'nx': 61, 'ny': 133},
        '가평': {'nx': 61, 'ny': 133},

        # 강원도 주요 도시
        '춘천시': {'nx': 73, 'ny': 134},
        '춘천': {'nx': 73, 'ny': 134},
        '강릉시': {'nx': 92, 'ny': 131},
        '강릉': {'nx': 92, 'ny': 131},
        '평창군': {'nx': 84, 'ny': 123},
        '평창': {'nx': 84, 'ny': 123},

        # 기타 주요 도시
        '경주시': {'nx': 100, 'ny': 91},
        '경주': {'nx': 100, 'ny': 91},
        '전주시': {'nx': 63, 'ny': 89},
        '전주': {'nx': 63, 'ny': 89},
        '여수시': {'nx': 73, 'ny': 66},
        '여수': {'nx': 73, 'ny': 66},
        '창원시': {'nx': 90, 'ny': 77},
        '창원': {'nx': 90, 'ny': 77},
        '제주시': {'nx': 53, 'ny': 38},
        '서귀포시': {'nx': 52, 'ny': 33},
        '서귀포': {'nx': 52, 'ny': 33},

        # 구 이름들 (중복 처리)
        '중구': {'nx': 60, 'ny': 127},  # 서울 기준
        '동구': {'nx': 68, 'ny': 100},  # 대전 기준
        '서구': {'nx': 67, 'ny': 100},  # 대전 기준
        '남구': {'nx': 58, 'ny': 74},   # 광주 기준
        '북구': {'nx': 59, 'ny': 75},   # 광주 기준
    }

    # 정확한 매치 시도
    if region_name in region_coordinates:
        return region_coordinates[region_name]

    # 부분 매치 시도 (지역명이 포함된 경우)
    for key, coords in region_coordinates.items():
        if region_name in key or key in region_name:
            return coords

    # 기본값 (서울)
    return {'nx': 60, 'ny': 127}

def get_db_regions_and_cities():
    """DB에서 실제 region과 city 데이터 추출"""
    try:
        engine = shared_engine
        with engine.connect() as conn:
            # Region 데이터 추출
            regions = []
            result = conn.execute(text("SELECT DISTINCT cmetadata->>'region' as region FROM langchain_pg_embedding WHERE cmetadata->>'region' IS NOT NULL AND cmetadata->>'region' != ''"))
            for row in result:
                if row[0]:  # 빈 문자열 제외
                    regions.append(row[0])

            # City 데이터 추출 (상위 100개)
            cities = []
            result = conn.execute(text("SELECT DISTINCT cmetadata->>'city' as city FROM langchain_pg_embedding WHERE cmetadata->>'city' IS NOT NULL AND cmetadata->>'city' != '' ORDER BY city LIMIT 100"))
            for row in result:
                if row[0]:  # 빈 문자열 제외
                    cities.append(row[0])

            return regions, cities
    except Exception as e:
        print(f"DB 연결 오류: {e}")
        # 기본값 반환
        return ['서울특별시', '부산광역시', '대구광역시'], ['서울', '부산', '대구']

def extract_region_from_query(query):
    """사용자 쿼리에서 지역명 추출 (DB 기반)"""
    # DB에서 실제 region과 city 데이터 가져오기
    db_regions, db_cities = get_db_regions_and_cities()

    # 전체 지역 키워드 = DB regions + DB cities + 추가 별칭
    region_keywords = []

    # DB에서 가져온 region들
    region_keywords.extend(db_regions)

    # DB에서 가져온 city들
    region_keywords.extend(db_cities)

    # 추가 별칭들 (줄임말, 다른 표기)
    aliases = [
        '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
        '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
        '해운대', '강남', '강북', '종로', '명동', '홍대', '이태원', '인사동',
        '광안리', '남포동', '서면', '강릉', '춘천', '원주', '속초', '동해',
        '삼척', '태백', '정선', '평창', '영월', '횡성', '홍천', '화천',
        '양구', '인제', '고성', '양양'
    ]
    region_keywords.extend(aliases)

    # 중복 제거
    region_keywords = list(set(region_keywords))

    # 긴 키워드부터 매칭 (더 구체적인 지역명 우선)
    region_keywords.sort(key=len, reverse=True)

    # 쿼리에서 지역명 찾기
    for region in region_keywords:
        if region in query:
            return region

    return None

def get_weather_info(region_name):
    """기상청 API로 날씨 정보 가져오기"""
    if not WEATHER_API_KEY:
        return "❌ 기상청 API 키가 설정되지 않았습니다. .env 파일에 WEATHER_API_KEY를 추가해주세요."

    try:
        # 지역 좌표 가져오기
        coords = get_coordinates_for_region(region_name)

        # 현재 날짜와 시간
        now = datetime.datetime.now()
        base_date = now.strftime('%Y%m%d')

        # 기상청 발표시간에 맞춰 base_time 설정 (02, 05, 08, 11, 14, 17, 20, 23시)
        hour = now.hour
        if hour < 2:
            base_time = '2300'
            base_date = (now - datetime.timedelta(days=1)).strftime('%Y%m%d')
        elif hour < 5:
            base_time = '0200'
        elif hour < 8:
            base_time = '0500'
        elif hour < 11:
            base_time = '0800'
        elif hour < 14:
            base_time = '1100'
        elif hour < 17:
            base_time = '1400'
        elif hour < 20:
            base_time = '1700'
        elif hour < 23:
            base_time = '2000'
        else:
            base_time = '2300'

        # 기상청 API 요청 URL (HTTP로 시도)
        url = 'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst'

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

        # 재시도 로직과 함께 HTTP 요청
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        }

        # 재시도 로직
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🌤️ 기상청 API 호출 시도 {attempt + 1}/{max_retries}")
                response = requests.get(url, params=params, headers=headers, timeout=30)
                break
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    return f"❌ 기상청 서버 응답 시간 초과 ({region_name})"
                print(f"   ⏰ 타임아웃 발생, {attempt + 2}번째 시도...")
                continue
            except Exception as e:
                if attempt == max_retries - 1:
                    return f"❌ 기상청 API 연결 오류: {e}"
                print(f"   🔄 연결 오류, {attempt + 2}번째 시도...")
                continue

        if response.status_code == 200:
            data = response.json()

            if data['response']['header']['resultCode'] == '00':
                items = data['response']['body']['items']['item']

                # 오늘과 내일 날씨 정보 추출
                weather_info = parse_weather_data(items, region_name)
                return weather_info
            else:
                return f"❌ 기상청 API 오류: {data['response']['header']['resultMsg']}"
        else:
            return f"❌ API 요청 실패: {response.status_code}"

    except Exception as e:
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

            # 오늘 데이터
            if fcst_date == today:
                if fcst_time not in today_data:
                    today_data[fcst_time] = {}
                today_data[fcst_time][category] = fcst_value

            # 내일 데이터
            elif fcst_date == tomorrow:
                if fcst_time not in tomorrow_data:
                    tomorrow_data[fcst_time] = {}
                tomorrow_data[fcst_time][category] = fcst_value

        # 날씨 정보 포맷팅
        weather_text = f"🌤️ <strong>{region_name} 날씨 정보</strong>\n\n"

        # 오늘 날씨 (대표 시간: 12시)
        if '1200' in today_data:
            data = today_data['1200']
            weather_text += "📅 <strong>오늘</strong>\n"
            weather_text += format_weather_detail(data)
            weather_text += "\n"

        # 내일 날씨 (대표 시간: 12시)
        if '1200' in tomorrow_data:
            data = tomorrow_data['1200']
            weather_text += "📅 <strong>내일</strong>\n"
            weather_text += format_weather_detail(data)

        return weather_text

    except Exception as e:
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

        detail = ""

        # 하늘상태
        if 'SKY' in data:
            sky = sky_codes.get(data['SKY'], '정보없음')
            detail += f"• 하늘상태: {sky}\n"

        # 강수형태
        if 'PTY' in data:
            pty = pty_codes.get(data['PTY'], '정보없음')
            if data['PTY'] != '0':
                detail += f"• 강수형태: {pty}\n"

        # 기온
        if 'TMP' in data:
            detail += f"• 기온: {data['TMP']}°C 🌡️\n"

        # 강수확률
        if 'POP' in data:
            detail += f"• 강수확률: {data['POP']}% 💧\n"

        # 습도
        if 'REH' in data:
            detail += f"• 습도: {data['REH']}% 💨\n"

        # 풍속
        if 'WSD' in data:
            detail += f"• 풍속: {data['WSD']}m/s 💨\n"

        return detail

    except Exception as e:
        return f"상세 정보 처리 오류: {e}\n"

def get_smart_weather_info(region_name, travel_date=None):
    """스마트 날씨 조회: 단기예보 우선, 실패 시 과거 데이터 폴백"""
    try:
        # 1. 먼저 단기예보(미래 날씨) 시도 - 현재 시간 기준 3일 이내
        now = datetime.datetime.now()

        # 여행 날짜가 없으면 현재 날짜로 가정
        if not travel_date:
            travel_dt = now
        else:
            try:
                if isinstance(travel_date, str):
                    if len(travel_date) == 8:  # YYYYMMDD
                        travel_dt = datetime.datetime.strptime(travel_date, '%Y%m%d')
                    else:
                        travel_dt = datetime.datetime.strptime(travel_date, '%Y-%m-%d')
                else:
                    travel_dt = travel_date
            except Exception as e:
                print(f"날짜 파싱 오류: {e}")
                travel_dt = now

        days_diff = (travel_dt - now).days
        print(f"📅 여행일: {travel_dt.strftime('%Y-%m-%d')}, 현재로부터 {days_diff}일 후")

        # 단기예보 가능 기간: 오늘~3일 후 (기상청 API 제공 범위)
        if 0 <= days_diff <= 3:
            print(f"🌤️ {region_name} 단기예보 조회 중... ({days_diff}일 후)")
            future_weather = get_weather_info(region_name)
            if not future_weather.startswith("❌"):
                return f"📍 <strong>{region_name} 예상 날씨</strong> (여행일 기준)\n\n{future_weather}"

        # 2. 단기예보 실패 시 과거 동일 기간 날씨로 폴백
        print(f"📅 {region_name} 과거 동일 기간 날씨 조회 중...")

        # 작년 동일 기간 날짜 계산
        now = datetime.datetime.now()
        if travel_date:
            try:
                if isinstance(travel_date, str) and len(travel_date) == 8:
                    travel_dt = datetime.datetime.strptime(travel_date, '%Y%m%d')
                else:
                    travel_dt = now
                # 작년 동일 날짜
                last_year_date = travel_dt.replace(year=travel_dt.year - 1)
            except:
                last_year_date = now.replace(year=now.year - 1)
        else:
            # 여행 날짜 없으면 작년 이맘때
            last_year_date = now.replace(year=now.year - 1)

        historical_date = last_year_date.strftime('%Y%m%d')
        historical_weather = get_historical_weather_info(region_name, historical_date)

        if not historical_weather.startswith("❌"):
            # 과거 날씨에서 평균 기온만 추출
            simplified_weather = simplify_historical_weather(historical_weather, region_name, last_year_date.strftime('%Y-%m-%d'))
            return f"📊 <strong>{region_name} 참고 날씨</strong> (작년 동일 기간)\n\n{simplified_weather}\n\n💡 <em>실제 여행 시 최신 예보를 확인해주세요!</em>"

        # 3. 모든 시도 실패 시 일반적인 계절 정보
        month = now.month if not travel_date else travel_dt.month
        seasonal_info = get_seasonal_weather_info(region_name, month)
        return seasonal_info

    except Exception as e:
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
        10: {"temp": "15~23°C", "desc": "가을 단풍, 쾌적", "clothes": "가디건, 얇은 외투"},
        11: {"temp": "8~18°C", "desc": "쌀쌀한 가을", "clothes": "두꺼운 외투 준비"},
        12: {"temp": "0~8°C", "desc": "추위 시작", "clothes": "코트, 목도리"}
    }

    info = seasonal_data.get(month, seasonal_data[datetime.datetime.now().month])

    return f"""🌡️ <strong>평균 기온</strong>: {info['temp']}
☁️ <strong>날씨 특징</strong>: {info['desc']}
👕 <strong>복장 추천</strong>: {info['clothes']}

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
    historical_keywords = [
        '지난', '작년', '전년', '과거', '예전', '이전', '지난주', '지난달', '지난해',
        '어제', '그때', '당시', '년전', '달전', '주전', '일전',
        '작년 이맘때', '지난번', '그 당시', '몇년전', '몇달전'
    ]

    weather_keywords = [
        '날씨', '기온', '온도', '비', '눈', '바람', '습도', '강수', '기상'
    ]

    query_lower = query.lower()

    # 일반적인 과거 키워드 체크
    has_historical = any(keyword in query_lower for keyword in historical_keywords)
    has_weather = any(keyword in query_lower for keyword in weather_keywords)

    # 구체적인 날짜 패턴 체크 (과거로 간주)
    date_patterns = [
        r'\d{1,2}월\s*\d{1,2}일',  # 10월 4일
        r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',  # 2023년 10월 4일
        r'\d{1,2}/\d{1,2}',  # 10/4
        r'\d{4}/\d{1,2}/\d{1,2}',  # 2023/10/4
        r'\d{1,2}-\d{1,2}',  # 10-4
        r'\d{4}-\d{1,2}-\d{1,2}'  # 2023-10-4
    ]

    # 추가 날짜 패턴들 (년도 포함)
    additional_patterns = [
        r'20\d{2}년',  # 2023년, 2022년 등
        r'20\d{2}[.-/]\d{1,2}[.-/]\d{1,2}',  # 2023-10-15, 2023.10.15 등
        r'20\d{2}년\s*\d{1,2}월',  # 2023년 10월
    ]

    date_patterns.extend(additional_patterns)
    has_specific_date = any(re.search(pattern, query_lower) for pattern in date_patterns)

    return (has_historical or has_specific_date) and has_weather

def get_historical_weather_info(region_name, date_str):
    """기상청 API로 과거 날씨 정보 가져오기 (지상관측 일자료)"""
    if not WEATHER_API_KEY:
        return "❌ 기상청 API 키가 설정되지 않았습니다."

    try:
        # 지역에 해당하는 관측소 ID 찾기
        station_id = get_station_id_for_region(region_name)
        if not station_id:
            return f"❌ {region_name}에 해당하는 기상 관측소를 찾을 수 없습니다."

        # 날짜 형식 변환 (YYYYMMDD)
        try:
            if isinstance(date_str, str):
                if len(date_str) == 8:
                    target_date = date_str
                elif len(date_str) == 10:  # YYYY-MM-DD
                    target_date = date_str.replace('-', '')
                else:
                    return f"❌ 잘못된 날짜 형식: {date_str}"
            else:
                return f"❌ 날짜는 문자열이어야 합니다: {date_str}"
        except Exception as e:
            return f"❌ 날짜 처리 오류: {e}"

        # 기상청 지상관측 일자료 API URL
        url = 'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'

        params = {
            'serviceKey': WEATHER_API_KEY,
            'pageNo': '1',
            'numOfRows': '10',
            'dataType': 'JSON',
            'dataCd': 'ASOS',
            'dateCd': 'DAY',
            'startDt': target_date,
            'endDt': target_date,
            'stnIds': station_id
        }

        # API 요청
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, params=params, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if data['response']['header']['resultCode'] == '00':
                items = data['response']['body']['items']

                if items and len(items) > 0:
                    weather_data = items[0]
                    return format_historical_weather_data(weather_data, region_name, date_str)
                else:
                    return f"❌ {region_name}의 {date_str} 날씨 기록을 찾을 수 없습니다."
            else:
                return f"❌ 기상청 API 오류: {data['response']['header']['resultMsg']}"
        else:
            return f"❌ API 요청 실패: {response.status_code}"

    except Exception as e:
        return f"❌ 과거 날씨 조회 오류: {e}"

def get_station_id_for_region(region_name):
    """지역에 해당하는 기상 관측소 ID 조회"""
    station_mapping = {
        "서울": "108",
        "부산": "159",
        "대구": "143",
        "인천": "112",
        "광주": "156",
        "대전": "133",
        "울산": "152",
        "제주": "184",
        "강릉": "105",
        "전주": "146",
        "청주": "131",
        "춘천": "101",
        "포항": "138",
        "여수": "168",
        "목포": "165",
        "안동": "136",
        "창원": "155",
        "수원": "119",
        "강화": "201",
        "서산": "129"
    }

    # 정확한 매치
    if region_name in station_mapping:
        return station_mapping[region_name]

    # 부분 매치 시도
    for region, station_id in station_mapping.items():
        if region in region_name or region_name in region:
            return station_id

    # 기본값 (서울)
    return "108"

def format_historical_weather_data(data, region_name, date_str):
    """과거 날씨 데이터 포맷팅"""
    try:
        if not data:
            return f"{region_name}의 {date_str} 날씨 기록을 찾을 수 없습니다."

        # 날짜 포맷팅
        formatted_date = date_str
        if len(date_str) == 8:
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        weather_text = f"📅 **{region_name} {formatted_date} 과거 날씨**\n\n"

        # 최고기온
        if 'maxTa' in data and data['maxTa']:
            weather_text += f"🌡️ 최고기온: {data['maxTa']}°C\n"

        # 최저기온
        if 'minTa' in data and data['minTa']:
            weather_text += f"🌡️ 최저기온: {data['minTa']}°C\n"

        # 평균기온
        if 'avgTa' in data and data['avgTa']:
            weather_text += f"🌡️ 평균기온: {data['avgTa']}°C\n"

        # 강수량
        if 'sumRn' in data and data['sumRn']:
            if float(data['sumRn']) > 0:
                weather_text += f"💧 강수량: {data['sumRn']}mm\n"
            else:
                weather_text += "💧 강수량: 없음\n"

        # 평균 풍속
        if 'avgWs' in data and data['avgWs']:
            weather_text += f"💨 평균 풍속: {data['avgWs']}m/s\n"

        # 평균 습도
        if 'avgRhm' in data and data['avgRhm']:
            weather_text += f"💧 평균 습도: {data['avgRhm']}%\n"

        return weather_text

    except Exception as e:
        return f"과거 날씨 데이터 포맷팅 오류: {e}"

def simplify_historical_weather(historical_weather_text, region_name, date_str):
    """과거 날씨 정보 요약"""
    try:
        if not historical_weather_text:
            return f"{region_name}의 {date_str} 날씨 요약 정보가 없습니다."

        # 긴 텍스트를 요약하는 로직
        summary = historical_weather_text[:200] + "..." if len(historical_weather_text) > 200 else historical_weather_text
        return f"**{region_name} {date_str} 날씨 요약**\n{summary}"

    except Exception as e:
        return f"날씨 정보 요약 오류: {e}"

def extract_date_from_query(query):
    """쿼리에서 날짜 정보 추출"""
    try:
        # 날짜 패턴 매칭
        date_patterns = [
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\d{1,2})월\s*(\d{1,2})일',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, query)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    year, month, day = groups
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                elif len(groups) == 2:
                    current_year = datetime.datetime.now().year
                    month, day = groups
                    return f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"

        return None

    except Exception as e:
        print(f"날짜 추출 오류: {e}")
        return None