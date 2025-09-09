"""
S3에서 PostgreSQL로 배치 처리 파이프라인
EC2 Collection Server가 S3에 저장한 JSON 데이터를 PostgreSQL로 이관
"""

import asyncio
import asyncpg
import boto3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
import uuid

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class S3ToDBPipeline:
    def __init__(self):
        # AWS S3 설정
        self.s3_client = boto3.client(
            's3',
            region_name='ap-northeast-2',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        # S3 버킷 설정 (EC2 Collection Server가 사용하는 버킷)
        self.source_bucket = 'user-actions-data'
        
        # PostgreSQL 연결 설정
        self.database_url = os.getenv('DATABASE_URL')
        
    async def get_db_connection(self):
        """PostgreSQL 연결"""
        return await asyncpg.connect(self.database_url)
        
    def list_s3_files(self, hours_back: int = 1) -> List[Dict]:
        """지정된 시간 이후의 S3 파일들을 조회"""
        try:
            # 현재 시간에서 hours_back 시간 전까지의 파일들을 가져옴
            now = datetime.now()
            start_time = now - timedelta(hours=hours_back)
            
            # S3 객체 목록 조회
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.source_bucket,
                Prefix='user-actions/'
            )
            
            files = []
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # 파일 수정 시간이 지정된 시간 범위 내인지 확인
                        if obj['LastModified'].replace(tzinfo=None) >= start_time:
                            files.append({
                                'key': obj['Key'],
                                'size': obj['Size'],
                                'last_modified': obj['LastModified']
                            })
            
            logger.info(f"Found {len(files)} files in S3 from last {hours_back} hours")
            return files
            
        except Exception as e:
            logger.error(f"Error listing S3 files: {e}")
            return []
    
    def download_s3_file(self, key: str) -> Dict[str, Any]:
        """S3에서 JSON 파일을 다운로드하고 파싱"""
        try:
            response = self.s3_client.get_object(Bucket=self.source_bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            
            # JSON 파싱
            data = json.loads(content)
            logger.debug(f"Downloaded and parsed: {key}")
            return data
            
        except Exception as e:
            logger.error(f"Error downloading {key}: {e}")
            return None
    
    async def insert_action_to_db(self, conn: asyncpg.Connection, action_data: Dict[str, Any]) -> bool:
        """개별 액션을 PostgreSQL에 삽입"""
        try:
            # 필수 필드 검증
            required_fields = ['user_id', 'place_category', 'place_id', 'action_type']
            for field in required_fields:
                if field not in action_data:
                    logger.warning(f"Missing required field {field} in action data")
                    return False
            
            # UUID 생성 (S3에서 collection_id가 있으면 사용, 없으면 새로 생성)
            action_id = action_data.get('collection_id', str(uuid.uuid4()))
            
            # PostgreSQL에 삽입
            await conn.execute("""
                INSERT INTO user_action_logs 
                (id, user_id, place_category, place_id, action_type, action_value, action_detail, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (id) DO NOTHING
            """,
            action_id,
            action_data['user_id'],
            action_data['place_category'],
            action_data['place_id'],
            action_data['action_type'],
            action_data.get('action_value'),
            action_data.get('action_detail'),
            # timestamp가 있으면 사용, 없으면 현재 시간
            datetime.fromisoformat(action_data.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00'))
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error inserting action to DB: {e}")
            logger.error(f"Action data: {action_data}")
            return False
    
    async def process_batch(self, hours_back: int = 1) -> Dict[str, int]:
        """S3에서 PostgreSQL로 배치 처리"""
        stats = {
            'files_processed': 0,
            'actions_processed': 0,
            'actions_inserted': 0,
            'errors': 0
        }
        
        try:
            # S3 파일 목록 조회
            files = self.list_s3_files(hours_back)
            if not files:
                logger.info("No files to process")
                return stats
            
            # PostgreSQL 연결
            conn = await self.get_db_connection()
            
            try:
                for file_info in files:
                    try:
                        # S3에서 파일 다운로드
                        action_data = self.download_s3_file(file_info['key'])
                        if not action_data:
                            stats['errors'] += 1
                            continue
                        
                        # 단일 액션 처리
                        stats['actions_processed'] += 1
                        success = await self.insert_action_to_db(conn, action_data)
                        
                        if success:
                            stats['actions_inserted'] += 1
                        else:
                            stats['errors'] += 1
                        
                        stats['files_processed'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing file {file_info['key']}: {e}")
                        stats['errors'] += 1
                        
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            stats['errors'] += 1
        
        logger.info(f"Batch processing completed: {stats}")
        return stats
    
    async def process_and_calculate_recommendations(self, hours_back: int = 1):
        """배치 처리 후 추천 알고리즘 실행"""
        
        # 1. S3 → PostgreSQL 배치 처리
        logger.info("🔄 Starting S3 to PostgreSQL batch processing...")
        batch_stats = await self.process_batch(hours_back)
        
        if batch_stats['actions_inserted'] == 0:
            logger.info("No new actions to process recommendations")
            return
        
        # 2. 추천 알고리즘 계산
        logger.info("🧮 Starting recommendation algorithm calculation...")
        await self.calculate_user_recommendations()
        
        logger.info("✅ Pipeline completed successfully")
    
    async def get_dynamic_weight(self, conn: asyncpg.Connection, action_type: str, action_value: float) -> float:
        """action_value에 따라 동적 가중치 계산"""
        try:
            if action_type == 'dwell_time':
                if action_value < 5:
                    value_range = '0-5s'
                elif action_value <= 20:
                    value_range = '5-20s'
                else:
                    value_range = '20s+'
            elif action_type == 'scroll_depth':
                if action_value < 30:
                    value_range = '0-30%'
                elif action_value <= 70:
                    value_range = '30-70%'
                else:
                    value_range = '70-100%'
            else:
                # click, search, like, bookmark는 value_range가 NULL
                value_range = None
            
            # DB에서 가중치 조회
            weight_query = """
                SELECT weight FROM action_weights 
                WHERE action_type = $1 AND (value_range = $2 OR (value_range IS NULL AND $2 IS NULL))
            """
            
            result = await conn.fetchval(weight_query, action_type, value_range)
            return float(result) if result else 1.0
            
        except Exception as e:
            logger.error(f"Error getting dynamic weight: {e}")
            return 1.0

    async def calculate_user_recommendations(self):
        """사용자 행동 데이터를 기반으로 정교한 추천 점수 계산"""
        try:
            conn = await self.get_db_connection()
            
            try:
                # 최근 7일간의 사용자 행동 분석 (개별 action_value 포함)
                analysis_query = """
                SELECT 
                    user_id,
                    place_category,
                    action_type,
                    action_value,
                    COUNT(*) as action_count
                FROM user_action_logs 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY user_id, place_category, action_type, action_value
                ORDER BY user_id, place_category, action_type
                """
                
                results = await conn.fetch(analysis_query)
                
                # 사용자별 선호도 점수 계산
                user_preferences = {}
                
                for row in results:
                    user_id = row['user_id']
                    category = row['place_category']
                    action_type = row['action_type']
                    action_value = float(row['action_value']) if row['action_value'] else 1.0
                    count = row['action_count']
                    
                    if user_id not in user_preferences:
                        user_preferences[user_id] = {}
                    
                    if category not in user_preferences[user_id]:
                        user_preferences[user_id][category] = 0
                    
                    # 동적 가중치 계산
                    weight = await self.get_dynamic_weight(conn, action_type, action_value)
                    
                    # 점수 계산: 행동 횟수 × 동적 가중치
                    score = count * weight
                    
                    user_preferences[user_id][category] += score
                    
                    logger.debug(f"User {user_id[:8]}, {category}, {action_type}, value={action_value}, weight={weight}, score={score}")
                
                logger.info(f"Calculated preferences for {len(user_preferences)} users")
                
                # 사용자별 상위 선호도 출력
                for user_id, preferences in user_preferences.items():
                    sorted_prefs = sorted(preferences.items(), key=lambda x: x[1], reverse=True)
                    logger.info(f"User {user_id[:8]}... preferences: {sorted_prefs[:3]}")
                
                # 추천 결과를 user_category_preferences 테이블에 저장
                await self.save_user_preferences(conn, user_preferences)
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Error calculating recommendations: {e}")
    
    async def save_user_preferences(self, conn: asyncpg.Connection, user_preferences: dict):
        """계산된 사용자 선호도를 DB에 저장"""
        try:
            # user_category_preferences 테이블이 없으면 생성
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_category_preferences (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    place_category VARCHAR(50) NOT NULL,
                    preference_score NUMERIC(10,2) NOT NULL DEFAULT 0,
                    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id, place_category)
                )
            """)
            
            # 인덱스 생성
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_category_preferences_user_score 
                ON user_category_preferences(user_id, preference_score DESC)
            """)
            
            # 기존 데이터 삭제 후 새 데이터 삽입
            for user_id, preferences in user_preferences.items():
                # 해당 사용자의 기존 선호도 삭제
                await conn.execute("DELETE FROM user_category_preferences WHERE user_id = $1", user_id)
                
                # 새 선호도 삽입
                for category, score in preferences.items():
                    await conn.execute("""
                        INSERT INTO user_category_preferences 
                        (user_id, place_category, preference_score, last_updated) 
                        VALUES ($1, $2, $3, NOW())
                    """, user_id, category, round(score, 2))
            
            logger.info(f"Saved preferences for {len(user_preferences)} users to database")
            
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")

# CLI 인터페이스
async def main():
    """메인 실행 함수"""
    import sys
    
    pipeline = S3ToDBPipeline()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        
        if command == 'batch':
            # 배치 처리만 실행
            await pipeline.process_batch(hours)
        elif command == 'recommend':
            # 추천 계산만 실행  
            await pipeline.calculate_user_recommendations()
        elif command == 'full':
            # 전체 파이프라인 실행
            await pipeline.process_and_calculate_recommendations(hours)
        else:
            print("Usage: python s3_to_db_pipeline.py [batch|recommend|full] [hours_back]")
    else:
        # 기본: 전체 파이프라인 실행
        await pipeline.process_and_calculate_recommendations()

if __name__ == "__main__":
    asyncio.run(main())