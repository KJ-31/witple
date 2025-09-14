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


# ============================================================================
# 🚀 ENHANCED RECOMMENDATION SYSTEM (팀 검토 후 적용)
# ============================================================================

"""
# 개선된 추천 알고리즘 - Phase 1: 즉시 구현 가능한 고도화

import math
from datetime import datetime, timedelta
from typing import Optional

# 1. 가중치 기반 점수 시스템
ACTION_WEIGHTS = {
    'click': 1.0,      # 기본 관심도 (가장 많은 데이터)
    'like': 3.0,       # 3배 가중치 (긍정적 반응)
    'bookmark': 5.0    # 5배 가중치 (강한 선호, 재방문 의도)
}

def calculate_weighted_popularity_score(place_data: Dict) -> float:
    '''가중치 기반 인기도 점수 계산'''
    weighted_score = (
        place_data.get('total_clicks', 0) * ACTION_WEIGHTS['click'] +
        place_data.get('total_likes', 0) * ACTION_WEIGHTS['like'] + 
        place_data.get('total_bookmarks', 0) * ACTION_WEIGHTS['bookmark']
    )
    
    # 정규화 (0-100 스케일)
    # 기준: click 50개 + like 10개 + bookmark 5개 = 100점
    max_reference_score = (50 * 1.0) + (10 * 3.0) + (5 * 5.0)  # = 105
    normalized_score = min((weighted_score / max_reference_score) * 100, 100)
    
    return round(normalized_score, 2)

def calculate_engagement_score(place_data: Dict) -> float:
    '''참여도 점수 계산 (액션의 질 중심)'''
    total_actions = (place_data.get('total_clicks', 0) + 
                    place_data.get('total_likes', 0) + 
                    place_data.get('total_bookmarks', 0))
    
    if total_actions == 0:
        return 0.0
    
    # 높은 가중치 액션 비율
    high_value_actions = place_data.get('total_likes', 0) + place_data.get('total_bookmarks', 0)
    engagement_ratio = high_value_actions / total_actions
    
    # 참여도 점수 (비율 * 100 + 절대값 보정)
    base_engagement = engagement_ratio * 100
    
    # 절대값 보정 (최소한의 like/bookmark이 있어야 높은 점수)
    min_threshold_bonus = min(high_value_actions * 5, 20)  # 최대 20점 보너스
    
    return min(base_engagement + min_threshold_bonus, 100)

# 2. 시간 감쇄 함수 (Temporal Decay)
def calculate_time_decay_weight(action_date: datetime, decay_rate: float = 0.02) -> float:
    '''시간 감쇄 가중치 계산'''
    if action_date is None:
        return 0.5  # 기본값
    
    days_ago = (datetime.now() - action_date).days
    
    # 지수 감쇄: e^(-decay_rate * days)
    # decay_rate = 0.02 기준으로 약 35일 후 50% 가중치
    weight = math.exp(-decay_rate * days_ago)
    
    return max(weight, 0.1)  # 최소 10% 가중치는 유지

def calculate_time_weighted_popularity(actions_data: List[Dict]) -> float:
    '''시간 가중치 적용된 인기도 계산'''
    total_weighted_score = 0
    
    for action in actions_data:
        base_weight = ACTION_WEIGHTS[action['action_type']]
        time_weight = calculate_time_decay_weight(action['created_at'])
        
        total_weighted_score += base_weight * time_weight
    
    return total_weighted_score

# 3. 벡터 기반 추천 엔진 (새로운 행동 벡터 활용)
class VectorBasedRecommendationEngine:
    '''AWS Batch에서 생성된 사용자/장소 벡터를 활용한 추천 엔진'''
    
    def __init__(self):
        self.db_url = settings.DATABASE_URL
        logger.info("🤖 VectorBasedRecommendationEngine initialized")
    
    async def get_user_behavior_vector(self, user_id: str) -> Optional[np.ndarray]:
        '''사용자 행동 벡터 가져오기'''
        conn = await asyncpg.connect(self.db_url)
        try:
            vector_data = await conn.fetchrow('''
                SELECT behavior_vector, like_score, bookmark_score, click_score, 
                       total_actions, vector_updated_at
                FROM user_behavior_vectors 
                WHERE user_id = $1
            ''', user_id)
            
            if not vector_data or not vector_data['behavior_vector']:
                logger.info(f"No behavior vector found for user {user_id}")
                return None
                
            # PostgreSQL ARRAY를 numpy array로 변환
            vector = np.array(vector_data['behavior_vector'], dtype=np.float32)
            
            if len(vector) != 384:
                logger.warning(f"Invalid vector dimension for user {user_id}: {len(vector)}")
                return None
                
            logger.info(f"✅ User behavior vector loaded: {user_id} (actions: {vector_data['total_actions']})")
            return vector
            
        except Exception as e:
            logger.error(f"❌ Error loading user vector {user_id}: {str(e)}")
            return None
        finally:
            await conn.close()
    
    async def get_place_vectors_enhanced(self, category: str = None, limit: int = 1000) -> List[Dict[str, Any]]:
        '''향상된 장소 벡터 데이터 가져오기 (가중치 점수 포함)'''
        conn = await asyncpg.connect(self.db_url)
        try:
            query = '''
                SELECT pv.place_id, pv.place_category, pv.combined_vector,
                       pv.popularity_score, pv.engagement_score,
                       pv.total_likes, pv.total_bookmarks, pv.total_clicks,
                       pv.vector_updated_at,
                       pr.name, pr.region, pr.city, pr.latitude, pr.longitude,
                       pr.overview as description, pr.image_urls
                FROM place_vectors pv
                LEFT JOIN place_recommendations pr ON pv.place_id = pr.place_id
                WHERE pv.combined_vector IS NOT NULL
            '''
            params = []
            
            if category:
                query += " AND pv.place_category = $1"
                params.append(category)
            
            query += f" ORDER BY pv.popularity_score DESC LIMIT {limit}"
            
            places = await conn.fetch(query, *params)
            
            results = []
            for place in places:
                if not place['combined_vector']:
                    continue
                    
                try:
                    vector = np.array(place['combined_vector'], dtype=np.float32)
                    if len(vector) != 384:
                        continue
                    
                    # 개선된 점수 계산 적용
                    place_data = {
                        'total_clicks': place['total_clicks'] or 0,
                        'total_likes': place['total_likes'] or 0, 
                        'total_bookmarks': place['total_bookmarks'] or 0
                    }
                    
                    enhanced_popularity = calculate_weighted_popularity_score(place_data)
                    enhanced_engagement = calculate_engagement_score(place_data)
                    
                    results.append({
                        'place_id': place['place_id'],
                        'place_category': place['place_category'],
                        'vector': vector,
                        'popularity_score': enhanced_popularity,  # 개선된 점수 사용
                        'engagement_score': enhanced_engagement,  # 개선된 점수 사용
                        'legacy_popularity': float(place['popularity_score'] or 0),  # 기존 점수 보존
                        'legacy_engagement': float(place['engagement_score'] or 0),  # 기존 점수 보존
                        'total_interactions': place_data['total_clicks'] + place_data['total_likes'] + place_data['total_bookmarks'],
                        'name': place['name'] or '이름 없음',
                        'region': place['region'] or '지역 미상',
                        'city': place['city'],
                        'latitude': float(place['latitude']) if place['latitude'] else 0.0,
                        'longitude': float(place['longitude']) if place['longitude'] else 0.0,
                        'description': place['description'] or '설명 없음',
                        'image_urls': place['image_urls'],
                        'vector_updated_at': place['vector_updated_at']
                    })
                except Exception as e:
                    logger.warning(f"Failed to process place {place['place_id']}: {str(e)}")
                    continue
            
            logger.info(f"✅ Loaded {len(results)} enhanced place vectors")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error loading enhanced place vectors: {str(e)}")
            return []
        finally:
            await conn.close()
    
    async def get_vector_based_recommendations_enhanced(
        self, 
        user_id: str, 
        category: str = None, 
        region: str = None,
        limit: int = 20,
        diversity_boost: float = 0.1,
        use_time_decay: bool = True
    ) -> List[Dict[str, Any]]:
        '''향상된 벡터 기반 개인화 추천'''
        
        # 1. 사용자 행동 벡터 가져오기
        user_vector = await self.get_user_behavior_vector(user_id)
        if user_vector is None:
            logger.info(f"No user vector available for {user_id}, falling back to enhanced popular recommendations")
            return await self.get_enhanced_popular_recommendations(category=category, region=region, limit=limit)
        
        # 2. 장소 벡터들 가져오기 (향상된 점수 포함)
        places = await self.get_place_vectors_enhanced(category=category)
        if not places:
            logger.warning("No place vectors available")
            return []
        
        # 3. 지역 필터링 (필요한 경우)
        if region:
            places = [p for p in places if p['region'] == region]
        
        if not places:
            logger.info(f"No places found for region: {region}")
            return []
        
        # 4. 벡터 유사도 계산
        place_vectors = np.array([p['vector'] for p in places])
        similarities = cosine_similarity(user_vector.reshape(1, -1), place_vectors).flatten()
        
        # 5. 향상된 하이브리드 스코어 계산
        results = []
        for i, place in enumerate(places):
            similarity = float(similarities[i])
            
            # 향상된 점수 사용 (가중치 반영됨)
            popularity_norm = min(place['popularity_score'] / 100.0, 1.0)
            engagement_norm = min(place['engagement_score'] / 100.0, 1.0)
            
            # 시간 가중치 (벡터 업데이트 최신성)
            time_weight = 1.0
            if use_time_decay and place['vector_updated_at']:
                time_weight = calculate_time_decay_weight(place['vector_updated_at'], decay_rate=0.01)
            
            # 향상된 하이브리드 점수: 벡터 유사도 + 가중치 기반 점수 + 시간 감쇄
            hybrid_score = (
                similarity * 0.6 +              # 벡터 유사도 60%
                popularity_norm * 0.25 +        # 가중치 기반 인기도 25%
                engagement_norm * 0.15          # 가중치 기반 참여도 15%
            ) * time_weight                     # 시간 감쇄 적용
            
            # 다양성 부스팅 (중간 인기도 장소 혜택)
            if 20 <= place['popularity_score'] <= 70:
                hybrid_score += diversity_boost
            
            results.append({
                'place_id': place['place_id'],
                'place_category': place['place_category'],
                'name': place['name'],
                'region': place['region'],
                'city': place['city'],
                'latitude': place['latitude'],
                'longitude': place['longitude'],
                'description': place['description'],
                'image_urls': place['image_urls'],
                'similarity_score': similarity,
                'popularity_score': place['popularity_score'],  # 향상된 점수
                'engagement_score': place['engagement_score'],  # 향상된 점수
                'hybrid_score': hybrid_score,
                'time_weight': time_weight,
                'recommendation_type': 'enhanced_vector_based'
            })
        
        # 6. 하이브리드 점수로 정렬
        results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # 7. 다양성 필터링 적용
        filtered_results = self.apply_diversity_filter(results, similarity_threshold=0.95)
        
        logger.info(f"✅ Generated {len(filtered_results[:limit])} enhanced vector-based recommendations for user {user_id}")
        return filtered_results[:limit]
    
    async def get_enhanced_popular_recommendations(
        self, 
        category: str = None, 
        region: str = None, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        '''향상된 인기 기반 추천 (벡터가 없을 때)'''
        places = await self.get_place_vectors_enhanced(category=category, limit=500)
        
        if region:
            places = [p for p in places if p['region'] == region]
        
        # 향상된 점수 기반으로 정렬
        for place in places:
            # 가중치 기반 점수 + 참여도 조합
            place['hybrid_score'] = (place['popularity_score'] * 0.7) + (place['engagement_score'] * 0.3)
            place['similarity_score'] = 0.5  # 기본값
            place['recommendation_type'] = 'enhanced_popular'
        
        places.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        return places[:limit]
    
    def apply_diversity_filter(self, places: List[Dict], similarity_threshold: float = 0.95) -> List[Dict]:
        '''다양성 필터링 (카테고리/지역 다양성 확보)'''
        if len(places) <= 10:
            return places
        
        filtered = []
        category_count = {}
        region_count = {}
        max_per_category = max(len(places) // 4, 2)  # 카테고리당 최대 개수
        max_per_region = max(len(places) // 3, 3)    # 지역당 최대 개수
        
        for place in places:
            category = place.get('place_category', 'unknown')
            region = place.get('region', 'unknown')
            
            # 카테고리/지역 제한 확인
            if (category_count.get(category, 0) < max_per_category and 
                region_count.get(region, 0) < max_per_region):
                
                filtered.append(place)
                category_count[category] = category_count.get(category, 0) + 1
                region_count[region] = region_count.get(region, 0) + 1
        
        # 빈 자리는 높은 점수 순으로 채움
        remaining_slots = len(places) - len(filtered)
        if remaining_slots > 0:
            remaining_places = [p for p in places if p not in filtered]
            filtered.extend(remaining_places[:remaining_slots])
        
        return filtered

# 4. 하이브리드 추천 엔진 (기존 + 새로운 시스템 결합)
class HybridRecommendationEngine:
    '''기존 태그 기반 + 새로운 벡터 기반 추천을 결합하는 엔진'''
    
    def __init__(self):
        self.legacy_engine = RecommendationEngine()  # 기존 태그 기반
        self.vector_engine = VectorBasedRecommendationEngine()  # 새로운 행동 기반
        logger.info("🚀 HybridRecommendationEngine initialized")
        
    async def get_hybrid_recommendations(
        self, 
        user_id: str, 
        region: str = None, 
        category: str = None, 
        limit: int = 20,
        algorithm: str = 'balanced'  # 'vector_heavy', 'tag_heavy', 'balanced'
    ) -> List[Dict]:
        '''하이브리드 추천 결과 생성'''
        
        # 알고리즘별 가중치 설정
        algorithm_weights = {
            'vector_heavy': {'vector': 0.8, 'tag': 0.2},
            'tag_heavy': {'vector': 0.3, 'tag': 0.7}, 
            'balanced': {'vector': 0.6, 'tag': 0.4}
        }
        weights = algorithm_weights.get(algorithm, algorithm_weights['balanced'])
        
        # 1. 사용자 행동 벡터 존재 여부 확인
        has_behavior_vector = await self.vector_engine.get_user_behavior_vector(user_id) is not None
        
        if has_behavior_vector:
            # 2-A. 행동 데이터 있는 경우: 벡터 + 태그 결합
            vector_results = await self.vector_engine.get_vector_based_recommendations_enhanced(
                user_id, category, region, limit * 2  # 2배로 가져와서 다양성 확보
            )
            tag_results = await self.legacy_engine.get_personalized_recommendations(
                user_id, region, category, limit
            )
            
            # 하이브리드 점수 계산 및 결합
            hybrid_results = self.combine_recommendations(vector_results, tag_results, weights)
            
        else:
            # 2-B. 행동 데이터 없는 경우: 태그 기반 + 향상된 인기도
            tag_results = await self.legacy_engine.get_personalized_recommendations(
                user_id, region, category, limit * 1.5
            )
            popular_results = await self.vector_engine.get_enhanced_popular_recommendations(
                category, region, limit // 2
            )
            
            # 태그 중심 결합
            hybrid_results = self.combine_recommendations(tag_results, popular_results, {
                'primary': 0.8,
                'secondary': 0.2
            })
        
        # 3. 최종 다양성 필터링 적용
        diversified_results = self.vector_engine.apply_diversity_filter(hybrid_results)
        
        # 4. 최종 점수로 정렬
        final_results = sorted(diversified_results, key=lambda x: x.get('hybrid_score', 0), reverse=True)
        
        logger.info(f"✅ Generated {len(final_results[:limit])} hybrid recommendations for user {user_id} (algorithm: {algorithm})")
        return final_results[:limit]

    def combine_recommendations(
        self, 
        primary_results: List[Dict], 
        secondary_results: List[Dict], 
        weights: Dict[str, float]
    ) -> List[Dict]:
        '''두 추천 결과를 가중치로 결합'''
        
        # 장소 ID별로 그룹화
        place_scores = {}
        
        # Primary 결과 처리
        primary_weight = list(weights.values())[0]
        for i, place in enumerate(primary_results):
            place_id = place['place_id']
            # 순위 기반 점수 (1위: 1.0, 마지막: 0.1)
            rank_score = 1.0 - (i / len(primary_results)) * 0.9
            
            place_scores[place_id] = {
                'place_data': place,
                'primary_score': rank_score * primary_weight,
                'secondary_score': 0.0
            }
        
        # Secondary 결과 처리  
        secondary_weight = list(weights.values())[1]
        for i, place in enumerate(secondary_results):
            place_id = place['place_id']
            rank_score = 1.0 - (i / len(secondary_results)) * 0.9
            
            if place_id in place_scores:
                place_scores[place_id]['secondary_score'] = rank_score * secondary_weight
            else:
                place_scores[place_id] = {
                    'place_data': place,
                    'primary_score': 0.0,
                    'secondary_score': rank_score * secondary_weight
                }
        
        # 하이브리드 점수 계산
        hybrid_results = []
        for place_id, scores in place_scores.items():
            hybrid_score = scores['primary_score'] + scores['secondary_score']
            
            result = {
                **scores['place_data'],
                'hybrid_score': hybrid_score,
                'primary_score': scores['primary_score'],
                'secondary_score': scores['secondary_score'],
                'recommendation_source': 'hybrid'
            }
            hybrid_results.append(result)
        
        return hybrid_results

# 사용 예시 (라우터에서 적용)
# hybrid_engine = HybridRecommendationEngine()
# recommendations = await hybrid_engine.get_hybrid_recommendations(
#     user_id=user.user_id,
#     region=region,
#     category=category, 
#     limit=limit,
#     algorithm='balanced'  # 'vector_heavy', 'tag_heavy', 'balanced'
# )
"""