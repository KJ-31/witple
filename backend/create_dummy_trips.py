"""
단순화된 더미 여행 데이터 생성 스크립트
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Trip, User
from datetime import datetime
import json
import sys
import os

# 데이터베이스 연결 설정
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:witple123!@witple-pub-database.cfme8csmytkv.ap-northeast-2.rds.amazonaws.com:5432/witple_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def create_dummy_trips():
    db = SessionLocal()
    
    try:
        # 기존 여행 데이터 모두 삭제
        db.query(Trip).delete()
        print("기존 여행 데이터를 삭제했습니다.")
        
        # 첫 번째 사용자 찾기 (더미 데이터용)
        user = db.query(User).first()
        if not user:
            print("사용자가 없습니다. 먼저 사용자를 생성해주세요.")
            return
        
        print(f"사용자 {user.email}을 위한 단순화된 더미 여행 데이터를 생성합니다...")
        
        # 더미 여행 1: 서울 시장 여행 (진행 중)
        places1 = [
            {"name": "광장시장", "order": 1, "latitude": "37.5703", "longitude": "126.9998", "address": "서울특별시 종로구 창경궁로 88"},
            {"name": "동대문 디자인 플라자", "order": 2, "latitude": "37.5665", "longitude": "127.0092", "address": "서울특별시 중구 을지로 281"},
            {"name": "남대문시장", "order": 3, "latitude": "37.5597", "longitude": "126.9772", "address": "서울특별시 중구 남대문시장4길 21"}
        ]
        
        trip1 = Trip(
            user_id=user.user_id,
            title="서울 시장 여행",
            places=json.dumps(places1),
            start_date=datetime(2025, 8, 14),
            end_date=datetime(2025, 8, 16),
            status="active",
            total_budget=500000,
            description="전통 시장과 현대적인 쇼핑몰을 함께 즐기는 서울 여행"
        )
        db.add(trip1)
        
        # 더미 여행 2: 부산 시장 여행 (완료됨)
        places2 = [
            {"name": "자갈치시장", "order": 1, "latitude": "35.0966", "longitude": "129.0306", "address": "부산광역시 중구 자갈치해안로 52"},
            {"name": "국제시장", "order": 2, "latitude": "35.1004", "longitude": "129.0251", "address": "부산광역시 중구 신창동4가 12-1"},
            {"name": "해운대 해수욕장", "order": 3, "latitude": "35.1587", "longitude": "129.1603", "address": "부산광역시 해운대구 우동"}
        ]
        
        trip2 = Trip(
            user_id=user.user_id,
            title="부산 시장 여행",
            places=json.dumps(places2),
            start_date=datetime(2024, 7, 2),
            end_date=datetime(2024, 7, 4),
            status="completed",
            total_budget=400000,
            description="부산의 대표 전통시장과 해안 명소를 함께 둘러보는 여행"
        )
        db.add(trip2)
        
        # 더미 여행 3: 제주 시장 여행 (계획됨)
        places3 = [
            {"name": "제주동문시장", "order": 1, "latitude": "33.5145", "longitude": "126.5278", "address": "제주특별자치도 제주시 관덕로14길 20"},
            {"name": "성산일출봉", "order": 2, "latitude": "33.4583", "longitude": "126.9431", "address": "제주특별자치도 서귀포시 성산읍 일출로 284-12"},
            {"name": "한라산 국립공원", "order": 3, "latitude": "33.3617", "longitude": "126.5292", "address": "제주특별자치도 제주시 1100로 2070-61"}
        ]
        
        trip3 = Trip(
            user_id=user.user_id,
            title="제주 시장 여행",
            places=json.dumps(places3),
            start_date=datetime(2025, 12, 14),
            end_date=datetime(2025, 12, 16),
            status="planned",
            total_budget=600000,
            description="제주도 전통시장과 자연 명소를 함께 즐기는 힐링 여행"
        )
        db.add(trip3)
        
        db.commit()
        print("✅ 단순화된 더미 여행 데이터 생성이 완료되었습니다!")
        print(f"- 서울 시장 여행 (진행 중) - 3개 장소")
        print(f"- 부산 시장 여행 (완료됨) - 3개 장소")  
        print(f"- 제주 시장 여행 (계획됨) - 3개 장소")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 오류 발생: {str(e)}")
        
    finally:
        db.close()

if __name__ == "__main__":
    create_dummy_trips()