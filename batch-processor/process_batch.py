#!/usr/bin/env python3
"""
AWS Batch 메인 처리 스크립트
S3에서 사용자 행동 데이터를 읽어서 OpenCLIP 벡터로 변환하고 PostgreSQL에 저장
"""
import os
import sys
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import gzip
from pathlib import Path

import boto3
import pandas as pd
import numpy as np
from langchain_experimental.open_clip import OpenCLIPEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import requests
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env file from {env_path}")
else:
    print(f"⚠️ .env file not found at {env_path}")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/batch_processing.log')
    ]
)
logger = logging.getLogger(__name__)

# 환경 변수 설정
AWS_REGION = os.getenv('AWS_REGION', 'ap-northeast-2')
S3_BUCKET = os.getenv('S3_BUCKET', os.getenv('S3_EVENTS_BUCKET', 'user-actions-data'))
S3_PREFIX = os.getenv('S3_PREFIX', 'user-actions/')
DATABASE_URL = os.getenv('DATABASE_URL')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Main EC2 webhook URL
BATCH_ID = os.getenv('BATCH_ID', f'batch_{int(datetime.now().timestamp())}')
JOB_NAME = os.getenv('AWS_BATCH_JOB_NAME', 'witple-vectorization-job')
JOB_ID = os.getenv('AWS_BATCH_JOB_ID', 'unknown')

# 시간 가중치 설정 (외부화)
TIME_DECAY_LAMBDA = float(os.getenv('TIME_DECAY_LAMBDA', '0.0231'))  # 30일 후 50% 감쇠

# 텍스트 벡터화 모델 설정 (HuggingFace MiniLM)
TEXT_MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"
TEXT_VECTOR_DIM = 384

# 이미지 벡터화 모델 설정 (OpenCLIP)
OPENCLIP_IMAGE_MODEL_NAME = "ViT-B-32"  # 이미지용 (512차원)
OPENCLIP_IMAGE_CHECKPOINT = "laion2b_s34b_b79k"
IMAGE_VECTOR_DIM = 512

# 로드된 환경변수 확인
logger = logging.getLogger(__name__)
print(f"🔧 Environment Variables:")
print(f"  AWS_REGION: {AWS_REGION}")
print(f"  S3_BUCKET: {S3_BUCKET}")
print(f"  S3_PREFIX: {S3_PREFIX}")
print(f"  DATABASE_URL: {'***' if DATABASE_URL else 'NOT SET'}")
print(f"  WEBHOOK_URL: {WEBHOOK_URL}")
print(f"  AWS_ACCESS_KEY_ID: {'***' if os.getenv('AWS_ACCESS_KEY_ID') else 'NOT SET'}")
print(f"  TIME_DECAY_LAMBDA: {TIME_DECAY_LAMBDA} (30-day decay: {np.exp(-TIME_DECAY_LAMBDA * 30):.2f})")
print(f"  TEXT_VECTOR_DIM: {TEXT_VECTOR_DIM} (MiniLM 텍스트 벡터 차원)")
print(f"  IMAGE_VECTOR_DIM: {IMAGE_VECTOR_DIM} (CLIP 이미지 벡터 차원)")

