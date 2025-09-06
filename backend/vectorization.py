import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import pickle
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
from sklearn.preprocessing import MinMaxScaler
import logging
from typing import Dict, List, Tuple, Any
import asyncio
import asyncpg
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlaceVectorizer:
    def __init__(self):
        # BERT 모델 초기화 (256차원)
        self.bert_model = SentenceTransformer('sentence-transformers/all-MiniLM-L12-v2')
        self.scaler = MinMaxScaler()
        
        # 데이터베이스 연결 설정
        self.db_url = os.getenv("DATABASE_URL")
        
        # 테이블 정보 (각 테이블별 실제 컬럼명)
        self.tables = {
            'accommodation': ['name', 'overview', 'category', 'region', 'city', 'latitude', 'longitude'],
            'restaurants': ['name', 'overview', 'category', 'region', 'city', 'latitude', 'longitude'],
            'nature': ['name', 'overview', 'major_category', 'middle_category', 'minor_category', 'region', 'city', 'latitude', 'longitude'],
            'shopping': ['name', 'overview', 'major_category', 'middle_category', 'minor_category', 'region', 'city', 'latitude', 'longitude'],
            'humanities': ['name', 'overview', 'major_category', 'middle_category', 'minor_category', 'region', 'city', 'latitude', 'longitude'],
            'leisure_sports': ['name', 'overview', 'major_category', 'middle_category', 'minor_category', 'region', 'city', 'latitude', 'longitude']
        }

    async def fetch_data_from_db(self) -> Dict[str, pd.DataFrame]:
        """데이터베이스에서 모든 테이블 데이터 가져오기 (이미 완료된 테이블 제외)"""
        conn = await asyncpg.connect(self.db_url)
        all_data = {}
        
        try:
            for table_name, columns in self.tables.items():
                # 이미 벡터화된 테이블인지 확인
                if await self.is_table_vectorized(table_name):
                    logger.info(f"Skipping {table_name} - already vectorized")
                    continue
                
                query = f"SELECT id, {', '.join(columns)} FROM {table_name} WHERE name IS NOT NULL AND overview IS NOT NULL AND image_urls IS NOT NULL AND image_urls != 'null'::jsonb AND (jsonb_typeof(image_urls) = 'array' AND jsonb_array_length(image_urls) > 0)"
                rows = await conn.fetch(query)
                
                if rows:
                    df = pd.DataFrame([dict(row) for row in rows])
                    all_data[table_name] = df
                    logger.info(f"Loaded {len(df)} records from {table_name}")
                else:
                    logger.warning(f"No data found in {table_name}")
                    
        finally:
            await conn.close()
            
        return all_data

    def create_combined_text(self, row: pd.Series, table_name: str) -> str:
        """텍스트 결합 (이름 + 설명 + 카테고리 + 지역)"""
        text_parts = []
        
        # 이름 추가
        if pd.notna(row.get('name')):
            text_parts.append(str(row['name']))
        
        # 설명 추가
        if pd.notna(row.get('overview')):
            text_parts.append(str(row['overview']))
        
        # 카테고리 추가
        if table_name == 'restaurants' or table_name == 'accommodation':
            if pd.notna(row.get('category')):
                text_parts.append(str(row['category']))
        else:
            # nature, shopping, humanities, leisure_sports의 경우
            for cat in ['major_category', 'middle_category', 'minor_category']:
                if pd.notna(row.get(cat)):
                    text_parts.append(str(row[cat]))
        
        # 지역 정보 추가
        if pd.notna(row.get('region')):
            text_parts.append(str(row['region']))
        if pd.notna(row.get('city')):
            text_parts.append(str(row['city']))
        
        return ' '.join(text_parts)

    async def is_table_vectorized(self, table_name: str) -> bool:
        """테이블이 이미 벡터화되었는지 확인"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # place_features 테이블에서 해당 테이블의 벡터 데이터가 있는지 확인
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM place_features WHERE table_name = $1",
                table_name
            )
            return count > 0
        except:
            return False
        finally:
            await conn.close()

    def vectorize_places(self, data: Dict[str, pd.DataFrame]) -> Dict[str, np.ndarray]:
        """모든 장소 데이터를 벡터화"""
        vectors = {}
        
        for table_name, df in data.items():
            logger.info(f"Vectorizing {table_name}...")
            
            # 텍스트 결합
            combined_texts = []
            for _, row in df.iterrows():
                combined_text = self.create_combined_text(row, table_name)
                combined_texts.append(combined_text)
            
            # BERT 임베딩 생성
            embeddings = self.bert_model.encode(combined_texts, show_progress_bar=True)
            
            # ID와 함께 저장
            place_data = []
            for idx, (_, row) in enumerate(df.iterrows()):
                place_data.append({
                    'id': row['id'],
                    'table_name': table_name,
                    'name': row.get('name', ''),
                    'region': row.get('region', ''),
                    'city': row.get('city', ''),
                    'latitude': float(row.get('latitude', 0)) if pd.notna(row.get('latitude')) else 0,
                    'longitude': float(row.get('longitude', 0)) if pd.notna(row.get('longitude')) else 0,
                    'vector': embeddings[idx][:256]  # 256차원으로 자르기
                })
            
            vectors[table_name] = place_data
            logger.info(f"Vectorized {len(place_data)} places from {table_name}")
        
        return vectors

    async def save_vectors_to_db(self, vectors: Dict[str, List[Dict]]):
        """벡터 데이터를 데이터베이스에 저장"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # place_features 테이블이 없으면 생성
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS place_features (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    place_id INTEGER NOT NULL,
                    table_name VARCHAR(50) NOT NULL,
                    name VARCHAR(255),
                    region VARCHAR(100),
                    city VARCHAR(100),
                    latitude NUMERIC,
                    longitude NUMERIC,
                    vector VECTOR(256) NOT NULL,
                    created_at TIMESTAMP DEFAULT now(),
                    UNIQUE(place_id, table_name)
                )
            """)
            
            # 기존 데이터 삭제
            await conn.execute("TRUNCATE TABLE place_features")
            
            # 새 벡터 데이터 삽입
            for table_name, places in vectors.items():
                for place in places:
                    await conn.execute("""
                        INSERT INTO place_features 
                        (place_id, table_name, name, region, city, latitude, longitude, vector)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, 
                    place['id'], 
                    place['table_name'],
                    place['name'],
                    place['region'],
                    place['city'],
                    place['latitude'],
                    place['longitude'],
                    str(place['vector'].tolist())
                    )
            
            logger.info("Vectors saved to database successfully")
            
        finally:
            await conn.close()

    def save_vectors_to_file(self, vectors: Dict[str, List[Dict]], filepath: str = "place_vectors.pkl"):
        """벡터 데이터를 파일로 저장 (백업용)"""
        with open(filepath, 'wb') as f:
            pickle.dump(vectors, f)
        logger.info(f"Vectors saved to {filepath}")

    async def run_vectorization(self):
        """전체 벡터화 프로세스 실행"""
        logger.info("Starting vectorization process...")
        
        # 1. 데이터 가져오기
        data = await self.fetch_data_from_db()
        
        if not data:
            logger.error("No data found in database")
            return
        
        # 2. 벡터화
        vectors = self.vectorize_places(data)
        
        # 3. 데이터베이스에 저장
        await self.save_vectors_to_db(vectors)
        
        # 4. 파일로 백업
        self.save_vectors_to_file(vectors)
        
        logger.info("Vectorization completed successfully")

