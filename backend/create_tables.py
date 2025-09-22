"""
DB 테이블 생성 스크립트
"""
from database import engine, Base
from models import TravelPlan, User  # 필요한 모델들 import

def create_tables():
    """
    모든 테이블 생성
    """
    try:
        print("🔨 데이터베이스 테이블 생성 시작...")
        Base.metadata.create_all(bind=engine)
        print("✅ 데이터베이스 테이블 생성 완료!")

        # 생성된 테이블 확인
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"📋 생성된 테이블 목록: {tables}")

        if 'travel_plans' in tables:
            print("✅ travel_plans 테이블이 성공적으로 생성되었습니다!")
        else:
            print("⚠️ travel_plans 테이블이 보이지 않습니다.")

    except Exception as e:
        print(f"❌ 테이블 생성 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_tables()