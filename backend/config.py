from pydantic_settings import BaseSettings
from typing import Optional
import configparser
import os


def get_database_url_from_config():
    """DB.conf 파일에서 데이터베이스 URL을 생성합니다."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'DB.conf')
    
    if os.path.exists(config_path):
        config = configparser.ConfigParser()
        config.read(config_path)
        
        if 'postgres_config' in config:
            pg_config = config['postgres_config']
            host = pg_config.get('host')
            port = pg_config.get('port')
            username = pg_config.get('username')
            password = pg_config.get('password')
            database = pg_config.get('database')
            
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    # 기본값
    return "postgresql://witple_user:witple_password@localhost:5432/witple_db"


class Settings(BaseSettings):
    # 데이터베이스 설정
    DATABASE_URL: str = get_database_url_from_config()
    
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
    
    # AWS S3 설정
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = "user-posts"
    
    class Config:
        env_file = ".env"


settings = Settings()
