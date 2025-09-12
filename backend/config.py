from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings(BaseSettings):
    # 데이터베이스 설정
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Redis 설정
    REDIS_URL: str = "redis://localhost:6379"

    # JWT 설정
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7일 (개발용)

    # 환경 설정
    ENVIRONMENT: str = "development"

    # API 설정
    API_V1_STR: str = "/api/v1"

    # AWS S3 설정
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-northeast-2")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "witple-user-uploads")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