class BatchProcessor:
    def __init__(self):
        logger.info("🚀 Initializing Batch Processor")
        
        # AWS 클라이언트 초기화
        self.s3_client = boto3.client('s3', region_name=AWS_REGION)
        
        # 텍스트 벡터화 모델 로드 (HuggingFace MiniLM)
        logger.info(f"📥 Loading HuggingFace text model: {TEXT_MODEL_NAME}")
        self.text_embedding_model = HuggingFaceEmbeddings(
            model_name=TEXT_MODEL_NAME
        )

        # 이미지 벡터화 모델 로드 (OpenCLIP)
        logger.info(f"📥 Loading OpenCLIP image model: {OPENCLIP_IMAGE_MODEL_NAME}")
        self.image_embedding_model = OpenCLIPEmbeddings(
            model_name=OPENCLIP_IMAGE_MODEL_NAME,
            checkpoint=OPENCLIP_IMAGE_CHECKPOINT
        )

        # 벡터 차원 설정
        self.text_vector_dimension = TEXT_VECTOR_DIM
        self.image_vector_dimension = IMAGE_VECTOR_DIM
        logger.info(f"✅ Text and image models loaded successfully.")
        logger.info(f"🎯 Text vectors (MiniLM): {self.text_vector_dimension} dimensions")
        logger.info(f"🎯 Image vectors (CLIP): {self.image_vector_dimension} dimensions")
        
        # 데이터베이스 연결
        if DATABASE_URL:
            self.engine = create_engine(DATABASE_URL)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            logger.info("✅ Database connection established")
        else:
            logger.warning("⚠️ DATABASE_URL not provided, database operations will be skipped")
            self.engine = None
            self.SessionLocal = None
        
        # NEW: DB 조회 결과를 캐싱하여 성능 향상
        self.place_overview_cache = {}

        # NEW: OpenCLIP 인코딩 결과 캐싱하여 중복 연산 방지
        self.bert_encoding_cache = {}
        self._cache_hits = 0
        self._cache_attempts = 0

        # 통계 정보 초기화
        self.stats = {
            'processed_files': 0,
            'processed_actions': 0,
            'processed_users': 0,
            'processed_places': 0,
            'errors': 0,
            'time_weighted_users': 0,  # 시간 가중치 적용된 사용자 수
            'fallback_users': 0,       # 텍스트 기반 fallback 사용자 수
            'start_time': datetime.now(),
            'end_time': None
        }

    # NEW: place_id와 category로 DB에서 overview를 조회하는 함수
    def _get_overview_from_db(self, numeric_id: int, category: str) -> Optional[str]:
        """주어진 숫자 ID와 카테고리로 DB에서 overview를 조회하고 캐시에 저장합니다."""
        cache_key = f"{numeric_id}:{category}"
        if cache_key in self.place_overview_cache:
            return self.place_overview_cache[cache_key]

        if not self.SessionLocal:
            return None

        db = self.SessionLocal()
        try:
            # place_recommendations 테이블을 조회한다고 가정
            query = text("""
                SELECT overview FROM place_recommendations
                WHERE place_id = :numeric_id AND table_name = :category
                LIMIT 1
            """)
            result = db.execute(query, {'numeric_id': numeric_id, 'category': category}).scalar_one_or_none()
            
            self.place_overview_cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"❌ DB lookup failed for ID={numeric_id}, Category={category}: {e}")
            self.place_overview_cache[cache_key] = None  # 실패한 조회도 캐싱하여 반복 방지
            return None
        finally:
            db.close()

    def _encode_text_with_cache(self, text: str) -> List[float]:
        """텍스트를 OpenCLIP으로 인코딩하되 캐시를 활용하여 중복 연산 방지"""
        # 통계 업데이트
        self._cache_attempts += 1

        # 텍스트를 정규화하여 캐시 키로 사용
        cache_key = text.strip()[:500]  # 너무 긴 텍스트는 잘라서 사용

        if cache_key in self.bert_encoding_cache:
            self._cache_hits += 1
            logger.debug(f"🔥 Cache hit for text encoding: {cache_key[:50]}...")
            return self.bert_encoding_cache[cache_key]

        # 캐시 미스 시 MiniLM 텍스트 인코딩 수행 (384차원)
        vector = self.text_embedding_model.embed_query(text)
        # 벡터 차원 검증 및 패딩/트리밍
        if len(vector) > TEXT_VECTOR_DIM:
            vector = vector[:TEXT_VECTOR_DIM]  # 트리밍
        elif len(vector) < TEXT_VECTOR_DIM:
            vector = vector + [0.0] * (TEXT_VECTOR_DIM - len(vector))  # 제로 패딩
        self.bert_encoding_cache[cache_key] = vector
        logger.debug(f"🧠 Generated new encoding for: {cache_key[:50]}...")

        return vector

    def _encode_image_rgb(self, image_path_or_url: str) -> List[float]:
        """이미지를 RGB 기준 512차원 벡터로 인코딩"""
        cache_key = f"image:{image_path_or_url}"
        self._cache_attempts += 1

        # 캐시 조회
        if cache_key in self.bert_encoding_cache:
            self._cache_hits += 1
            logger.debug(f"🔥 Cache hit for image encoding: {cache_key[:50]}...")
            return self.bert_encoding_cache[cache_key]

        try:
            # CLIP을 통한 이미지 인코딩 (512차원)
            # 실제 이미지 파일이나 URL을 처리하는 경우 embed_image 메서드 사용
            # 현재는 이미지 설명 텍스트를 이미지 모델로 인코딩
            vector = self.image_embedding_model.embed_query(f"image: {image_path_or_url}")

            # 벡터 차원 검증 및 패딩/트리밍 (512차원)
            if len(vector) > IMAGE_VECTOR_DIM:
                vector = vector[:IMAGE_VECTOR_DIM]  # 트리밍
            elif len(vector) < IMAGE_VECTOR_DIM:
                vector = vector + [0.0] * (IMAGE_VECTOR_DIM - len(vector))  # 제로 패딩

            self.bert_encoding_cache[cache_key] = vector
            logger.debug(f"🖼️ Generated new CLIP image encoding for: {cache_key[:50]}...")
            return vector

        except Exception as e:
            logger.error(f"❌ Error encoding image {image_path_or_url}: {e}")
            # 에러 시 제로 벡터 반환
            return [0.0] * IMAGE_VECTOR_DIM

    def _generate_time_weighted_user_vector(self, user_id: str, data: Dict[str, Any], place_vectors: Dict[str, Any]) -> List[float]:
        """시간 가중치를 적용한 사용자 벡터 생성 (안전성 강화)"""
        try:
            positive_actions_info = []
            current_time_utc = datetime.now(timezone.utc)

            # 1. 긍정적 행동(좋아요/북마크)에서 시간 정보와 벡터 수집
            for action in data['actions']:
                if action.get('action_type') in ['like', 'bookmark']:
                    place_key = f"{action.get('place_category')}:{action.get('place_id')}"
                    action_time = action.get('action_time')

                    # 시간 정보와 장소 벡터가 모두 있는 경우만 처리
                    if action_time and place_key in place_vectors:
                        try:
                            # 안전한 시간 파싱 (다양한 형식 지원)
                            timestamp_str = str(action_time)
                            if timestamp_str.endswith('Z'):
                                timestamp_str = timestamp_str.replace('Z', '+00:00')

                            timestamp = datetime.fromisoformat(timestamp_str)

                            # naive datetime을 UTC로 처리
                            if timestamp.tzinfo is None:
                                timestamp = timestamp.replace(tzinfo=timezone.utc)

                            vector = place_vectors[place_key]['behavior_vector']
                            positive_actions_info.append({
                                'vector': vector,
                                'timestamp': timestamp,
                                'action_type': action.get('action_type')
                            })

                        except (ValueError, TypeError, AttributeError) as e:
                            logger.debug(f"Failed to parse timestamp '{action_time}' for user {user_id}: {e}")
                            continue

            # 2. 시간 가중치 적용한 벡터 평균 계산
            if positive_actions_info:
                vectors = np.array([item['vector'] for item in positive_actions_info])

                # 시간 가중치 계산 (지수 감쇠 모델)
                weights = []
                total_weight = 0

                for item in positive_actions_info:
                    time_diff_days = (current_time_utc - item['timestamp']).total_seconds() / 86400
                    time_weight = np.exp(-TIME_DECAY_LAMBDA * max(0, time_diff_days))  # 음수 방지

                    # 행동 유형별 추가 가중치 (북마크 > 좋아요)
                    action_weight = 1.5 if item['action_type'] == 'bookmark' else 1.0

                    final_weight = time_weight * action_weight
                    weights.append(final_weight)
                    total_weight += final_weight

                if total_weight > 0:
                    # 가중 평균 계산
                    vector = np.average(vectors, axis=0, weights=weights).tolist()
                    logger.info(f"Generated time-weighted vector for user {user_id} from {len(vectors)} actions (total_weight: {total_weight:.3f})")
                    self.stats['time_weighted_users'] += 1
                    return vector

            # 3. Fallback: 시간 정보가 없거나 긍정적 행동이 없는 경우
            logger.info(f"User {user_id}: No time-weighted actions available, using behavior text fallback")
            behavior_text = self.create_user_behavior_text(data)
            self.stats['fallback_users'] += 1
            return self._encode_text_with_cache(behavior_text)

        except Exception as e:
            # 4. 완전한 예외 처리: 모든 실패 시 기본 텍스트 기반 벡터 사용
            logger.error(f"Time-weighted vector generation failed for user {user_id}: {e}")
            behavior_text = self.create_user_behavior_text(data)
            self.stats['fallback_users'] += 1
            return self._encode_text_with_cache(behavior_text)

    def list_s3_files(self, max_files: int = 100) -> List[Dict[str, Any]]:
        """S3에서 처리할 파일 목록 조회"""
        logger.info(f"🔍 Searching for files in s3://{S3_BUCKET}/{S3_PREFIX}")
        
        files = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        try:
            for page in paginator.paginate(
                Bucket=S3_BUCKET,
                Prefix=S3_PREFIX,
                MaxKeys=1000
            ):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    # .json 파일만 처리 (batch- 접두사가 있는 파일들)
                    if obj['Key'].endswith('.json') and 'batch-' in obj['Key']:
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified']
                        })
                        
                        if len(files) >= max_files:
                            break
                            
                if len(files) >= max_files:
                    break
                    
        except Exception as e:
            logger.error(f"❌ Failed to list S3 files: {str(e)}")
            raise
            
        logger.info(f"📋 Found {len(files)} files to process")
        return sorted(files, key=lambda x: x['last_modified'])
    
    def download_and_parse_s3_file(self, s3_key: str) -> List[Dict[str, Any]]:
        """S3 파일을 다운로드하고 파싱"""
        logger.info(f"📥 Downloading {s3_key}")
        
        try:
            # S3 객체 다운로드
            response = self.s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            content = response['Body'].read()
            
            # GZIP 압축 여부 확인
            if response.get('ContentEncoding') == 'gzip':
                content = gzip.decompress(content)
            
            # JSON 파싱
            data = json.loads(content.decode('utf-8'))
            
            # 배치 데이터 구조에서 actions 추출
            if 'actions' in data:
                actions = data['actions']
            else:
                # 단일 액션 파일인 경우
                actions = [data] if isinstance(data, dict) else data
                
            logger.info(f"✅ Parsed {len(actions)} actions from {s3_key}")
            return actions
            
        except Exception as e:
            logger.error(f"❌ Failed to download/parse {s3_key}: {str(e)}")
            self.stats['errors'] += 1
            return []
    
    def process_user_actions(self, actions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """사용자별 행동 데이터를 처리하고 벡터 생성"""
        logger.info(f"🧠 Processing {len(actions)} actions for vectorization")
        
        user_data = {}
        place_data = {}
        
        # 1. 사용자별/장소별 행동 집계
        for action in actions:
            user_id = action.get('user_id')
            place_id = action.get('place_id')
            place_category = action.get('place_category')
            action_type = action.get('action_type')
            
            if not all([user_id, place_id, place_category, action_type]):
                continue
                
            # 사용자 데이터 집계
            if user_id not in user_data:
                user_data[user_id] = {
                    'actions': [],
                    'total_likes': 0,
                    'total_bookmarks': 0,
                    'total_clicks': 0,
                    'places_visited': set(),
                    'categories_visited': set()
                }
            
            user_data[user_id]['actions'].append(action)
            user_data[user_id]['places_visited'].add(f"{place_category}:{place_id}")
            user_data[user_id]['categories_visited'].add(place_category)
            
            if action_type == 'like':
                user_data[user_id]['total_likes'] += 1
            elif action_type == 'bookmark':
                user_data[user_id]['total_bookmarks'] += 1
            elif action_type == 'click':
                user_data[user_id]['total_clicks'] += 1
            
            # 장소 데이터 집계
            place_key = f"{place_category}:{place_id}"
            if place_key not in place_data:
                place_data[place_key] = {
                    'place_id': place_id,
                    'place_category': place_category,
                    'total_likes': 0,
                    'total_bookmarks': 0,
                    'total_clicks': 0,
                    'unique_users': set()
                }
            
            place_data[place_key]['unique_users'].add(user_id)
            
            if action_type == 'like':
                place_data[place_key]['total_likes'] += 1
            elif action_type == 'bookmark':
                place_data[place_key]['total_bookmarks'] += 1
            elif action_type == 'click':
                place_data[place_key]['total_clicks'] += 1
        
        # 2. 장소별 벡터 생성 (완전히 먼저 생성하여 사용자 벡터에서 참조)
        place_vectors = {}
        logger.info(f"🏢 Generating vectors for {len(place_data)} places")

        for place_key, data in place_data.items():
            try:
                # MODIFIED START
                place_full_id = data['place_id']
                place_category = data['place_category']

                try:
                    numeric_id = int(place_full_id.split('_')[1])
                except (IndexError, ValueError):
                    logger.warning(f"Could not parse numeric ID from {place_full_id}. Skipping overview lookup.")
                    numeric_id = None

                overview = None
                if numeric_id and self.SessionLocal:
                    overview = self._get_overview_from_db(numeric_id, place_category)

                if overview:
                    place_text = overview
                else:
                    place_text = f"Place category: {place_category} with {len(data['unique_users'])} visitors"

                # MiniLM 텍스트 벡터 생성 (캐시 활용하여 중복 연산 방지)
                vector = self._encode_text_with_cache(place_text)
                
                # 인기도 점수 계산
                total_interactions = data['total_likes'] + data['total_bookmarks'] + data['total_clicks']
                popularity_score = min(total_interactions * 2, 100)  # 간단한 인기도 공식
                engagement_score = min((data['total_likes'] + data['total_bookmarks']) * 5, 100)
                
                # ============================================================================
                # 🚀 ENHANCED SCORING SYSTEM (팀 검토 후 적용)
                # ============================================================================
                """
                # 개선된 가중치 기반 점수 계산
                ACTION_WEIGHTS = {
                    'click': 1.0,      # 기본 관심도
                    'like': 3.0,       # 3배 가중치 (긍정적 반응)
                    'bookmark': 5.0    # 5배 가중치 (강한 선호)
                }
                
                # 1. 가중치 기반 인기도 점수
                weighted_score = (
                    data['total_clicks'] * ACTION_WEIGHTS['click'] +
                    data['total_likes'] * ACTION_WEIGHTS['like'] + 
                    data['total_bookmarks'] * ACTION_WEIGHTS['bookmark']
                )
                
                # 정규화 (0-100 스케일) - 기준: click 50개 + like 10개 + bookmark 5개 = 100점
                max_reference_score = (50 * 1.0) + (10 * 3.0) + (5 * 5.0)  # = 105
                enhanced_popularity_score = min((weighted_score / max_reference_score) * 100, 100)
                
                # 2. 참여도 점수 (액션의 질 중심)
                if total_interactions > 0:
                    high_value_actions = data['total_likes'] + data['total_bookmarks'] 
                    engagement_ratio = high_value_actions / total_interactions
                    base_engagement = engagement_ratio * 100
                    # 절대값 보정 (최소한의 like/bookmark이 있어야 높은 점수)
                    min_threshold_bonus = min(high_value_actions * 5, 20)  # 최대 20점 보너스
                    enhanced_engagement_score = min(base_engagement + min_threshold_bonus, 100)
                else:
                    enhanced_engagement_score = 0.0
                
                # 기존 점수와 개선된 점수를 모두 저장하여 A/B 테스트 가능
                # popularity_score = round(enhanced_popularity_score, 2)
                # engagement_score = round(enhanced_engagement_score, 2)
                """
                
                place_vectors[place_key] = {
                    'place_id': data['place_id'],
                    'place_category': data['place_category'],
                    'behavior_vector': vector,
                    'combined_vector': vector,  # 동일한 벡터 사용
                    'total_likes': data['total_likes'],
                    'total_bookmarks': data['total_bookmarks'],
                    'total_clicks': data['total_clicks'],
                    'unique_users': len(data['unique_users']),
                    'popularity_score': round(popularity_score, 2),
                    'engagement_score': round(engagement_score, 2)
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to process place {place_key}: {str(e)}")
                self.stats['errors'] += 1
                continue

        logger.info(f"✅ Completed place vector generation for {len(place_vectors)} places")

        # 3. 사용자별 벡터 생성 (장소 벡터 완성 후)
        user_vectors = {}
        logger.info(f"👤 Generating vectors for {len(user_data)} users")
        for user_id, data in user_data.items():
            try:
                # 개선된 시간 가중치 벡터 생성
                vector = self._generate_time_weighted_user_vector(user_id, data, place_vectors)

                # 행동 점수 계산 (0-100 스케일)
                total_actions = len(data['actions'])
                like_score = min((data['total_likes'] / max(total_actions, 1)) * 100, 100)
                bookmark_score = min((data['total_bookmarks'] / max(total_actions, 1)) * 100, 100)
                click_score = min((data['total_clicks'] / max(total_actions, 1)) * 100, 100)

                # 다양성 점수 (방문한 카테고리 수 기반)
                diversity_score = min(len(data['categories_visited']) * 10, 100)

                user_vectors[user_id] = {
                    'user_id': user_id,
                    'behavior_vector': vector,
                    'like_score': round(like_score, 2),
                    'bookmark_score': round(bookmark_score, 2),
                    'click_score': round(click_score, 2),
                    'dwell_time_score': 0.0,  # 기본값 설정
                    'total_actions': total_actions,
                    'total_likes': data['total_likes'],
                    'total_bookmarks': data['total_bookmarks'],
                    'total_clicks': data['total_clicks'],
                    'last_action_date': datetime.now()
                }

            except Exception as e:
                logger.error(f"❌ Failed to process user {user_id}: {str(e)}")
                self.stats['errors'] += 1
                continue

        # 캐시 효율성 통계
        total_cache_entries = len(self.bert_encoding_cache)
        cache_hit_ratio = 0
        if hasattr(self, '_cache_hits') and hasattr(self, '_cache_attempts'):
            cache_hit_ratio = (self._cache_hits / max(self._cache_attempts, 1)) * 100

        logger.info(f"✅ Generated vectors for {len(user_vectors)} users and {len(place_vectors)} places")
        logger.info(f"🔥 Text encoding cache: {total_cache_entries} entries, {cache_hit_ratio:.1f}% hit ratio")
        logger.info(f"⏰ Time-weighted vectors: {self.stats['time_weighted_users']} users, Fallback: {self.stats['fallback_users']} users")

        self.stats['processed_users'] = len(user_vectors)
        self.stats['processed_places'] = len(place_vectors)
        
        return {
            'user_vectors': user_vectors,
            'place_vectors': place_vectors
        }
    
    def create_user_behavior_text(self, user_data: Dict[str, Any]) -> str:
        """사용자 행동 데이터를 MiniLM 입력용 텍스트로 변환"""
        categories = list(user_data['categories_visited'])
        total_actions = len(user_data['actions'])
        
        # 행동 패턴을 자연어로 표현
        behavior_parts = []
        
        if user_data['total_likes'] > 0:
            behavior_parts.append(f"likes {user_data['total_likes']} places")
        if user_data['total_bookmarks'] > 0:
            behavior_parts.append(f"bookmarks {user_data['total_bookmarks']} places")
        if user_data['total_clicks'] > 0:
            behavior_parts.append(f"clicks {user_data['total_clicks']} places")
        
        behavior_text = f"User interested in {', '.join(categories)} categories, " + \
                       f"performed {total_actions} actions: " + \
                       ', '.join(behavior_parts)
        
        return behavior_text[:512]  # MiniLM 텍스트 입력 길이 제한
    
    def save_to_database(self, vectors_data: Dict[str, Dict[str, Any]]) -> bool:
        """벡터 데이터를 데이터베이스에 저장"""
        if not self.SessionLocal:
            logger.warning("⚠️ Database not available, skipping database save")
            return False
            
        logger.info("💾 Saving vectors to database")
        
        db = self.SessionLocal()
        user_success_count = 0
        place_success_count = 0
        user_failures = []
        place_failures = []
        
        try:
            user_vectors = vectors_data['user_vectors']
            place_vectors = vectors_data['place_vectors']
            
            logger.info(f"📊 Processing {len(user_vectors)} user vectors and {len(place_vectors)} place vectors")
            
            # 사용자 벡터 업데이트/삽입
            for user_id, data in user_vectors.items():
                try:
                    # UPSERT 쿼리 실행
                    result = db.execute(text("""
                        INSERT INTO user_behavior_vectors 
                        (user_id, behavior_vector, like_score, bookmark_score, click_score, dwell_time_score,
                         total_actions, total_likes, total_bookmarks, total_clicks, last_action_date, vector_updated_at)
                        VALUES (:user_id, :behavior_vector, :like_score, :bookmark_score, :click_score, :dwell_time_score,
                                :total_actions, :total_likes, :total_bookmarks, :total_clicks, :last_action_date, NOW())
                        ON CONFLICT (user_id) DO UPDATE SET
                            behavior_vector = EXCLUDED.behavior_vector,
                            like_score = EXCLUDED.like_score,
                            bookmark_score = EXCLUDED.bookmark_score,
                            click_score = EXCLUDED.click_score,
                            dwell_time_score = EXCLUDED.dwell_time_score,
                            total_actions = EXCLUDED.total_actions,
                            total_likes = EXCLUDED.total_likes,
                            total_bookmarks = EXCLUDED.total_bookmarks,
                            total_clicks = EXCLUDED.total_clicks,
                            last_action_date = EXCLUDED.last_action_date,
                            vector_updated_at = NOW()
                    """), {
                        'user_id': user_id,
                        'behavior_vector': data['behavior_vector'],
                        'like_score': data['like_score'],
                        'bookmark_score': data['bookmark_score'],
                        'click_score': data['click_score'],
                        'dwell_time_score': data['dwell_time_score'],
                        'total_actions': data['total_actions'],
                        'total_likes': data['total_likes'],
                        'total_bookmarks': data['total_bookmarks'],
                        'total_clicks': data['total_clicks'],
                        'last_action_date': data['last_action_date']
                    })
                    user_success_count += 1
                    logger.debug(f"✅ User vector {user_id} saved successfully")
                except Exception as e:
                    user_failures.append(f"{user_id}: {str(e)}")
                    logger.error(f"❌ Failed to save user vector {user_id}: {str(e)}")
                    continue
            
            # 장소 벡터 업데이트/삽입
            for place_key, data in place_vectors.items():
                try:
                    result = db.execute(text("""
                        INSERT INTO place_vectors 
                        (place_id, place_category, behavior_vector, combined_vector,
                         total_likes, total_bookmarks, total_clicks, unique_users,
                         popularity_score, engagement_score, vector_updated_at, stats_updated_at)
                        VALUES (:place_id, :place_category, :behavior_vector, :combined_vector,
                                :total_likes, :total_bookmarks, :total_clicks, :unique_users,
                                :popularity_score, :engagement_score, NOW(), NOW())
                        ON CONFLICT (place_id, place_category) DO UPDATE SET
                            behavior_vector = EXCLUDED.behavior_vector,
                            combined_vector = EXCLUDED.combined_vector,
                            total_likes = EXCLUDED.total_likes,
                            total_bookmarks = EXCLUDED.total_bookmarks,
                            total_clicks = EXCLUDED.total_clicks,
                            unique_users = EXCLUDED.unique_users,
                            popularity_score = EXCLUDED.popularity_score,
                            engagement_score = EXCLUDED.engagement_score,
                            vector_updated_at = NOW(),
                            stats_updated_at = NOW()
                    """), {
                        'place_id': data['place_id'],
                        'place_category': data['place_category'],
                        'behavior_vector': data['behavior_vector'],
                        'combined_vector': data['combined_vector'],
                        'total_likes': data['total_likes'],
                        'total_bookmarks': data['total_bookmarks'],
                        'total_clicks': data['total_clicks'],
                        'unique_users': data['unique_users'],
                        'popularity_score': data['popularity_score'],
                        'engagement_score': data['engagement_score']
                    })
                    place_success_count += 1
                    logger.debug(f"✅ Place vector {place_key} saved successfully")
                except Exception as e:
                    place_failures.append(f"{place_key}: {str(e)}")
                    logger.error(f"❌ Failed to save place vector {place_key}: {str(e)}")
                    continue
            
            # 트랜잭션 커밋
            db.commit()
            
            # 상세한 결과 로깅
            logger.info(f"📊 Database save results:")
            logger.info(f"  - User vectors: {user_success_count}/{len(user_vectors)} saved successfully")
            logger.info(f"  - Place vectors: {place_success_count}/{len(place_vectors)} saved successfully")
            
            if user_failures:
                logger.warning(f"⚠️ User vector failures: {len(user_failures)}")
                for failure in user_failures[:5]:  # 최대 5개만 로그
                    logger.warning(f"  - {failure}")
                if len(user_failures) > 5:
                    logger.warning(f"  - ... and {len(user_failures) - 5} more failures")
            
            if place_failures:
                logger.warning(f"⚠️ Place vector failures: {len(place_failures)}")
                for failure in place_failures[:5]:  # 최대 5개만 로그
                    logger.warning(f"  - {failure}")
                if len(place_failures) > 5:
                    logger.warning(f"  - ... and {len(place_failures) - 5} more failures")
            
            # 성공 기준: 전체의 80% 이상이 성공해야 함
            total_expected = len(user_vectors) + len(place_vectors)
            total_success = user_success_count + place_success_count
            success_rate = total_success / total_expected if total_expected > 0 else 0
            
            if success_rate >= 0.8:
                logger.info(f"✅ Database save completed successfully (success rate: {success_rate:.1%})")
                return True
            else:
                logger.error(f"❌ Database save failed (success rate: {success_rate:.1%} < 80%)")
                return False
            
        except Exception as e:
            logger.error(f"❌ Database save failed with exception: {str(e)}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def send_webhook_notification(self, success: bool, error_message: Optional[str] = None):
        """Main EC2에 처리 완료 알림 전송"""
        if not WEBHOOK_URL:
            logger.warning("⚠️ WEBHOOK_URL not provided, skipping webhook notification")
            return
            
        logger.info(f"📡 Sending webhook notification to {WEBHOOK_URL}")
        
        try:
            webhook_data = {
                'job_id': JOB_ID,
                'job_name': JOB_NAME,
                'job_status': 'SUCCEEDED' if success else 'FAILED',
                'batch_id': BATCH_ID,
                'processed_records': self.stats['processed_actions'],
                'processing_time_seconds': (self.stats['end_time'] - self.stats['start_time']).total_seconds(),
                's3_input_path': f's3://{S3_BUCKET}/{S3_PREFIX}',
                'error_message': error_message,
                'metadata': {
                    'processed_files': self.stats['processed_files'],
                    'processed_users': self.stats['processed_users'],
                    'processed_places': self.stats['processed_places'],
                    'errors': self.stats['errors']
                }
            }
            
            response = requests.post(
                WEBHOOK_URL,
                json=webhook_data,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info("✅ Webhook notification sent successfully")
            else:
                logger.error(f"❌ Webhook notification failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Failed to send webhook: {str(e)}")
    
    def run(self):
        """메인 처리 로직 실행"""
        logger.info("🎯 Starting batch processing")
        
        try:
            # 1. S3 파일 목록 조회
            files = self.list_s3_files(max_files=50)  # 한번에 최대 50개 파일 처리
            
            if not files:
                logger.info("✅ No files to process")
                self.send_webhook_notification(success=True)
                return
            
            # 2. 파일별로 처리
            all_actions = []
            
            for file_info in files:
                actions = self.download_and_parse_s3_file(file_info['key'])
                if actions:
                    all_actions.extend(actions)
                    self.stats['processed_files'] += 1
            
            if not all_actions:
                logger.info("✅ No actions to process")
                self.send_webhook_notification(success=True)
                return
                
            self.stats['processed_actions'] = len(all_actions)
            logger.info(f"📊 Total actions to process: {len(all_actions)}")
            
            # 3. 벡터화 처리
            vectors_data = self.process_user_actions(all_actions)
            
            # 4. 데이터베이스에 저장
            db_success = self.save_to_database(vectors_data)
            
            # 5. 처리 완료 알림
            self.stats['end_time'] = datetime.now()
            
            if db_success:
                logger.info("🎉 Batch processing completed successfully")
                self.send_webhook_notification(success=True)
            else:
                logger.error("❌ Database save failed")
                self.send_webhook_notification(success=False, error_message="Database save failed")
                
        except Exception as e:
            logger.error(f"❌ Batch processing failed: {str(e)}")
            logger.error(traceback.format_exc())
            
            self.stats['end_time'] = datetime.now()
            self.send_webhook_notification(success=False, error_message=str(e))
            raise

def main():
    """메인 엔트리 포인트"""
    logger.info("🚀 Witple Batch Processor Starting")
    
    # 환경 변수 검증
    required_env_vars = ['DATABASE_URL']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        sys.exit(1)
    
    try:
        processor = BatchProcessor()
        processor.run()
        logger.info("🎉 Batch processing completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()