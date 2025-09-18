from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# 데이터베이스 엔진 생성 (연결 풀 최적화)
engine = create_engine(
    settings.DATABASE_URL,
    # 연결 풀 설정
    pool_size=10,           # 기본 연결 풀 크기 (기본값: 5)
    max_overflow=20,        # 최대 추가 연결 수 (기본값: 10)
    pool_pre_ping=True,     # 연결 상태 확인 (끊어진 연결 자동 재연결)
    pool_recycle=3600,      # 1시간마다 연결 재활용 (초단위)
    # 성능 최적화 설정
    echo=False,             # SQL 로그 비활성화 (운영환경)
    future=True             # SQLAlchemy 2.0 스타일 사용
)

# 세션 로컬 클래스
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스
Base = declarative_base()


# 데이터베이스 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
