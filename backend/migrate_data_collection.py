#!/usr/bin/env python3
"""
데이터 수집 시스템을 위한 데이터베이스 마이그레이션 스크립트
UserAction, UserBehaviorVector, PlaceVector 테이블 추가
"""
import psycopg2
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_data_collection_tables():
    """데이터 수집 관련 테이블들을 추가"""
    try:
        # 데이터베이스 연결
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        
        logger.info("Connected to database for data collection migration")
        
        # 1. user_actions 테이블 생성
        logger.info("Creating user_actions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_actions (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(user_id),
                place_category VARCHAR NOT NULL,
                place_id VARCHAR NOT NULL,
                action_type VARCHAR NOT NULL,
                action_value INTEGER,
                action_detail JSONB,
                session_id VARCHAR,
                
                -- 서버 메타데이터
                server_timestamp TIMESTAMP WITH TIME ZONE,
                client_ip VARCHAR,
                user_agent TEXT,
                request_id VARCHAR,
                
                -- AWS Batch 처리 상태
                batch_processed BOOLEAN DEFAULT FALSE,
                batch_processed_at TIMESTAMP WITH TIME ZONE,
                batch_id VARCHAR,
                
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✓ user_actions table created")
        
        # 2. user_behavior_vectors 테이블 생성  
        logger.info("Creating user_behavior_vectors table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_behavior_vectors (
                user_id VARCHAR PRIMARY KEY REFERENCES users(user_id),
                
                -- BERT 벡터 (384차원) - PostgreSQL ARRAY 타입
                behavior_vector FLOAT[],
                
                -- 행동 점수들 (0.0~100.0)
                like_score FLOAT DEFAULT 0.0,
                bookmark_score FLOAT DEFAULT 0.0,
                click_score FLOAT DEFAULT 0.0,
                dwell_time_score FLOAT DEFAULT 0.0,
                
                -- 통계 메타데이터
                total_actions INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_bookmarks INTEGER DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                
                -- 최신성 정보
                last_action_date TIMESTAMP WITH TIME ZONE,
                vector_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✓ user_behavior_vectors table created")
        
        # 3. place_vectors 테이블 생성
        logger.info("Creating place_vectors table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS place_vectors (
                id SERIAL PRIMARY KEY,
                place_id VARCHAR NOT NULL,
                place_category VARCHAR NOT NULL,
                
                -- 장소 특성 벡터들
                content_vector FLOAT[],
                behavior_vector FLOAT[],
                combined_vector FLOAT[],
                
                -- 장소별 통계 정보
                total_likes INTEGER DEFAULT 0,
                total_bookmarks INTEGER DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                avg_dwell_time FLOAT DEFAULT 0.0,
                
                -- 인기도 점수 (0.0~100.0)
                popularity_score FLOAT DEFAULT 0.0,
                engagement_score FLOAT DEFAULT 0.0,
                
                -- 벡터 업데이트 정보
                vector_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                stats_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✓ place_vectors table created")
        
        # 4. user_actions 테이블 인덱스 생성
        logger.info("Creating user_actions indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_place_category ON user_actions(place_category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_place_id ON user_actions(place_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_action_type ON user_actions(action_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_session_id ON user_actions(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_batch_processed ON user_actions(batch_processed);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_created_at ON user_actions(created_at);")
        logger.info("✓ user_actions indexes created")
        
        # 5. place_vectors 테이블 인덱스 생성
        logger.info("Creating place_vectors indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_place_vectors_place_id ON place_vectors(place_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_place_vectors_place_category ON place_vectors(place_category);")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_place_vectors_place_unique ON place_vectors(place_id, place_category);")
        logger.info("✓ place_vectors indexes created")
        
        # 6. 복합 인덱스 생성 (쿼리 성능 최적화)
        logger.info("Creating composite indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_composite ON user_actions(user_id, place_category, action_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_batch_processing ON user_actions(batch_processed, created_at) WHERE batch_processed = FALSE;")
        logger.info("✓ Composite indexes created")
        
        # 커밋
        conn.commit()
        logger.info("✓ Data collection tables migration completed successfully!")
        
        # 테이블 정보 확인
        logger.info("Verifying created tables...")
        cursor.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('user_actions', 'user_behavior_vectors', 'place_vectors')
            ORDER BY table_name, ordinal_position;
        """)
        
        results = cursor.fetchall()
        current_table = None
        for table_name, column_name, data_type in results:
            if current_table != table_name:
                logger.info(f"\n📋 Table: {table_name}")
                current_table = table_name
            logger.info(f"   └─ {column_name}: {data_type}")
        
        # 인덱스 정보 확인
        logger.info("\nVerifying created indexes...")
        cursor.execute("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE tablename IN ('user_actions', 'user_behavior_vectors', 'place_vectors')
            ORDER BY tablename, indexname;
        """)
        
        indexes = cursor.fetchall()
        current_table = None
        for table_name, index_name in indexes:
            if current_table != table_name:
                logger.info(f"\n🗂️  Indexes for {table_name}:")
                current_table = table_name
            logger.info(f"   └─ {index_name}")
        
    except Exception as e:
        logger.error(f"Data collection migration failed: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def rollback_data_collection_tables():
    """데이터 수집 테이블들을 롤백 (개발용)"""
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        
        logger.info("Rolling back data collection tables...")
        
        # 순서대로 테이블 삭제 (외래 키 제약 고려)
        cursor.execute("DROP TABLE IF EXISTS place_vectors CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS user_behavior_vectors CASCADE;") 
        cursor.execute("DROP TABLE IF EXISTS user_actions CASCADE;")
        
        conn.commit()
        logger.info("✓ Data collection tables rolled back successfully!")
        
    except Exception as e:
        logger.error(f"Rollback failed: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_data_collection_tables()
    else:
        migrate_data_collection_tables()