class RecommendationEngine:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.bert_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    async def get_user_preferences(self, user_id: str) -> Dict:
        """사용자 선호도 가져오기"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # 기본 선호도
            basic_prefs = await conn.fetchrow("""
                SELECT persona, priority, accommodation, exploration 
                FROM user_preferences 
                WHERE user_id = $1
                ORDER BY created_at DESC LIMIT 1
            """, user_id)
            
            # 태그 선호도
            tag_prefs = await conn.fetch("""
                SELECT tag, weight
                FROM user_preference_tags
                WHERE user_id = $1
            """, user_id)
            
            return {
                'basic': dict(basic_prefs) if basic_prefs else None,
                'tags': [dict(tag) for tag in tag_prefs] if tag_prefs else []
            }
            
        finally:
            await conn.close()

    async def get_user_action_history(self, user_id: str) -> List[Dict]:
        """사용자 행동 이력 가져오기"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            actions = await conn.fetch("""
                SELECT ual.place_category, ual.place_id, ual.action_type, 
                       ual.action_value, aw.weight
                FROM user_action_logs ual
                JOIN action_weights aw ON ual.action_type = aw.action_type
                WHERE ual.user_id = $1
                ORDER BY ual.created_at DESC
            """, user_id)
            
            return [dict(action) for action in actions]
            
        finally:
            await conn.close()

    def calculate_similarity_scores(
        self, 
        user_vector: np.ndarray, 
        place_vectors: List[np.ndarray],
        weights: Dict[str, float] = None
    ) -> List[float]:
        """유사도 점수 계산 (코사인 + 유클리드)"""
        if weights is None:
            weights = {'cosine': 0.7, 'euclidean': 0.3}
        
        # 코사인 유사도 (높을수록 유사)
        cosine_scores = cosine_similarity([user_vector], place_vectors)[0]
        
        # 유클리드 거리 (낮을수록 유사) -> 유사도로 변환
        euclidean_dists = euclidean_distances([user_vector], place_vectors)[0]
        max_dist = np.max(euclidean_dists)
        euclidean_scores = (max_dist - euclidean_dists) / max_dist if max_dist > 0 else np.ones_like(euclidean_dists)
        
        # 가중 평균
        final_scores = (
            weights['cosine'] * cosine_scores + 
            weights['euclidean'] * euclidean_scores
        )
        
        return final_scores.tolist()

    async def get_fallback_places(self, limit: int = 20) -> List[Dict]:
        """개인화 추천 실패시 실제 DB 데이터에서 간단한 장소 반환"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # place_recommendations 테이블에서 간단히 데이터 가져오기
            query = """
                SELECT place_id, table_name, name, region, city, latitude, longitude, 
                       description, image_urls
                FROM place_recommendations 
                ORDER BY RANDOM() 
                LIMIT $1
            """
            
            places = await conn.fetch(query, limit)
            
            results = []
            for place in places:
                results.append({
                    'place_id': place['place_id'],
                    'table_name': place['table_name'],
                    'name': place['name'] or '이름 없음',
                    'region': place['region'] or '지역 미상',
                    'city': place['city'],
                    'latitude': float(place['latitude']) if place['latitude'] else 0.0,
                    'longitude': float(place['longitude']) if place['longitude'] else 0.0,
                    'description': place['description'] or '설명 없음',
                    'image_urls': place['image_urls'],
                    'similarity_score': 0.7  # 기본 점수
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in fallback places: {str(e)}")
            return []
        finally:
            await conn.close()

    async def get_popular_places(self, region: str = None, category: str = None, limit: int = 20, exclude_places: List[tuple] = None) -> List[Dict]:
        """인기 장소 가져오기 (로그인 전 추천) - 통합 테이블 사용"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # 행동 로그 기반 인기도 계산 (통합 테이블 사용)
            query = """
                WITH place_popularity AS (
                    SELECT 
                        ual.place_category as table_name,
                        ual.place_id,
                        SUM(aw.weight * COALESCE(ual.action_value, 1)) as popularity_score,
                        COUNT(*) as action_count
                    FROM user_action_logs ual
                    JOIN action_weights aw ON ual.action_type = aw.action_type
                    GROUP BY ual.place_category, ual.place_id
                )
                SELECT 
                    pr.*,
                    COALESCE(pp.popularity_score, 0) as popularity_score,
                    COALESCE(pp.action_count, 0) as action_count
                FROM place_recommendations pr
                LEFT JOIN place_popularity pp ON pr.table_name = pp.table_name AND pr.place_id = pp.place_id
            """
            
            conditions = []
            params = []
            param_count = 0
            
            if region:
                param_count += 1
                conditions.append(f"pr.region = ${param_count}")
                params.append(region)
            
            if category:
                param_count += 1
                conditions.append(f"pr.table_name = ${param_count}")
                params.append(category)
            
            # 제외할 장소 조건 추가
            if exclude_places:
                exclude_conditions = []
                for place_id, table_name in exclude_places:
                    param_count += 2
                    exclude_conditions.append(f"NOT (pr.place_id = ${param_count - 1} AND pr.table_name = ${param_count})")
                    params.extend([place_id, table_name])
                conditions.extend(exclude_conditions)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += f" ORDER BY popularity_score DESC, action_count DESC LIMIT ${param_count + 1}"
            params.append(limit)
            
            places = await conn.fetch(query, *params)
            return [dict(place) for place in places]
            
        finally:
            await conn.close()

    async def get_personalized_recommendations(
        self, 
        user_id: str, 
        region: str = None, 
        category: str = None, 
        limit: int = 20
    ) -> List[Dict]:
        """개인화 추천 (로그인 후) - 통합 테이블 사용"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # 사용자 선호도 및 행동 이력 가져오기
            preferences = await self.get_user_preferences(user_id)
            actions = await self.get_user_action_history(user_id)
            
            # 사용자 선호도 벡터 생성
            user_vector = await self._create_user_vector(preferences, actions)
            
            # 통합 테이블에서 장소 데이터 가져오기 (JOIN 없음)
            query = "SELECT * FROM place_recommendations"
            conditions = []
            params = []
            param_count = 0
            
            if region:
                param_count += 1
                conditions.append(f"region = ${param_count}")
                params.append(region)
            
            if category:
                param_count += 1
                conditions.append(f"table_name = ${param_count}")
                params.append(category)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            # 성능을 위해 전체가 아닌 샘플링 (큰 데이터셋인 경우)
            query += " ORDER BY RANDOM() LIMIT 5000"
            
            places = await conn.fetch(query, *params)
            
            if not places:
                return []
            
            # 벡터 추출 및 유사도 계산
            place_vectors = [np.array(place['vector']) for place in places]
            similarity_scores = self.calculate_similarity_scores(user_vector, place_vectors)
            
            # 점수와 함께 결과 생성
            results = []
            for i, place in enumerate(places):
                place_dict = dict(place)
                place_dict['similarity_score'] = similarity_scores[i]
                results.append(place_dict)
            
            # 유사도 순으로 정렬
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return results[:limit]
            
        finally:
            await conn.close()

    async def _create_user_vector(self, preferences: Dict, actions: List[Dict]) -> np.ndarray:
        """사용자 선호도와 행동을 바탕으로 사용자 벡터 생성"""
        
        # 선호도 텍스트 생성
        preference_texts = []
        
        if preferences['basic']:
            # 선호도 정의에서 설명 가져오기
            conn = await asyncpg.connect(self.db_url)
            try:
                for key, value in preferences['basic'].items():
                    desc = await conn.fetchval("""
                        SELECT description FROM preference_definitions 
                        WHERE category = $1 AND option_key = $2
                    """, key, value)
                    if desc:
                        preference_texts.append(desc)
            finally:
                await conn.close()
        
        # 태그 선호도 추가
        for tag_pref in preferences['tags']:
            preference_texts.append(tag_pref['tag'])
        
        # 행동 이력 기반 텍스트 추가 (좋아요, 북마크한 장소들의 정보)
        action_places = []
        high_weight_actions = [action for action in actions if action['weight'] >= 2.0]
        
        if high_weight_actions:
            conn = await asyncpg.connect(self.db_url)
            try:
                for action in high_weight_actions[:10]:  # 최근 10개만
                    place_info = await conn.fetchrow(f"""
                        SELECT name, overview FROM {action['place_category']} 
                        WHERE id = $1
                    """, action['place_id'])
                    if place_info and place_info['overview']:
                        action_places.append(f"{place_info['name']} {place_info['overview']}")
            finally:
                await conn.close()
        
        # 모든 텍스트 결합
        all_texts = preference_texts + action_places
        combined_text = ' '.join(all_texts) if all_texts else "일반적인 여행지"
        
        # BERT 벡터화
        user_vector = self.bert_model.encode([combined_text])[0]
        
        return user_vector

    async def get_popular_regions(self, limit: int = 10) -> List[Dict]:
        """인기 지역 목록 조회"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            regions = await conn.fetch("""
                WITH region_popularity AS (
                    SELECT 
                        pf.region,
                        COUNT(*) as place_count,
                        AVG(COALESCE(pp.popularity_score, 0)) as avg_popularity
                    FROM place_features pf
                    LEFT JOIN (
                        SELECT 
                            ual.place_category as table_name,
                            ual.place_id,
                            SUM(aw.weight * COALESCE(ual.action_value, 1)) as popularity_score
                        FROM user_action_logs ual
                        JOIN action_weights aw ON ual.action_type = aw.action_type
                        GROUP BY ual.place_category, ual.place_id
                    ) pp ON pf.table_name = pp.table_name AND pf.place_id = pp.place_id
                    WHERE pf.region IS NOT NULL
                    GROUP BY pf.region
                )
                SELECT 
                    region,
                    place_count,
                    avg_popularity,
                    (place_count * 0.3 + avg_popularity * 0.7) as total_score
                FROM region_popularity
                ORDER BY total_score DESC
                LIMIT $1
            """, limit)
            
            return [dict(region) for region in regions]
            
        finally:
            await conn.close()

    async def get_personalized_regions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """개인화 지역 추천"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # 사용자 선호도 가져오기
            preferences = await self.get_user_preferences(user_id)
            actions = await self.get_user_action_history(user_id)
            
            # 사용자 벡터 생성
            user_vector = await self._create_user_vector(preferences, actions)
            
            # 지역별 대표 벡터 계산
            regions = await conn.fetch("""
                SELECT 
                    region,
                    COUNT(*) as place_count,
                    AVG(latitude) as avg_lat,
                    AVG(longitude) as avg_lng
                FROM place_features 
                WHERE region IS NOT NULL
                GROUP BY region
                HAVING COUNT(*) >= 3
            """)
            
            region_scores = []
            for region in regions:
                # 해당 지역의 장소들 가져오기
                places = await conn.fetch("""
                    SELECT vector FROM place_features WHERE region = $1 LIMIT 20
                """, region['region'])
                
                if places:
                    # 지역 대표 벡터 (평균)
                    place_vectors = [np.array(place['vector']) for place in places]
                    region_vector = np.mean(place_vectors, axis=0)
                    
                    # 유사도 계산
                    similarity = self.calculate_similarity_scores(user_vector, [region_vector])[0]
                    
                    region_scores.append({
                        'region': region['region'],
                        'place_count': region['place_count'],
                        'avg_lat': float(region['avg_lat']),
                        'avg_lng': float(region['avg_lng']),
                        'similarity_score': similarity
                    })
            
            # 유사도 순으로 정렬
            region_scores.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return region_scores[:limit]
            
        finally:
            await conn.close()

    async def record_user_action(
        self, 
        user_id: str, 
        place_id: int, 
        place_category: str, 
        action_type: str, 
        action_value: float = None
    ):
        """사용자 행동 기록"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            await conn.execute("""
                INSERT INTO user_action_logs 
                (user_id, place_category, place_id, action_type, action_value)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id, place_category, place_id, action_type, action_value)
            
        finally:
            await conn.close()

    async def get_user_recommendation_stats(self, user_id: str) -> Dict:
        """사용자 추천 통계"""
        conn = await asyncpg.connect(self.db_url)
        
        try:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_actions,
                    COUNT(DISTINCT place_category) as categories_explored,
                    COUNT(DISTINCT CASE WHEN action_type = 'like' THEN place_id END) as liked_places,
                    COUNT(DISTINCT CASE WHEN action_type = 'bookmark' THEN place_id END) as bookmarked_places,
                    AVG(CASE WHEN action_type = 'dwell_time' THEN action_value END) as avg_dwell_time
                FROM user_action_logs 
                WHERE user_id = $1
            """, user_id)
            
            return dict(stats) if stats else {}
            
        finally:
            await conn.close()

# 실행 함수들
async def run_vectorization():
    """벡터화 실행"""
    vectorizer = PlaceVectorizer()
    await vectorizer.run_vectorization()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "vectorize":
        asyncio.run(run_vectorization())
    else:
        print("Usage: python vectorization.py vectorize")