#!/usr/bin/env python3
"""
OAuth 지원을 위한 데이터베이스 마이그레이션 스크립트
"""
import psycopg2
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """데이터베이스 스키마를 OAuth 지원으로 업데이트"""
    try:
        # 데이터베이스 연결
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        
        logger.info("Connected to database")
        
        # 1. users 테이블의 pw 컬럼을 NULL 허용으로 변경
        logger.info("Updating users table pw column to allow NULL...")
        cursor.execute("ALTER TABLE users ALTER COLUMN pw DROP NOT NULL;")
        logger.info("✓ users.pw column updated to allow NULL")
        
        # 2. oauth_accounts 테이블 생성
        logger.info("Creating oauth_accounts table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_accounts (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(user_id),
                provider VARCHAR NOT NULL,
                provider_user_id VARCHAR NOT NULL,
                email VARCHAR,
                name VARCHAR,
                profile_picture VARCHAR,
                access_token TEXT,
                refresh_token TEXT,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, provider_user_id)
            );
        """)
        logger.info("✓ oauth_accounts table created")
        
        # 3. 인덱스 생성
        logger.info("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id ON oauth_accounts(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_oauth_accounts_provider ON oauth_accounts(provider, provider_user_id);")
        logger.info("✓ Indexes created")
        
        # 커밋
        conn.commit()
        logger.info("✓ Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database()