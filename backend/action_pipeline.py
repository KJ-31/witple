"""
사용자 행동 데이터 파이프라인
Frontend → Backend → DB → Collection Server → S3 → 이미지 벡터화 → 추천 시스템
"""

import asyncio
import json
import boto3
import asyncpg
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import uuid
import os
from dotenv import load_dotenv
import numpy as np

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ActionDataPipeline:
    """사용자 행동 데이터 처리 파이프라인"""
    
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.s3_bucket = os.getenv("S3_BUCKET_NAME", "user-actions-data")
        self.s3_client = boto3.client('s3')
        
        # 이미지 벡터화 모델
        self.setup_image_models()
        
    def setup_image_models(self):
        """CLIP 이미지 벡터화 모델 초기화"""
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            
            self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.clip_model.to(self.device)
            
            logger.info(f"CLIP model initialized on {self.device}")
        except Exception as e:
            logger.warning(f"CLIP model initialization failed: {e}")
            self.clip_model = None

    # 1단계: 실시간 행동 로깅 (Frontend → Backend → DB)
    async def log_user_action(self, action_data: Dict) -> str:
        """사용자 행동 실시간 DB 저장"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            action_id = str(uuid.uuid4())
            
            await conn.execute("""
                INSERT INTO user_action_logs
                (id, user_id, place_category, place_id, action_type, action_value, action_detail, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            action_id,
            action_data['user_id'],
            action_data['place_category'], 
            action_data['place_id'],
            action_data['action_type'],
            action_data.get('action_value'),
            action_data.get('action_detail'),
            datetime.utcnow()
            )
            
            logger.info(f"Action logged: {action_id}")
            return action_id
            
        finally:
            await conn.close()
    
    # 2단계: DB → S3 배치 전송 (Collection Server 역할)
    async def export_actions_to_s3(self, hours_back: int = 1):
        """DB에서 S3로 배치 전송"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # 최근 N시간의 데이터 조회
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            actions = await conn.fetch("""
                SELECT 
                    id::text as id,
                    user_id,
                    place_category,
                    place_id::text as place_id,
                    action_type::text as action_type,
                    action_value,
                    action_detail,
                    created_at
                FROM user_action_logs
                WHERE created_at >= $1
                ORDER BY created_at
            """, cutoff_time)
            
            if not actions:
                logger.info("No actions to export")
                return
            
            # JSON 배치 생성
            batch_data = {
                "export_info": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "count": len(actions),
                    "time_range": {
                        "from": cutoff_time.isoformat() + "Z",
                        "to": datetime.utcnow().isoformat() + "Z"
                    }
                },
                "actions": []
            }
            
            for action in actions:
                action_json = {
                    "id": action['id'],
                    "user_id": action['user_id'],
                    "place_category": action['place_category'],
                    "place_id": action['place_id'],
                    "action_type": action['action_type'],
                    "action_value": float(action['action_value']) if action['action_value'] else None,
                    "action_detail": action['action_detail'],
                    "created_at": action['created_at'].isoformat() + "Z"
                }
                batch_data["actions"].append(action_json)
            
            # S3 키 생성 (파티셔닝)
            now = datetime.utcnow()
            s3_key = f"user_actions/year={now.year}/month={now.month:02d}/day={now.day:02d}/hour={now.hour:02d}/{now.strftime('%Y%m%d_%H%M%S')}_{len(actions)}_actions.json"
            
            # S3 업로드
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=json.dumps(batch_data, indent=2, ensure_ascii=False),
                ContentType='application/json',
                Metadata={
                    'action_count': str(len(actions)),
                    'export_timestamp': now.isoformat()
                }
            )
            
            logger.info(f"Exported {len(actions)} actions to s3://{self.s3_bucket}/{s3_key}")
            
        finally:
            await conn.close()
    
    # 3단계: S3 → DB 재처리 (분석용)
    async def import_actions_from_s3(self, s3_key: str):
        """S3에서 액션 데이터를 읽어서 분석 테이블에 저장"""
        try:
            # S3에서 JSON 파일 읽기
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            conn = await asyncpg.connect(self.db_url)
            
            try:
                processed_count = 0
                
                for action in data['actions']:
                    # 이미지 관련 액션이면 이미지 벡터 처리
                    if action['action_type'] in ['bookmark', 'like']:
                        await self.process_action_for_image_vectors(action)
                        processed_count += 1
                
                logger.info(f"Processed {processed_count} image-related actions from {s3_key}")
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Error importing from S3: {e}")
    
    # 4단계: 이미지 벡터 처리
    async def process_action_for_image_vectors(self, action_data: Dict):
        """액션 데이터로부터 이미지 벡터 처리"""
        
        if not self.clip_model:
            return
            
        conn = await asyncpg.connect(self.db_url)
        
        try:
            user_id = action_data['user_id']
            place_id = action_data['place_id']
            place_category = action_data['place_category']
            action_type = action_data['action_type']
            
            # 1. 해당 장소의 이미지 벡터가 있는지 확인
            existing_vector = await conn.fetchval("""
                SELECT image_vector FROM place_image_vectors 
                WHERE place_id = $1 AND place_category = $2
                LIMIT 1
            """, place_id, place_category)
            
            if not existing_vector:
                # 이미지 벡터가 없으면 생성
                await self.create_place_image_vector(place_id, place_category)
                
                existing_vector = await conn.fetchval("""
                    SELECT image_vector FROM place_image_vectors 
                    WHERE place_id = $1 AND place_category = $2
                    LIMIT 1
                """, place_id, place_category)
            
            if existing_vector:
                # 2. 사용자 이미지 선호도 업데이트
                await self.update_user_image_preference(
                    user_id,
                    np.array(json.loads(existing_vector)),
                    action_type
                )
                
        finally:
            await conn.close()
    
    async def create_place_image_vector(self, place_id: str, place_category: str):
        """장소 이미지 벡터 생성"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # 해당 장소의 이미지 URL들 조회
            image_data = await conn.fetchval(f"""
                SELECT image_urls FROM {place_category} WHERE id = $1
            """, place_id)
            
            if image_data:
                if isinstance(image_data, str):
                    image_urls = json.loads(image_data)
                else:
                    image_urls = image_data
                
                # 첫 번째 이미지만 벡터화
                if image_urls and len(image_urls) > 0:
                    vector = await self.vectorize_image(image_urls[0])
                    
                    if np.any(vector):
                        await conn.execute("""
                            INSERT INTO place_image_vectors 
                            (place_id, place_category, image_vector, image_url)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (place_id, place_category, image_url) DO NOTHING
                        """, place_id, place_category, str(vector.tolist()), image_urls[0])
                        
                        logger.info(f"Created image vector for place {place_id}")
                        
        except Exception as e:
            logger.error(f"Error creating place image vector: {e}")
        finally:
            await conn.close()
    
    async def vectorize_image(self, image_url: str) -> np.ndarray:
        """이미지 URL을 384차원 벡터로 변환"""
        if not self.clip_model:
            return np.zeros(384)
            
        try:
            import requests
            from PIL import Image
            import io
            import torch
            
            # 이미지 다운로드
            response = requests.get(image_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            image = Image.open(io.BytesIO(response.content)).convert('RGB')
            
            # CLIP으로 벡터화
            inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                image_features = self.clip_model.get_image_features(**inputs)
            
            # 512차원을 384차원으로 축소
            vector_512 = image_features.cpu().numpy().flatten()
            vector_384 = vector_512[:384]
            
            return vector_384
            
        except Exception as e:
            logger.error(f"Image vectorization failed for {image_url}: {e}")
            return np.zeros(384)
    
    async def update_user_image_preference(self, user_id: str, image_vector: np.ndarray, action_type: str):
        """사용자 이미지 선호도 벡터 업데이트"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # 액션별 가중치
            action_weights = {
                'bookmark': 0.8,
                'like': 0.6,
                'click': 0.3
            }
            weight = action_weights.get(action_type, 0.5)
            
            # 기존 선호도 벡터 조회
            current_pref = await conn.fetchrow("""
                SELECT preference_vector, action_count FROM user_image_preferences 
                WHERE user_id = $1
            """, user_id)
            
            if current_pref:
                # 점진적 업데이트
                current_vector = np.array(json.loads(current_pref['preference_vector']))
                current_count = current_pref['action_count']
                
                # 가중 평균 업데이트
                learning_rate = min(0.1, weight / 5.0)
                updated_vector = (1 - learning_rate) * current_vector + learning_rate * image_vector
                new_count = current_count + 1
                
                await conn.execute("""
                    UPDATE user_image_preferences 
                    SET preference_vector = $1, action_count = $2, last_updated = now()
                    WHERE user_id = $3
                """, str(updated_vector.tolist()), new_count, user_id)
                
            else:
                # 첫 번째 선호도 생성
                initial_vector = weight * image_vector
                
                await conn.execute("""
                    INSERT INTO user_image_preferences (user_id, preference_vector, action_count)
                    VALUES ($1, $2, 1)
                """, user_id, str(initial_vector.tolist()))
            
            logger.info(f"Updated image preference for user {user_id}")
            
        finally:
            await conn.close()
    
    # 5단계: 배치 프로세싱 스케줄러
    async def run_hourly_pipeline(self):
        """시간별 파이프라인 실행"""
        logger.info("Starting hourly pipeline...")
        
        try:
            # 1. DB → S3 내보내기
            await self.export_actions_to_s3(hours_back=1)
            
            # 2. 최근 1시간의 이미지 관련 액션 처리
            await self.process_recent_image_actions(hours_back=1)
            
            logger.info("Hourly pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"Hourly pipeline failed: {e}")
    
    async def process_recent_image_actions(self, hours_back: int = 1):
        """최근 이미지 관련 액션들을 배치 처리"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            # 이미지 관련 액션만 조회
            actions = await conn.fetch("""
                SELECT user_id, place_category, place_id::text as place_id, action_type::text as action_type
                FROM user_action_logs
                WHERE created_at >= $1 
                  AND action_type IN ('bookmark', 'like', 'click')
                ORDER BY created_at
            """, cutoff_time)
            
            processed = 0
            for action in actions:
                action_dict = dict(action)
                await self.process_action_for_image_vectors(action_dict)
                processed += 1
                
                if processed % 10 == 0:
                    logger.info(f"Processed {processed}/{len(actions)} actions")
            
            logger.info(f"Batch processed {processed} image actions")
            
        finally:
            await conn.close()
    
    # 6단계: S3 데이터 분석 유틸리티
    def list_s3_action_files(self, date_prefix: str = None) -> List[str]:
        """S3의 액션 파일 목록 조회"""
        if date_prefix:
            prefix = f"user_actions/{date_prefix}"
        else:
            prefix = "user_actions/"
        
        response = self.s3_client.list_objects_v2(
            Bucket=self.s3_bucket,
            Prefix=prefix
        )
        
        return [obj['Key'] for obj in response.get('Contents', [])]
    
    async def analyze_s3_actions(self, s3_key: str) -> Dict:
        """S3 액션 파일 분석"""
        try:
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            # 기본 통계
            actions = data['actions']
            stats = {
                'total_actions': len(actions),
                'unique_users': len(set(a['user_id'] for a in actions)),
                'action_types': {},
                'place_categories': {},
                'time_range': data['export_info']['time_range']
            }
            
            # 액션 타입별 통계
            for action in actions:
                action_type = action['action_type']
                place_category = action['place_category']
                
                stats['action_types'][action_type] = stats['action_types'].get(action_type, 0) + 1
                stats['place_categories'][place_category] = stats['place_categories'].get(place_category, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error analyzing S3 file: {e}")
            return {}

# 실행 함수들
async def run_pipeline_once():
    """파이프라인 1회 실행"""
    pipeline = ActionDataPipeline()
    await pipeline.run_hourly_pipeline()

async def process_historical_data():
    """S3에 있는 기존 데이터 재처리"""
    pipeline = ActionDataPipeline()
    
    # 최근 파일들 조회
    files = pipeline.list_s3_action_files()
    
    for file_key in files[-10:]:  # 최근 10개 파일만 처리
        logger.info(f"Processing {file_key}...")
        await pipeline.import_actions_from_s3(file_key)
        
        # 분석 결과도 출력
        stats = await pipeline.analyze_s3_actions(file_key)
        logger.info(f"File stats: {stats}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "pipeline":
            asyncio.run(run_pipeline_once())
        elif command == "historical":
            asyncio.run(process_historical_data())
        elif command == "schedule":
            # 실제 운영에서는 cron job이나 Celery 등을 사용
            async def scheduler():
                while True:
                    await run_pipeline_once()
                    await asyncio.sleep(3600)  # 1시간마다 실행
            
            asyncio.run(scheduler())
        else:
            print("Usage: python action_pipeline.py [pipeline|historical|schedule]")
    else:
        print("""
Action Data Pipeline

Commands:
  pipeline    - Run pipeline once
  historical  - Process historical S3 data
  schedule    - Run continuously every hour

데이터 플로우:
Frontend → Backend API → user_action_logs → S3 JSON → 이미지 벡터화 → 추천 시스템
        """)