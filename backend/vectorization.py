import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from typing import Dict, List, Any
import asyncpg
import json
from config import settings

def cosine_similarity(X, Y):
    """코사인 유사도 계산"""
    X = np.array(X)
    Y = np.array(Y)
    
    if X.ndim == 1:
        X = X.reshape(1, -1)
    if Y.ndim == 1:
        Y = Y.reshape(1, -1)
    
    # L2 정규화
    X_norm = X / np.linalg.norm(X, axis=1, keepdims=True)
    Y_norm = Y / np.linalg.norm(Y, axis=1, keepdims=True)
    
    # 코사인 유사도 계산
    similarity = np.dot(X_norm, Y_norm.T)
    
    return similarity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self):
        self.bert_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.db_url = settings.DATABASE_URL

    async def get_user_priority_tags(self, user_id: str) -> List[Dict]:
        """사용자 우선순위 태그 가져오기 - 실제 데이터 구조에 맞게 수정"""
        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. user_preferences에서 priority (단일 최우선 태그) 가져오기
            priority_data = await conn.fetchval("""
                SELECT priority FROM user_preferences 
                WHERE user_id = $1 
                ORDER BY created_at DESC LIMIT 1
            """, user_id)
            
            # 2. user_preference_tags에서 추가 태그들 가져오기
            additional_tags = await conn.fetch("""
                SELECT tag, weight FROM user_preference_tags 
                WHERE user_id = $1
                ORDER BY created_at ASC
            """, user_id)
            
            priority_tags = []
            
            # 3. Priority 태그가 있으면 최고 우선순위로 설정
            if priority_data:
                # Priority를 실제 description이나 관련 키워드로 확장
                priority_keywords = self._expand_priority_to_keywords(priority_data)
                for keyword in priority_keywords:
                    priority_tags.append({
                        'tag': keyword,
                        'weight': 10.0  # 최고 우선순위 - 다른 태그보다 압도적으로 높게
                    })
            
            # 4. 추가 태그들을 우선순위에 따라 추가 (priority와 충돌하는 태그 제외)
            priority_category = self._get_category_from_priority(priority_data) if priority_data else None
            
            for idx, tag_row in enumerate(additional_tags):
                tag = tag_row['tag']
                original_weight = tag_row['weight']
                
                # Priority와 다른 카테고리 태그는 가중치를 크게 낮춤
                if priority_category and self._is_conflicting_tag(tag, priority_category):
                    # 충돌하는 태그는 가중치를 대폭 낮춤 (1.0)
                    weight = 1.0
                    logger.info(f"Conflicting tag '{tag}' weight reduced to 1.0 (priority: {priority_data})")
                else:
                    # 충돌하지 않는 태그는 기존 가중치 + 카테고리 가중치
                    base_weight = self._calculate_tag_category_weight(tag)
                    weight = min(base_weight + (original_weight * 0.5), 5.0)  # 최대 5.0 제한
                
                priority_tags.append({
                    'tag': tag,
                    'weight': weight
                })
                
                # 너무 많은 태그는 성능에 악영향 - 상위 12개만
                if len(priority_tags) >= 12:
                    break
            
            # 5. 기본 태그가 없으면 빈 리스트 반환
            if not priority_tags:
                return []
                
            return priority_tags
                
        except Exception as e:
            logger.error(f"Error getting user priority tags: {e}")
            return []
        finally:
            await conn.close()
    
    def _calculate_tag_category_weight(self, tag: str) -> float:
        """태그 카테고리별 가중치 계산"""
        # 여행 우선순위 관련 태그들 (높은 가중치)
        high_priority_tags = {
            '쇼핑', '면세점', '백화점', '쇼핑몰', '특산물', '구매',
            '숙박', '호텔', '리조트', '펜션', '휴양시설', 
            '맛집', '음식', '레스토랑', '카페',
            '체험', '액티비티', '레포츠'
        }
        
        # 장소/지역 관련 태그들 (중간 가중치)
        medium_priority_tags = {
            '자연', '바다', '산', '공원',
            '문화', '역사', '박물관', '명소',
            '핫플레이스', '유명관광지', '인기명소', '필수코스'
        }
        
        # 서비스/품질 관련 태그들 (낮은 가중치)
        low_priority_tags = {
            '럭셔리', '고급', '최고급', '서비스', '편안함', '아늑함',
            '힐링', '평화', '휴식', '여유', '대중적'
        }
        
        if tag in high_priority_tags:
            return 4.0
        elif tag in medium_priority_tags:
            return 3.0
        elif tag in low_priority_tags:
            return 2.0
        else:
            return 1.5  # 기본 가중치
    
    def _expand_priority_to_keywords(self, priority: str) -> List[str]:
        """Priority를 관련 키워드로 확장"""
        priority_mappings = {
            'accommodation': ['숙박', '호텔', '리조트', '펜션', '숙소', '휴양시설', '편안함', '서비스'],
            'restaurants': ['맛집', '음식', '레스토랑', '카페', '식당', '요리', '미식', '식사'],
            'shopping': ['쇼핑', '면세점', '백화점', '쇼핑몰', '특산물', '구매', '상점', '시장'],
            'experience': ['체험', '액티비티', '레포츠', '모험', '활동', '경험', '즐거움', '재미']
        }
        
        return priority_mappings.get(priority, [priority])
    
    def _get_category_from_priority(self, priority: str) -> str:
        """Priority에서 카테고리 추출"""
        category_mapping = {
            'accommodation': 'accommodation',
            'restaurants': 'restaurants', 
            'shopping': 'shopping',
            'experience': 'experience'
        }
        return category_mapping.get(priority, priority)
    
    def _is_conflicting_tag(self, tag: str, priority_category: str) -> bool:
        """태그가 priority 카테고리와 충돌하는지 확인"""
        # 각 카테고리별 태그 정의
        category_tags = {
            'restaurants': ['쇼핑', '면세점', '백화점', '쇼핑몰', '시장', '아울렛', '구매', '상점', '특산물'],
            'shopping': ['맛집', '음식', '레스토랑', '카페', '식당', '요리', '미식', '식사'],
            'accommodation': ['쇼핑', '면세점', '백화점', '쇼핑몰', '시장', '아울렛', '맛집', '음식', '레스토랑'],
            'experience': ['쇼핑', '면세점', '백화점', '쇼핑몰', '시장', '아울렛', '맛집', '음식', '레스토랑']
        }
        
        conflicting_tags = category_tags.get(priority_category, [])
        return tag in conflicting_tags

    async def get_tag_vectors(self, tags: List[str]) -> Dict[str, np.ndarray]:
        """태그 벡터 가져오기 - BERT로 직접 인코딩"""
        tag_vectors = {}
        for tag in tags:
            # BERT로 직접 인코딩 (preference_tags 테이블 없이)
            tag_vectors[tag] = self.bert_model.encode([tag])[0].astype(np.float32)
        
        return tag_vectors

    async def get_user_vector(self, user_id: str) -> np.ndarray:
        """사용자 선호도 벡터 생성"""
        priority_tags = await self.get_user_priority_tags(user_id)
        
        if not priority_tags:
            # 기본 벡터 반환
            return np.random.normal(0, 0.1, 384).astype(np.float32)
        
        # 태그별 벡터 가져오기
        tag_names = [tag_info['tag'] for tag_info in priority_tags]
        tag_vectors = await self.get_tag_vectors(tag_names)
        
        # 가중치 적용하여 사용자 벡터 생성
        weighted_vectors = []
        for tag_info in priority_tags:
            tag = tag_info['tag']
            weight = tag_info['weight']
            
            if tag in tag_vectors:
                # 가중치만큼 벡터를 반복 추가
                repeat_count = int(weight)
                for _ in range(repeat_count):
                    weighted_vectors.append(tag_vectors[tag])
        
        if weighted_vectors:
            # 평균 벡터 계산
            user_vector = np.mean(weighted_vectors, axis=0)
        else:
            user_vector = np.random.normal(0, 0.1, 384).astype(np.float32)
        
        return user_vector.astype(np.float32)

    async def get_user_preferences(self, user_id: str) -> Dict:
        """사용자 선호도 가져오기 (추천 시스템용)"""
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
                ORDER BY created_at ASC
            """, user_id)
            
            # 우선순위 태그 가져오기
            priority_tags = await self.get_user_priority_tags(user_id)
            
            return {
                'basic': dict(basic_prefs) if basic_prefs else None,
                'tags': priority_tags,  # 우선순위가 적용된 태그
                'original_tags': [dict(tag) for tag in tag_prefs] if tag_prefs else []
            }
            
        finally:
            await conn.close()

    async def get_fallback_places(self, limit: int = 20) -> List[Dict]:
        """개인화 추천 실패시 인기도 기반 장소 반환"""
        conn = await asyncpg.connect(self.db_url)
        try:
            query = """
                SELECT place_id, table_name, name, region, city, latitude, longitude, 
                       overview as description, image_urls,
                       random() as similarity_score
                FROM place_recommendations pr
                WHERE pr.name IS NOT NULL 
                  AND pr.overview IS NOT NULL 
                  AND pr.image_urls IS NOT NULL 
                  AND pr.image_urls != 'null'::jsonb
                ORDER BY random()
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
                    'similarity_score': 0.7 + (place.get('popularity_score', 0) * 0.1)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in fallback places: {str(e)}")
            return []
        finally:
            await conn.close()

    async def get_personalized_recommendations(
        self, 
        user_id: str, 
        region: str = None, 
        category: str = None, 
        limit: int = 20
    ) -> List[Dict]:
        """개인화 추천 - 벡터 코사인 유사도 기반"""
        conn = await asyncpg.connect(self.db_url)
        try:
            # 사용자 벡터 생성
            user_vector = await self.get_user_vector(user_id)
            
            # place_recommendations에서 장소 데이터 가져오기
            query = """
                SELECT place_id, table_name, name, region, city, 
                       latitude, longitude, overview as description, 
                       image_urls, vector
                FROM place_recommendations
                WHERE vector IS NOT NULL
            """
            params = []
            param_count = 0
            
            # 필터 조건 추가
            if region:
                param_count += 1
                query += f" AND region = ${param_count}"
                params.append(region)
            
            if category:
                param_count += 1
                query += f" AND table_name = ${param_count}"
                params.append(category)
            
            query += " ORDER BY random() LIMIT 2000"  # 성능을 위해 2000개로 제한
            
            places = await conn.fetch(query, *params)
            
            if not places:
                return []
            
            # 벡터 추출 및 코사인 유사도 계산
            place_vectors = []
            valid_places = []
            
            for place in places:
                try:
                    if isinstance(place['vector'], str):
                        vector_data = json.loads(place['vector'])
                    else:
                        vector_data = place['vector']
                    
                    vector_array = np.array(vector_data, dtype=np.float32)
                    if len(vector_array) == 384:  # 올바른 차원인지 확인
                        place_vectors.append(vector_array)
                        valid_places.append(place)
                except:
                    continue
            
            if not place_vectors:
                return []
            
            # 배치로 코사인 유사도 계산
            place_vectors = np.array(place_vectors)
            similarities = cosine_similarity(user_vector.reshape(1, -1), place_vectors)
            similarity_scores = similarities.flatten()
            
            # 결과 생성
            results = []
            for i, place in enumerate(valid_places):
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
                    'similarity_score': float(similarity_scores[i])
                })
            
            # 유사도 순으로 정렬 후 상위 반환
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return results[:limit]
        finally:
            await conn.close()

    async def get_popular_places(self, region: str = None, category: str = None, limit: int = 20) -> List[Dict]:
        """인기 장소 추천"""
        conn = await asyncpg.connect(self.db_url)
        try:
            query = """
                SELECT place_id, table_name, name, region, city,
                       latitude, longitude, overview as description, image_urls,
                       0.7 as similarity_score
                FROM place_recommendations
                WHERE name IS NOT NULL AND overview IS NOT NULL
            """
            params = []
            param_count = 0
            
            if region:
                param_count += 1
                query += f" AND region = ${param_count}"
                params.append(region)
            
            if category:
                param_count += 1
                query += f" AND table_name = ${param_count}"
                params.append(category)
            
            query += " ORDER BY random() LIMIT $" + str(param_count + 1)
            params.append(limit)
            
            places = await conn.fetch(query, *params)
            
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
                    'similarity_score': place['similarity_score']
                })
            
            return results
        finally:
            await conn.close()