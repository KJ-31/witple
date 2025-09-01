from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 데이터베이스 설정
    DATABASE_URL: str = "postgresql://witple_user:witple_password@localhost:5432/witple_db"
    
    # Redis 설정
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT 설정
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 환경 설정
    ENVIRONMENT: str = "development"
    
    # API 설정
    API_V1_STR: str = "/api/v1"
    
    class Config:
        env_file = ".env"


settings = Settings()
