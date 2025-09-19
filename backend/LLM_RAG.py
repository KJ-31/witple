"""
하이브리드 검색 최적화 RAG (Retrieval-Augmented Generation) 시스템
PostgreSQL + PGVector + LangChain + Amazon Bedrock 기반

작성일: 2025년
목적: SQL 필터링 + 벡터 유사도를 결합한 고성능 여행지 추천 시스템 (Amazon Bedrock 버전)
"""

import boto3
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_postgres import PGVector
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from typing import List, Any, Literal, TypedDict, Sequence, Optional
from sqlalchemy import create_engine, text
from database import engine as shared_engine
from cache_utils import RedisCache
import sys
import os
import json
import re
import requests
import datetime
import hashlib
import redis
from functools import wraps

# AWS 설정 (환경변수 또는 AWS CLI 설정 사용)
AWS_REGION = os.getenv('AWS_REGION')  # Bedrock이 지원되는 리전 (서울)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# AWS 세션 생성
try:
    boto3_session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
except Exception as e:
    print(f"⚠️ AWS 세션 생성 실패: {e}")
    boto3_session = None

# # 설정 및 초기화
# 데이터베이스 연결 설정 (Redis 우선, PGVector 폴백)
DB_ENABLED = True  # Redis 캐시 우선 + PGVector 폴백

# Redis 캐싱 설정
print("🔗 Redis 캐싱 시스템 초기화 중...")
redis_available = False
try:
    # 환경변수 직접 사용 + 오류 처리 강화
    redis_url = os.getenv('REDIS_URL')
    redis_client = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True
    )
    # 연결 테스트
    redis_client.ping()
    redis_available = True
    print("✅ Redis 연결 성공!")
except Exception as e:
    print(f"⚠️ Redis 연결 실패: {e}")
    redis_client = None
    redis_available = False

class LLMCache:
    """LLM 응답 전용 캐싱 시스템"""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.enabled = redis_client is not None
        print(f"🧠 LLM 캐시 {'활성화' if self.enabled else '비활성화'}")

    def _generate_cache_key(self, query: str, cache_type: str = "response") -> str:
        """쿼리 기반 캐시 키 생성"""
        # 쿼리 정규화 (공백, 대소문자, 특수문자 처리)
        normalized_query = re.sub(r'\s+', ' ', query.strip().lower())
        normalized_query = re.sub(r'[^\w\s가-힣]', '', normalized_query)

        # 해시 생성
        query_hash = hashlib.md5(normalized_query.encode('utf-8')).hexdigest()[:12]
        return f"llm:{cache_type}:{query_hash}"

    def get_cached_response(self, query: str) -> Optional[str]:
        """캐시된 LLM 응답 조회"""
        if not self.enabled:
            return None

        try:
            cache_key = self._generate_cache_key(query)
            cached_data = self.redis.get(cache_key)

            if cached_data:
                print(f"🎯 캐시 히트: {cache_key}")
                return cached_data
            else:
                print(f"❌ 캐시 미스: {cache_key}")
                return None

        except Exception as e:
            print(f"⚠️ 캐시 조회 오류: {e}")
            return None

    def cache_response(self, query: str, response: str, expire: int = 3600) -> bool:
        """LLM 응답 캐싱 (1시간 기본)"""
        if not self.enabled or not response:
            return False

        try:
            cache_key = self._generate_cache_key(query)
            success = self.redis.set(cache_key, response, ex=expire)

            if success:
                print(f"💾 응답 캐시 저장: {cache_key}")

            return success

        except Exception as e:
            print(f"⚠️ 캐시 저장 오류: {e}")
            return False

    def cache_search_results(self, query: str, docs: List[Document], expire: int = 1800) -> bool:
        """검색 결과 캐싱 (30분)"""
        if not self.enabled:
            return False

        try:
            cache_key = self._generate_cache_key(query, "search")

            # Document 객체를 직렬화 가능한 형태로 변환
            serializable_docs = []
            for doc in docs:
                serializable_docs.append({
                    'page_content': doc.page_content,
                    'metadata': doc.metadata
                })

            docs_json = json.dumps(serializable_docs, ensure_ascii=False)
            success = self.redis.set(cache_key, docs_json, ex=expire)

            if success:
                print(f"🔍 검색 결과 캐시 저장: {cache_key}")

            return success

        except Exception as e:
            print(f"⚠️ 검색 캐시 저장 오류: {e}")
            return False

    def get_cached_search_results(self, query: str) -> Optional[List[Document]]:
        """캐시된 검색 결과 조회"""
        if not self.enabled:
            return None

        try:
            cache_key = self._generate_cache_key(query, "search")
            cached_data = self.redis.get(cache_key)

            if cached_data:
                print(f"🔍 검색 캐시 히트: {cache_key}")

                # JSON을 Document 객체로 복원
                docs_data = json.loads(cached_data)
                docs = []
                for doc_data in docs_data:
                    doc = Document(
                        page_content=doc_data['page_content'],
                        metadata=doc_data['metadata']
                    )
                    docs.append(doc)

                return docs

            return None

        except Exception as e:
            print(f"⚠️ 검색 캐시 조회 오류: {e}")
            return None

    def get_cache_stats(self) -> dict:
        """캐시 통계 조회"""
        if not self.enabled:
            return {"enabled": False}

        try:
            # Redis INFO 명령으로 통계 조회
            info = self.redis.info()

            # LLM 관련 키 개수 조회
            llm_keys = self.redis.keys("llm:*")

            return {
                "enabled": True,
                "total_keys": len(llm_keys),
                "memory_usage": info.get('used_memory_human', 'N/A'),
                "connected_clients": info.get('connected_clients', 0),
                "cache_hit_ratio": "추후 구현"  # 별도 모니터링 필요
            }

        except Exception as e:
            return {"enabled": True, "error": str(e)}

    def preload_region_documents(self, region: str, expire: int = 7200) -> bool:
        """지역별 문서 사전 로딩 (2시간 캐시)"""
        if not self.enabled:
            return False

        try:
            cache_key = f"llm:region:{region}"

            # 이미 캐시되어 있으면 건너뛰기
            if self.redis.exists(cache_key):
                print(f"📦 지역 캐시 존재: {region}")
                return True

            # DB에서 해당 지역의 모든 문서 조회
            engine = shared_engine
            with engine.connect() as conn:
                query = text("""
                    SELECT document, cmetadata
                    FROM langchain_pg_embedding
                    WHERE cmetadata->>'region' = :region
                    LIMIT 500
                """)
                result = conn.execute(query, {"region": region})

                documents = []
                for row in result:
                    documents.append({
                        'page_content': row.document,
                        'metadata': json.loads(row.cmetadata) if row.cmetadata else {}
                    })

                if documents:
                    docs_json = json.dumps(documents, ensure_ascii=False)
                    success = self.redis.set(cache_key, docs_json, ex=expire)
                    print(f"🏗️ 지역 캐시 생성: {region} ({len(documents)}개 문서)")
                    return success

        except Exception as e:
            print(f"⚠️ 지역 캐시 오류: {e}")
            return False

    def get_region_documents(self, region: str) -> List[Document]:
        """지역별 캐시된 문서 조회"""
        if not self.enabled:
            return []

        try:
            cache_key = f"llm:region:{region}"
            cached_data = self.redis.get(cache_key)

            if cached_data:
                print(f"🎯 지역 캐시 히트: {region}")
                docs_data = json.loads(cached_data)
                return [Document(page_content=doc['page_content'], metadata=doc['metadata'])
                       for doc in docs_data]

        except Exception as e:
            print(f"⚠️ 지역 캐시 조회 오류: {e}")

        return []

    def preload_popular_documents(self, expire: int = 3600) -> bool:
        """인기 문서 사전 로딩 (1시간 캐시)"""
        if not self.enabled:
            return False

        try:
            cache_key = "llm:hot:popular"

            if self.redis.exists(cache_key):
                print("📦 인기 문서 캐시 존재")
                return True

            # 인기 문서 조회 (조회수, 추천수 기반)
            engine = shared_engine
            with engine.connect() as conn:
                query = text("""
                    SELECT document, cmetadata
                    FROM langchain_pg_embedding
                    ORDER BY (cmetadata->>'view_count')::int DESC NULLS LAST
                    LIMIT 100
                """)
                result = conn.execute(query)

                documents = []
                for row in result:
                    documents.append({
                        'page_content': row.document,
                        'metadata': json.loads(row.cmetadata) if row.cmetadata else {}
                    })

                if documents:
                    docs_json = json.dumps(documents, ensure_ascii=False)
                    success = self.redis.set(cache_key, docs_json, ex=expire)
                    print(f"🔥 인기 문서 캐시 생성: {len(documents)}개")
                    return success

        except Exception as e:
            print(f"⚠️ 인기 문서 캐시 오류: {e}")
            return False

# 전역 캐시 인스턴스
llm_cache = LLMCache(redis_client if redis_available else None)

# LLM 모델 설정 (Amazon Bedrock - Claude)
print("🤖 Amazon Bedrock Claude 모델 초기화 중...")
try:
    llm = ChatBedrock(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",      # Claude 3 Haiku
        # model_id="anthropic.claude-3-sonnet-20240229-v1:0",   # Claude 3 Sonnet
        # model_id="anthropic.claude-sonnet-4-20250514-v1:0",   # Claude 4 Sonnet
        region_name=AWS_REGION,
        credentials_profile_name=None,  # 기본 자격증명 사용
        model_kwargs={
            "temperature": 0.3,         # 약간 높여서 빠른 응답 (0.2 → 0.3)
            "max_tokens": 3000,         # 토큰 수 줄여서 속도 향상 (4000 → 2000)
            "top_p": 0.8,               # 더 제한적으로 선택해서 속도 향상
        }
    )
except Exception as e:
    print(f"❌ Bedrock LLM 초기화 실패: {e}")
    print("환경변수나 AWS CLI 설정을 확인해주세요.")
    sys.exit(1)

# 임베딩 모델 설정 - 안정적인 sentence-transformers 모델 사용
print("🧠 Sentence Transformers 임베딩 모델 초기화 중...")
embeddings = HuggingFaceEmbeddings(
    model_name='sentence-transformers/all-MiniLM-L12-v2',
)



# # 벡터스토어 연결 (Redis 캐시 우선 사용으로 비활성화)

print("🎯 Redis 캐시 우선 + PGVector 폴백 모드")
vectorstore = None
if DB_ENABLED:
    try:
        print("🔗 벡터스토어 연결 중...")
        vectorstore = PGVector(
            embeddings=embeddings,
            collection_name="place_recommendations",
            connection=os.getenv('DATABASE_URL'),
            pre_delete_collection=False,
        )
        print("✅ 벡터스토어 연결 완료 (Redis 우선, PGVector 폴백)")
    except Exception as e:
        print(f"⚠️ 벡터스토어 연결 실패: {e}")
        print("📢 Redis 캐시 전용 모드로 동작")
        vectorstore = None

# # 지역 및 키워드 인식 시스템

# 지역 및 키워드 데이터 (실제 DB 분석 결과 기반)
REGIONS = [
    '경기도', '서울특별시', '강원특별자치도', '경상남도', '경상북도', '전라남도', 
    '부산광역시', '충청남도', '제주특별자치도', '인천광역시', '전북특별자치도', 
    '충청북도', '대구광역시', '광주광역시', '대전광역시', '울산광역시', '세종특별자치시'
]

CITIES = [
    '중구', '평창군', '강남구', '서귀포시', '강릉시', '제주시', '고양시', '용인시', 
    '서구', '파주시', '안양시', '구로구', '경주시', '기장군', '가평군', '종로구', 
    '안동시', '영등포구', '수원시', '부산', '강릉', '제주', '서울', '경주', '가평'
]

CATEGORIES = [
    '한식', '쇼핑', '레포츠', '자연', '관광호텔', '펜션', '한옥', '게스트하우스', 
    '일식', '콘도미디엄', '카페', '모텔', '중식', '유스호스텔', '양식', '맛집'
]

# 음식 관련 키워드 확장
FOOD_KEYWORDS = ['맛집', '음식', '레스토랑', '식당', '먹거리', '요리', '카페', '디저트']

def extract_location_and_category(query: str):
    """쿼리에서 지역명과 카테고리를 정확히 추출"""
    query_lower = query.lower()
    
    found_regions = []
    found_cities = []
    found_categories = []
    
    # 도시-지역 매핑
    CITY_TO_REGION = {
        '강릉': '강원특별자치도', '강릉시': '강원특별자치도', 
        '평창군': '강원특별자치도',
        '부산': '부산광역시', '기장군': '부산광역시',
        '서울': '서울특별시', '강남구': '서울특별시', '종로구': '서울특별시', '영등포구': '서울특별시',
        '제주': '제주특별자치도', '제주시': '제주특별자치도', '서귀포시': '제주특별자치도',
        '수원시': '경기도', '고양시': '경기도', '용인시': '경기도', '파주시': '경기도', '안양시': '경기도', '가평군': '경기도', '가평': '경기도',
        '경주': '경상북도', '경주시': '경상북도', '안동시': '경상북도',
    }
    
    # 지역 매칭 (부분 문자열 포함)
    for region in REGIONS:
        if region in query or region.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '') in query:
            found_regions.append(region)
    
    # 도시 매칭
    for city in CITIES:
        if city in query:
            found_cities.append(city)
            # 도시에 해당하는 지역도 자동 추가
            if city in CITY_TO_REGION and CITY_TO_REGION[city] not in found_regions:
                found_regions.append(CITY_TO_REGION[city])
    
    # 카테고리 매칭
    for category in CATEGORIES:
        if category in query:
            found_categories.append(category)
    
    # 음식 키워드 특별 처리 - 더 포괄적으로
    if any(word in query for word in FOOD_KEYWORDS):
        found_categories.extend(['한식', '일식', '중식', '양식'])  # 모든 음식 카테고리 포함
    
    return found_regions, found_cities, found_categories

class HybridOptimizedRetriever(BaseRetriever):
    """SQL 필터링 + 벡터 유사도를 결합한 하이브리드 검색기"""
    
    vectorstore: Any = None
    k: int = 10000  # SQL 필터링으로 축소된 후보군에서 벡터 검색
    score_threshold: float = 0.5
    max_sql_results: int = 5000  # SQL 필터링 최대 결과 수
    
    def __init__(self, vectorstore, k: int = 10000, score_threshold: float = 0.5, max_sql_results: int = 5000):
        super().__init__(vectorstore=vectorstore, k=k, score_threshold=score_threshold, max_sql_results=max_sql_results)
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """하이브리드 검색: SQL 1차 필터링 + 벡터 2차 검색"""
        try:
            print(f"🔍 하이브리드 검색 쿼리: '{query}'")
            
            # 1단계: 지역/카테고리 추출
            regions, cities, categories = extract_location_and_category(query)
            print(f"   추출된 정보 - 지역: {regions}, 도시: {cities}, 카테고리: {categories}")
            
            # 2단계: SQL 기반 1차 필터링
            candidate_docs = self._sql_filter_candidates(query, regions, cities, categories)
            
            if not candidate_docs:
                print("⚠️ SQL 필터링 결과 없음, 순수 벡터 검색으로 폴백")
                return self._fallback_vector_search(query)
            
            print(f"📊 SQL 필터링: {len(candidate_docs)}개 후보 문서 선별")
            
            # 3단계: 선별된 후보군에 대해 벡터 유사도 계산
            final_docs = self._vector_search_on_candidates(query, candidate_docs)
            
            print(f"✅ 최종 결과: {len(final_docs)}개 문서 (임계값 ≥{self.score_threshold})")
            return final_docs
            
        except Exception as e:
            print(f"❌ HybridOptimizedRetriever 오류: {e}")
            return []
    
    def _sql_filter_candidates(self, query: str, regions: List[str], cities: List[str], categories: List[str]) -> List[Document]:
        """SQL 쿼리로 후보 문서들을 먼저 필터링"""
        try:
            engine = shared_engine
            
            # 조건이 없으면 최근 문서나 인기 문서로 제한
            if not regions and not cities and not categories:
                # 텍스트 검색으로 폴백
                return self._text_search_fallback(query, engine)
            
            # SQL 조건 구성
            conditions = []
            
            if regions:
                region_conditions = " OR ".join([f"cmetadata->>'region' ILIKE '%{region}%'" for region in regions])
                conditions.append(f"({region_conditions})")
            
            if cities:
                city_conditions = " OR ".join([f"cmetadata->>'city' ILIKE '%{city}%'" for city in cities])
                conditions.append(f"({city_conditions})")
            
            if categories:
                category_conditions = " OR ".join([f"cmetadata->>'category' ILIKE '%{category}%'" for category in categories])
                conditions.append(f"({category_conditions})")
            
            where_clause = " OR ".join(conditions)
            
            sql_query = f"""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding 
                WHERE {where_clause}
                LIMIT {self.max_sql_results}
            """
            
            print(f"🗄️ SQL 필터링 실행...")
            
            with engine.connect() as conn:
                result = conn.execute(text(sql_query))
                rows = result.fetchall()
                
                docs = []
                for row in rows:
                    doc = Document(
                        page_content=row.document,
                        metadata=row.cmetadata or {}
                    )
                    # 임베딩 정보도 저장 (벡터 검색용)
                    if row.embedding:
                        doc.metadata['_embedding'] = row.embedding
                    docs.append(doc)
                
                return docs
                
        except Exception as e:
            print(f"❌ SQL 필터링 오류: {e}")
            return []
    
    def _text_search_fallback(self, query: str, engine) -> List[Document]:
        """텍스트 기반 폴백 검색"""
        try:
            # 쿼리에서 키워드 추출하여 텍스트 검색
            keywords = query.split()
            text_conditions = []
            
            for keyword in keywords[:3]:  # 최대 3개 키워드만 사용
                if len(keyword) > 1:
                    text_conditions.append(f"document ILIKE '%{keyword}%'")
            
            if not text_conditions:
                return []
            
            text_where = " OR ".join(text_conditions)
            
            sql_query = f"""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding 
                WHERE {text_where}
                LIMIT {self.max_sql_results // 2}
            """
            
            with engine.connect() as conn:
                result = conn.execute(text(sql_query))
                rows = result.fetchall()
                
                docs = []
                for row in rows:
                    doc = Document(
                        page_content=row.document,
                        metadata=row.cmetadata or {}
                    )
                    if row.embedding:
                        doc.metadata['_embedding'] = row.embedding
                    docs.append(doc)
                
                return docs
                
        except Exception as e:
            print(f"❌ 텍스트 검색 폴백 오류: {e}")
            return []
    
    def _vector_search_on_candidates(self, query: str, candidate_docs: List[Document]) -> List[Document]:
        """선별된 후보 문서들에 대해 벡터 유사도 계산"""
        try:
            # 후보 문서들을 임시 벡터스토어나 직접 유사도 계산
            # 실제로는 후보 문서 ID들로 제한된 벡터 검색을 수행
            
            # 간단한 구현: 전체 벡터스토어에서 검색하되 결과를 후보와 매치
            all_docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=self.k)
            
            # 후보 문서의 내용으로 매칭 (실제로는 ID 기반 매칭이 더 효율적)
            candidate_contents = {doc.page_content for doc in candidate_docs}
            
            filtered_docs = []
            for doc, score in all_docs_with_scores:
                if doc.page_content in candidate_contents and score >= self.score_threshold:
                    # 유사도 점수를 metadata에 추가
                    doc.metadata['similarity_score'] = round(score, 3)
                    filtered_docs.append(doc)
                    
                    # 충분한 결과를 얻으면 중단 (성능 최적화)
                    if len(filtered_docs) >= 50:
                        break
            
            return filtered_docs
            
        except Exception as e:
            print(f"❌ 벡터 유사도 계산 오류: {e}")
            return []
    
    def _fallback_vector_search(self, query: str) -> List[Document]:
        """SQL 필터링 실패시 순수 벡터 검색"""
        try:
            print("🧠 순수 벡터 검색 실행...")
            docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=min(100, self.k))
            
            filtered_docs = []
            for doc, score in docs_with_scores:
                if score >= self.score_threshold:
                    doc.metadata['similarity_score'] = round(score, 3)
                    filtered_docs.append(doc)
            
            return filtered_docs
            
        except Exception as e:
            print(f"❌ 폴백 벡터 검색 오류: {e}")
            return []

# 하이브리드 최적화 Retriever 생성 (sentence-transformers 모델에 최적화된 임계값)
retriever = HybridOptimizedRetriever(vectorstore, k=32000, score_threshold=0.5, max_sql_results=5000)

# =============================================================================
# 프롬프트 템플릿 정의
# =============================================================================

rag_prompt = ChatPromptTemplate.from_template("""
당신은 여행 전문 어시스턴트입니다. 
주어진 여행지 정보를 바탕으로 사용자의 요청에 맞는 여행 일정을 작성해주세요.

여행지 정보:
{context}

사용자 질문: {question}

답변 지침:
1. 만약 여행지 정보가 "NO_RELEVANT_DATA"라면, 다음과 같이 답변하세요:
   "죄송합니다. 요청하신 '{question}'와 관련된 여행지 정보를 찾을 수 없습니다. 
   더 구체적인 지역명이나 다른 여행지로 다시 문의해 주시기 바랍니다."

2. 관련 여행지 정보가 있다면:
    - 실제 제공된 여행지 정보만을 활용하세요
    - 구체적인 장소명, 지역, 카테고리를 포함하세요
    - 사용자가 요청한 일정으로 구성해주세요
    - 점심, 저녁 시간을 생각하고 식사를 할 곳도 넣어주세요
    - 시간단위로 일정을 제공해주세요
    - 카테고리가 다르더라도 명소라 생각되면 답변해주세요
    - 중복된 추천은 반드시 제거해주세요
    - 한국어로 자연스럽게 작성하세요

답변:
""")

# # RAG 체인 구성

def format_docs(docs):
    """검색된 문서들을 텍스트로 포맷팅 (유사도 점수 포함)"""
    if not docs:
        return "NO_RELEVANT_DATA"  # 관련 데이터 없음을 나타내는 특별한 마커
    
    formatted_docs = []
    for i, doc in enumerate(docs, 1):
        # 유사도 점수 추출
        similarity_score = doc.metadata.get('similarity_score', 'N/A')
        content = f"[여행지 {i}] (유사도: {similarity_score})\n{doc.page_content}"
        
        if doc.metadata:
            meta_info = []
            for key, value in doc.metadata.items():
                if value and key not in ['original_id', 'similarity_score', '_embedding']:  # 내부 키 제외
                    meta_info.append(f"{key}: {value}")
            if meta_info:
                content += f"\n({', '.join(meta_info)})"
        formatted_docs.append(content)
    
    return "\n\n".join(formatted_docs)

# RAG 파이프라인 구성
rag_chain = (
    {
        "context": retriever | format_docs, 
        "question": RunnablePassthrough()
    }
    | rag_prompt
    | llm
    | StrOutputParser()
)

# # 주요 기능 함수들

def search_places(query):
    """여행지 검색 함수 (하이브리드 최적화 + Redis 캐싱)"""
    try:
        print(f"🔍 하이브리드 검색: '{query}'")

        # 캐시된 검색 결과 확인
        cached_docs = llm_cache.get_cached_search_results(query)
        if cached_docs:
            print("⚡ 캐시된 검색 결과 반환!")
            return cached_docs

        print("🔍 새로운 검색 실행...")

        # HybridOptimizedRetriever 직접 사용
        docs = retriever._get_relevant_documents(query)

        # 검색 결과 캐싱 (30분)
        llm_cache.cache_search_results(query, docs, expire=1800)

        return docs

    except Exception as e:
        print(f"❌ 검색 오류: {e}")
        return []

def get_travel_recommendation_optimized(query, stream=True):
    """최적화된 Redis 캐싱 + 스트림"""
    def _generate_stream():
        try:
            # 검색 단계는 항상 캐싱 활용
            cached_docs = llm_cache.get_cached_search_results(query)
            if cached_docs:
                docs = cached_docs
            else:
                docs = retriever._get_relevant_documents(query)
                llm_cache.cache_search_results(query, docs, expire=1800)

            context = format_docs(docs)
            prompt_value = rag_prompt.invoke({"context": context, "question": query})

            # 스트림 모드: yield로 실시간 응답
            full_response = ""
            buffer = ""
            for chunk in llm.stream(prompt_value):
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    if content:
                        buffer += content
                        full_response += content

                        # 적절한 청크로 yield
                        if len(buffer) > 15 or any(c in buffer for c in ['\n', '.']):
                            yield buffer
                            buffer = ""

            if buffer:
                yield buffer

            # 🎯 스트림 완료 후 전체 응답 캐싱
            if len(full_response) > 50:
                llm_cache.cache_response(query, full_response, expire=3600)

        except Exception as e:
            yield f"❌ 추천 생성 오류: {e}"

    try:
        if stream:
            return _generate_stream()
        else:
            # 비스트림: 캐시 확인 후 일반 처리
            cached_response = llm_cache.get_cached_response(query)
            if cached_response:
                return cached_response

            # 검색 단계는 항상 캐싱 활용
            cached_docs = llm_cache.get_cached_search_results(query)
            if cached_docs:
                docs = cached_docs
            else:
                docs = retriever._get_relevant_documents(query)
                llm_cache.cache_search_results(query, docs, expire=1800)

            context = format_docs(docs)
            prompt_value = rag_prompt.invoke({"context": context, "question": query})

            response = llm.invoke(prompt_value)
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            llm_cache.cache_response(query, response_text, expire=3600)
            return response_text

    except Exception as e:
        return f"❌ 추천 생성 오류: {e}"

def get_travel_recommendation(query, stream=True):
    """여행 추천 생성 함수 (스트림 지원 + Redis 캐싱)"""
    if stream:
        return get_travel_recommendation_optimized(query, stream=True)
    else:
        return get_travel_recommendation_optimized(query, stream=False)

def get_travel_recommendation_stream(query):
    """진짜 스트림 방식 여행 추천 생성 (터미널/웹 용)"""
    try:
        docs = retriever._get_relevant_documents(query)
        context = format_docs(docs)

        prompt_value = rag_prompt.invoke({"context": context, "question": query})

        # ▶️ 진짜 yield로 스트리밍
        buffer = ""
        full_response = ""
        for chunk in llm.stream(prompt_value):
            if hasattr(chunk, 'content'):
                content = chunk.content
            else:
                content = str(chunk)
            if content:
                buffer += content
                full_response += content
                # 자연스러운 스트리밍: 문장/줄/청크 단위로
                if len(buffer) > 15 or '\n' in buffer or '.' in buffer:
                    to_send, buffer = buffer, ""
                    yield to_send
        if buffer:
            yield buffer
    except Exception as e:
        yield f"❌ 스트림 추천 생성 오류: {e}"


async def get_travel_recommendation_stream_async(query):
    """비동기 스트림 방식 여행 추천 생성 (FastAPI 호환)"""
    import asyncio
    try:
        docs = retriever._get_relevant_documents(query)
        if len(docs) > 5:
            docs = docs[:5]
        context = format_docs(docs)
        prompt_value = rag_prompt.invoke({"context": context, "question": query})

        buffer = ""
        full_response = ""
        for chunk in llm.stream(prompt_value):
            if hasattr(chunk, 'content'):
                content = chunk.content
            else:
                content = str(chunk)
            if content:
                buffer += content
                full_response += content
                # 빠른 스트림 + 자연스러운 단위
                if len(buffer) > 15 or '\n' in buffer or '.' in buffer:
                    to_send, buffer = buffer, ""
                    yield to_send
                    await asyncio.sleep(0.02)
        if buffer:
            yield buffer
    except Exception as e:
        error_msg = f"❌ 비동기 스트림 추천 생성 오류: {e}"
        yield error_msg
        await asyncio.sleep(0.01)

# =============================================================================
# 기상청 API 관련 함수들
# =============================================================================

# 기상청 API 키 (환경변수에서 가져오기)
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')

def get_coordinates_for_region(region_name):
    """지역명을 기상청 API용 격자 좌표로 변환 (DB 기반 + 매핑)"""

    # 지역별 대표 좌표 매핑 (기상청 격자 좌표)
    region_coordinates = {
        # === 특별시/광역시/도 대표 좌표 ===
        '서울특별시': {'nx': 60, 'ny': 127},
        '서울': {'nx': 60, 'ny': 127},

        '부산광역시': {'nx': 98, 'ny': 76},
        '부산': {'nx': 98, 'ny': 76},

        '대구광역시': {'nx': 89, 'ny': 90},
        '대구': {'nx': 89, 'ny': 90},

        '인천광역시': {'nx': 55, 'ny': 124},
        '인천': {'nx': 55, 'ny': 124},

        '광주광역시': {'nx': 58, 'ny': 74},
        '광주': {'nx': 58, 'ny': 74},

        '대전광역시': {'nx': 67, 'ny': 100},
        '대전': {'nx': 67, 'ny': 100},

        '울산광역시': {'nx': 102, 'ny': 84},
        '울산': {'nx': 102, 'ny': 84},

        '세종특별자치시': {'nx': 66, 'ny': 103},
        '세종시': {'nx': 66, 'ny': 103},
        '세종': {'nx': 66, 'ny': 103},

        '경기도': {'nx': 60, 'ny': 121},  # 수원 기준
        '강원특별자치도': {'nx': 73, 'ny': 134},  # 춘천 기준
        '강원도': {'nx': 73, 'ny': 134},
        '충청북도': {'nx': 69, 'ny': 106},  # 청주 기준
        '충청남도': {'nx': 63, 'ny': 110},  # 천안 기준
        '전북특별자치도': {'nx': 63, 'ny': 89},  # 전주 기준
        '전라북도': {'nx': 63, 'ny': 89},
        '전라남도': {'nx': 58, 'ny': 74},  # 광주 기준
        '경상북도': {'nx': 89, 'ny': 90},  # 대구 기준
        '경상남도': {'nx': 90, 'ny': 77},  # 창원 기준
        '제주특별자치도': {'nx': 52, 'ny': 38},
        '제주도': {'nx': 52, 'ny': 38},
        '제주': {'nx': 52, 'ny': 38},

        # === 주요 도시 세부 좌표 ===
        # 서울 주요 구
        '강남구': {'nx': 61, 'ny': 126},
        '강남': {'nx': 61, 'ny': 126},
        '종로구': {'nx': 60, 'ny': 127},
        '종로': {'nx': 60, 'ny': 127},
        '마포구': {'nx': 59, 'ny': 126},
        '강북구': {'nx': 60, 'ny': 128},
        '강북': {'nx': 60, 'ny': 128},
        '송파구': {'nx': 62, 'ny': 126},
        '구로구': {'nx': 58, 'ny': 125},

        # 부산 주요 구
        '해운대구': {'nx': 99, 'ny': 75},
        '해운대': {'nx': 99, 'ny': 75},
        '사하구': {'nx': 96, 'ny': 76},
        '사하': {'nx': 96, 'ny': 76},
        '기장군': {'nx': 100, 'ny': 77},

        # 경기도 주요 도시
        '수원시': {'nx': 60, 'ny': 121},
        '수원': {'nx': 60, 'ny': 121},
        '성남시': {'nx': 63, 'ny': 124},
        '성남': {'nx': 63, 'ny': 124},
        '고양시': {'nx': 57, 'ny': 128},
        '고양': {'nx': 57, 'ny': 128},
        '용인시': {'nx': 64, 'ny': 119},
        '용인': {'nx': 64, 'ny': 119},
        '안양시': {'nx': 59, 'ny': 123},
        '안양': {'nx': 59, 'ny': 123},
        '파주시': {'nx': 56, 'ny': 131},
        '파주': {'nx': 56, 'ny': 131},
        '가평군': {'nx': 61, 'ny': 133},
        '가평': {'nx': 61, 'ny': 133},

        # 강원도 주요 도시
        '춘천시': {'nx': 73, 'ny': 134},
        '춘천': {'nx': 73, 'ny': 134},
        '강릉시': {'nx': 92, 'ny': 131},
        '강릉': {'nx': 92, 'ny': 131},
        '평창군': {'nx': 84, 'ny': 123},
        '평창': {'nx': 84, 'ny': 123},

        # 기타 주요 도시
        '경주시': {'nx': 100, 'ny': 91},
        '경주': {'nx': 100, 'ny': 91},
        '전주시': {'nx': 63, 'ny': 89},
        '전주': {'nx': 63, 'ny': 89},
        '여수시': {'nx': 73, 'ny': 66},
        '여수': {'nx': 73, 'ny': 66},
        '창원시': {'nx': 90, 'ny': 77},
        '창원': {'nx': 90, 'ny': 77},
        '제주시': {'nx': 53, 'ny': 38},
        '서귀포시': {'nx': 52, 'ny': 33},
        '서귀포': {'nx': 52, 'ny': 33},

        # 구 이름들 (중복 처리)
        '중구': {'nx': 60, 'ny': 127},  # 서울 기준
        '동구': {'nx': 68, 'ny': 100},  # 대전 기준
        '서구': {'nx': 67, 'ny': 100},  # 대전 기준
        '남구': {'nx': 58, 'ny': 74},   # 광주 기준
        '북구': {'nx': 59, 'ny': 75},   # 광주 기준
    }

    # 정확한 매치 시도
    if region_name in region_coordinates:
        return region_coordinates[region_name]

    # 부분 매치 시도 (지역명이 포함된 경우)
    for key, coords in region_coordinates.items():
        if region_name in key or key in region_name:
            return coords

    # 기본값 (서울)
    return {'nx': 60, 'ny': 127}

def get_db_regions_and_cities():
    """DB에서 실제 region과 city 데이터 추출"""
    try:
        from sqlalchemy import text

        engine = shared_engine
        with engine.connect() as conn:
            # Region 데이터 추출
            regions = []
            result = conn.execute(text("SELECT DISTINCT cmetadata->>'region' as region FROM langchain_pg_embedding WHERE cmetadata->>'region' IS NOT NULL AND cmetadata->>'region' != ''"))
            for row in result:
                if row[0]:  # 빈 문자열 제외
                    regions.append(row[0])

            # City 데이터 추출 (상위 100개)
            cities = []
            result = conn.execute(text("SELECT DISTINCT cmetadata->>'city' as city FROM langchain_pg_embedding WHERE cmetadata->>'city' IS NOT NULL AND cmetadata->>'city' != '' ORDER BY city LIMIT 100"))
            for row in result:
                if row[0]:  # 빈 문자열 제외
                    cities.append(row[0])

            return regions, cities
    except Exception as e:
        print(f"DB 연결 오류: {e}")
        # 기본값 반환
        return ['서울특별시', '부산광역시', '대구광역시'], ['서울', '부산', '대구']

def extract_region_from_context(state):
    """현재 대화 컨텍스트에서 지역명 추출"""
    try:
        # 1. 현재 여행 계획에서 지역 추출
        travel_plan = state.get("travel_plan", {})
        if travel_plan:
            # 여행 계획의 region 필드에서 직접 추출
            if "region" in travel_plan and travel_plan["region"]:
                return travel_plan["region"]

            # 장소들에서 지역 추출
            places = travel_plan.get("places", [])
            for place in places:
                if isinstance(place, dict):
                    region = place.get("region") or place.get("city")
                    if region:
                        return region
                elif isinstance(place, str):
                    extracted_region = extract_region_from_query(place)
                    if extracted_region:
                        return extracted_region

        # 2. 글로벌 current_travel_state에서 지역 추출
        global current_travel_state
        if current_travel_state and current_travel_state.get("travel_plan"):
            plan = current_travel_state["travel_plan"]
            if isinstance(plan, dict):
                if "region" in plan and plan["region"]:
                    return plan["region"]

                places = plan.get("places", [])
                for place in places:
                    if isinstance(place, dict):
                        region = place.get("region") or place.get("city")
                        if region:
                            return region

        # 3. 메시지 히스토리에서 지역 추출
        messages = state.get("messages", [])
        if messages:
            # 최근 메시지부터 역순으로 검색
            for message in reversed(messages):
                if isinstance(message, str):
                    extracted_region = extract_region_from_query(message)
                    if extracted_region:
                        return extracted_region

        # 4. 마지막 쿼리에서 지역 추출
        last_query = current_travel_state.get("last_query", "") if current_travel_state else ""
        if last_query:
            extracted_region = extract_region_from_query(last_query)
            if extracted_region:
                return extracted_region

        return None

    except Exception as e:
        print(f"❌ 컨텍스트에서 지역 추출 오류: {e}")
        return None

def extract_region_from_query(query):
    """사용자 쿼리에서 지역명 추출 (DB 기반)"""
    # DB에서 실제 region과 city 데이터 가져오기
    db_regions, db_cities = get_db_regions_and_cities()

    # 전체 지역 키워드 = DB regions + DB cities + 추가 별칭
    region_keywords = []

    # DB에서 가져온 region들
    region_keywords.extend(db_regions)

    # DB에서 가져온 city들
    region_keywords.extend(db_cities)

    # 추가 별칭들 (줄임말, 다른 표기)
    aliases = [
        '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
        '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
        '해운대', '강남', '강북', '종로', '명동', '홍대', '이태원', '인사동',
        '광안리', '남포동', '서면', '강릉', '춘천', '원주', '속초', '동해',
        '삼척', '태백', '정선', '평창', '영월', '횡성', '홍천', '화천',
        '양구', '인제', '고성', '양양'
    ]
    region_keywords.extend(aliases)

    # 중복 제거
    region_keywords = list(set(region_keywords))

    # 긴 키워드부터 매칭 (더 구체적인 지역명 우선)
    region_keywords.sort(key=len, reverse=True)

    # 쿼리에서 지역명 찾기
    for region in region_keywords:
        if region in query:
            return region

    return None

def get_weather_info(region_name):
    """기상청 API로 날씨 정보 가져오기"""
    if not WEATHER_API_KEY:
        return "❌ 기상청 API 키가 설정되지 않았습니다. .env 파일에 WEATHER_API_KEY를 추가해주세요."

    try:
        # 지역 좌표 가져오기
        coords = get_coordinates_for_region(region_name)

        # 현재 날짜와 시간
        now = datetime.datetime.now()
        base_date = now.strftime('%Y%m%d')

        # 기상청 발표시간에 맞춰 base_time 설정 (02, 05, 08, 11, 14, 17, 20, 23시)
        hour = now.hour
        if hour < 2:
            base_time = '2300'
            base_date = (now - datetime.timedelta(days=1)).strftime('%Y%m%d')
        elif hour < 5:
            base_time = '0200'
        elif hour < 8:
            base_time = '0500'
        elif hour < 11:
            base_time = '0800'
        elif hour < 14:
            base_time = '1100'
        elif hour < 17:
            base_time = '1400'
        elif hour < 20:
            base_time = '1700'
        elif hour < 23:
            base_time = '2000'
        else:
            base_time = '2300'

        # 기상청 API 요청 URL (HTTP로 시도)
        url = 'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst'

        params = {
            'serviceKey': WEATHER_API_KEY,
            'pageNo': '1',
            'numOfRows': '1000',
            'dataType': 'JSON',
            'base_date': base_date,
            'base_time': base_time,
            'nx': coords['nx'],
            'ny': coords['ny']
        }

        # 재시도 로직과 함께 HTTP 요청
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        }

        # 재시도 로직
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🌤️ 기상청 API 호출 시도 {attempt + 1}/{max_retries}")
                response = requests.get(url, params=params, headers=headers, timeout=30)
                break
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    return f"❌ 기상청 서버 응답 시간 초과 ({region_name})"
                print(f"   ⏰ 타임아웃 발생, {attempt + 2}번째 시도...")
                continue
            except Exception as e:
                if attempt == max_retries - 1:
                    return f"❌ 기상청 API 연결 오류: {e}"
                print(f"   🔄 연결 오류, {attempt + 2}번째 시도...")
                continue

        if response.status_code == 200:
            data = response.json()

            if data['response']['header']['resultCode'] == '00':
                items = data['response']['body']['items']['item']

                # 오늘과 내일 날씨 정보 추출
                weather_info = parse_weather_data(items, region_name)
                return weather_info
            else:
                return f"❌ 기상청 API 오류: {data['response']['header']['resultMsg']}"
        else:
            return f"❌ API 요청 실패: {response.status_code}"

    except Exception as e:
        return f"❌ 날씨 정보 조회 오류: {e}"

def parse_weather_data(items, region_name):
    """기상청 API 응답 데이터 파싱"""
    try:
        # 오늘과 내일 날씨 데이터 분류
        today = datetime.datetime.now().strftime('%Y%m%d')
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y%m%d')

        today_data = {}
        tomorrow_data = {}

        for item in items:
            fcst_date = item['fcstDate']
            fcst_time = item['fcstTime']
            category = item['category']
            fcst_value = item['fcstValue']

            # 오늘 데이터
            if fcst_date == today:
                if fcst_time not in today_data:
                    today_data[fcst_time] = {}
                today_data[fcst_time][category] = fcst_value

            # 내일 데이터
            elif fcst_date == tomorrow:
                if fcst_time not in tomorrow_data:
                    tomorrow_data[fcst_time] = {}
                tomorrow_data[fcst_time][category] = fcst_value

        # 날씨 정보 포맷팅
        weather_text = f"🌤️ <strong>{region_name} 날씨 정보</strong>\n\n"

        # 오늘 날씨 (대표 시간: 12시)
        if '1200' in today_data:
            data = today_data['1200']
            weather_text += "📅 <strong>오늘</strong>\n"
            weather_text += format_weather_detail(data)
            weather_text += "\n"

        # 내일 날씨 (대표 시간: 12시)
        if '1200' in tomorrow_data:
            data = tomorrow_data['1200']
            weather_text += "📅 <strong>내일</strong>\n"
            weather_text += format_weather_detail(data)

        return weather_text

    except Exception as e:
        return f"❌ 날씨 데이터 파싱 오류: {e}"

def format_weather_detail(data):
    """날씨 상세 정보 포맷팅"""
    try:
        # 기상청 코드 매핑
        sky_codes = {
            '1': '맑음 ☀️',
            '3': '구름많음 ⛅',
            '4': '흐림 ☁️'
        }

        pty_codes = {
            '0': '없음',
            '1': '비 🌧️',
            '2': '비/눈 🌨️',
            '3': '눈 ❄️',
            '4': '소나기 🌦️'
        }

        detail = ""

        # 하늘상태
        if 'SKY' in data:
            sky = sky_codes.get(data['SKY'], '정보없음')
            detail += f"• 하늘상태: {sky}\n"

        # 강수형태
        if 'PTY' in data:
            pty = pty_codes.get(data['PTY'], '정보없음')
            if data['PTY'] != '0':
                detail += f"• 강수형태: {pty}\n"

        # 기온
        if 'TMP' in data:
            detail += f"• 기온: {data['TMP']}°C 🌡️\n"

        # 강수확률
        if 'POP' in data:
            detail += f"• 강수확률: {data['POP']}% 💧\n"

        # 습도
        if 'REH' in data:
            detail += f"• 습도: {data['REH']}% 💨\n"

        # 풍속
        if 'WSD' in data:
            detail += f"• 풍속: {data['WSD']}m/s 💨\n"

        return detail

    except Exception as e:
        return f"상세 정보 처리 오류: {e}\n"

def get_smart_weather_info(region_name, travel_date=None):
    """스마트 날씨 조회: 단기예보 우선, 실패 시 과거 데이터 폴백"""
    import datetime

    try:
        # 1. 먼저 단기예보(미래 날씨) 시도 - 현재 시간 기준 3일 이내
        now = datetime.datetime.now()

        # 여행 날짜가 없으면 현재 날짜로 가정
        if not travel_date:
            travel_dt = now
        else:
            try:
                if isinstance(travel_date, str):
                    if len(travel_date) == 8:  # YYYYMMDD
                        travel_dt = datetime.datetime.strptime(travel_date, '%Y%m%d')
                    else:
                        travel_dt = datetime.datetime.strptime(travel_date, '%Y-%m-%d')
                else:
                    travel_dt = travel_date
            except Exception as e:
                print(f"날짜 파싱 오류: {e}")
                travel_dt = now

        days_diff = (travel_dt - now).days
        print(f"📅 여행일: {travel_dt.strftime('%Y-%m-%d')}, 현재로부터 {days_diff}일 후")

        # 단기예보 가능 기간: 오늘~3일 후 (기상청 API 제공 범위)
        if 0 <= days_diff <= 3:
            print(f"🌤️ {region_name} 단기예보 조회 중... ({days_diff}일 후)")
            future_weather = get_weather_info(region_name)
            if not future_weather.startswith("❌"):
                return f"📍 <strong>{region_name} 예상 날씨</strong> (여행일 기준)\n\n{future_weather}"

        # 2. 단기예보 실패 시 과거 동일 기간 날씨로 폴백
        print(f"📅 {region_name} 과거 동일 기간 날씨 조회 중...")

        # 작년 동일 기간 날짜 계산
        now = datetime.datetime.now()
        if travel_date:
            try:
                if isinstance(travel_date, str) and len(travel_date) == 8:
                    travel_dt = datetime.datetime.strptime(travel_date, '%Y%m%d')
                else:
                    travel_dt = now
                # 작년 동일 날짜
                last_year_date = travel_dt.replace(year=travel_dt.year - 1)
            except:
                last_year_date = now.replace(year=now.year - 1)
        else:
            # 여행 날짜 없으면 작년 이맘때
            last_year_date = now.replace(year=now.year - 1)

        historical_date = last_year_date.strftime('%Y%m%d')
        historical_weather = get_historical_weather_info(region_name, historical_date)

        if not historical_weather.startswith("❌"):
            # 과거 날씨에서 평균 기온만 추출
            simplified_weather = simplify_historical_weather(historical_weather, region_name, last_year_date.strftime('%Y-%m-%d'))
            return f"📊 <strong>{region_name} 참고 날씨</strong> (작년 동일 기간)\n\n{simplified_weather}\n\n💡 <em>실제 여행 시 최신 예보를 확인해주세요!</em>"

        # 3. 모든 시도 실패 시 일반적인 계절 정보
        month = now.month if not travel_date else travel_dt.month
        seasonal_info = get_seasonal_weather_info(region_name, month)
        return seasonal_info

    except Exception as e:
        return f"📍 <strong>{region_name}</strong>\n날씨 정보를 가져올 수 없어 일반적인 계절 정보를 제공합니다.\n\n{get_seasonal_weather_info(region_name, datetime.datetime.now().month)}"

def get_seasonal_weather_info(region_name, month):
    """계절별 일반적인 날씨 정보 제공"""
    seasonal_data = {
        1: {"temp": "영하~5°C", "desc": "춥고 건조", "clothes": "두꺼운 외투, 목도리 필수"},
        2: {"temp": "0~8°C", "desc": "추위가 절정", "clothes": "패딩, 장갑 권장"},
        3: {"temp": "5~15°C", "desc": "봄의 시작, 일교차 큼", "clothes": "얇은 외투, 레이어드"},
        4: {"temp": "10~20°C", "desc": "따뜻한 봄날씨", "clothes": "가디건, 얇은 재킷"},
        5: {"temp": "15~25°C", "desc": "화창하고 쾌적", "clothes": "반팔, 긴팔 셔츠"},
        6: {"temp": "20~28°C", "desc": "더워지기 시작", "clothes": "반팔, 선크림 필수"},
        7: {"temp": "23~32°C", "desc": "무덥고 습함, 장마", "clothes": "시원한 옷, 우산 준비"},
        8: {"temp": "25~33°C", "desc": "가장 더운 시기", "clothes": "통풍 잘되는 옷"},
        9: {"temp": "20~28°C", "desc": "선선해지기 시작", "clothes": "반팔~얇은 긴팔"},
        10: {"temp": "15~23°C", "desc": "가을 단풍, 쾌적", "clothes": "가디건, 얇은 외투"},
        11: {"temp": "8~18°C", "desc": "쌀쌀한 가을", "clothes": "두꺼운 외투 준비"},
        12: {"temp": "0~8°C", "desc": "추위 시작", "clothes": "코트, 목도리"}
    }

    info = seasonal_data.get(month, seasonal_data[datetime.datetime.now().month])

    return f"""🌡️ <strong>평균 기온</strong>: {info['temp']}
☁️ <strong>날씨 특징</strong>: {info['desc']}
👕 <strong>복장 추천</strong>: {info['clothes']}

💡 <em>일반적인 {month}월 날씨 정보입니다. 여행 전 최신 예보를 확인해주세요!</em>"""

def is_weather_query(query):
    """쿼리가 날씨 관련 질문인지 판단"""
    weather_keywords = [
        '날씨', '기온', '온도', '비', '눈', '바람', '습도', '맑음', '흐림',
        '강수', '기상', '일기예보', '예보', '우천', '강우', '폭우', '태풍',
        'weather', '온도가', '덥', '춥', '시원', '따뜻'
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in weather_keywords)

def is_historical_weather_query(query):
    """쿼리가 과거 날씨 관련 질문인지 판단"""
    import re

    historical_keywords = [
        '지난', '작년', '전년', '과거', '예전', '이전', '지난주', '지난달', '지난해',
        '어제', '그때', '당시', '년전', '달전', '주전', '일전',
        '작년 이맘때', '지난번', '그 당시', '몇년전', '몇달전'
    ]

    weather_keywords = [
        '날씨', '기온', '온도', '비', '눈', '바람', '습도', '강수', '기상'
    ]

    query_lower = query.lower()

    # 일반적인 과거 키워드 체크
    has_historical = any(keyword in query_lower for keyword in historical_keywords)
    has_weather = any(keyword in query_lower for keyword in weather_keywords)

    # 구체적인 날짜 패턴 체크 (과거로 간주)
    date_patterns = [
        r'\d{1,2}월\s*\d{1,2}일',  # 10월 4일
        r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',  # 2023년 10월 4일
        r'\d{1,2}/\d{1,2}',  # 10/4
        r'\d{4}/\d{1,2}/\d{1,2}',  # 2023/10/4
        r'\d{1,2}-\d{1,2}',  # 10-4
        r'\d{4}-\d{1,2}-\d{1,2}'  # 2023-10-4
    ]

    # 추가 날짜 패턴들 (년도 포함)
    additional_patterns = [
        r'20\d{2}년',  # 2023년, 2022년 등
        r'20\d{2}[.-/]\d{1,2}[.-/]\d{1,2}',  # 2023-10-15, 2023.10.15 등
        r'20\d{2}년\s*\d{1,2}월',  # 2023년 10월
    ]

    date_patterns.extend(additional_patterns)
    has_specific_date = any(re.search(pattern, query_lower) for pattern in date_patterns)

    return (has_historical or has_specific_date) and has_weather

def get_historical_weather_info(region_name, date_str):
    """기상청 API로 과거 날씨 정보 가져오기 (지상관측 일자료)"""
    if not WEATHER_API_KEY:
        return "❌ 기상청 API 키가 설정되지 않았습니다."

    try:
        # 지역 좌표 가져오기
        coords = get_coordinates_for_region(region_name)
        if not coords:
            return f"❌ {region_name}의 좌표 정보를 찾을 수 없습니다."

        # 날짜 형식 변환 (YYYYMMDD)
        try:
            if len(date_str) == 8 and date_str.isdigit():
                formatted_date = date_str
            else:
                # 다양한 날짜 형식 파싱
                import re
                # YYYY-MM-DD, YYYY/MM/DD 등의 형식을 YYYYMMDD로 변환
                date_clean = re.sub(r'[^\d]', '', date_str)
                if len(date_clean) == 8:
                    formatted_date = date_clean
                else:
                    return "❌ 날짜 형식이 올바르지 않습니다. (예: 20231015, 2023-10-15)"
        except:
            return "❌ 날짜 형식을 처리할 수 없습니다."

        # 기상청 지상관측 일자료 API URL
        url = 'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'

        params = {
            'serviceKey': WEATHER_API_KEY,
            'pageNo': '1',
            'numOfRows': '1',
            'dataType': 'JSON',
            'dataCd': 'ASOS',
            'dateCd': 'DAY',
            'startDt': formatted_date,
            'endDt': formatted_date,
            'stnIds': get_station_id_for_region(region_name)  # 지역별 관측소 ID
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print(f"📅 과거 날씨 조회: {region_name} ({formatted_date})")

        response = requests.get(url, params=params, headers=headers, timeout=30)

        if response.status_code == 200:
            try:
                data = response.json()
            except Exception as json_error:
                return f"❌ JSON 파싱 오류: {json_error}, 응답: {response.text[:200]}"

            if data['response']['header']['resultCode'] == '00':
                items = data['response']['body']['items']

                if 'item' in items and len(items['item']) > 0:
                    item = items['item'][0]
                    return format_historical_weather_data(item, region_name, formatted_date)
                else:
                    return f"❌ {formatted_date}의 {region_name} 관측 데이터가 없습니다."
            else:
                return f"❌ 기상청 API 오류: {data['response']['header']['resultMsg']}"
        else:
            return f"❌ API 요청 실패: {response.status_code}"

    except Exception as e:
        return f"❌ 과거 날씨 정보 조회 오류: {e}"

def get_station_id_for_region(region_name):
    """지역명에 해당하는 기상관측소 ID 반환"""
    station_mapping = {
        # 주요 도시별 관측소 ID (ASOS)
        '서울': '108',
        '서울특별시': '108',
        '부산': '159',
        '부산광역시': '159',
        '대구': '143',
        '대구광역시': '143',
        '인천': '112',
        '인천광역시': '112',
        '광주': '156',
        '광주광역시': '156',
        '대전': '133',
        '대전광역시': '133',
        '울산': '152',
        '울산광역시': '152',
        '제주': '184',
        '제주도': '184',
        '제주특별자치도': '184',
        '강릉': '105',
        '강원': '105',
        '강원도': '105',
        '강원특별자치도': '105',
        '춘천': '101',
        '원주': '114',
        '수원': '119',
        '경기': '119',
        '경기도': '119',
        '청주': '131',
        '충북': '131',
        '충청북도': '131',
        '천안': '232',
        '충남': '232',
        '충청남도': '232',
        '전주': '146',
        '전북': '146',
        '전라북도': '146',
        '전라북도특별자치도': '146',
        '광주': '156',
        '전남': '156',
        '전라남도': '156',
        '안동': '136',
        '경북': '136',
        '경상북도': '136',
        '창원': '155',
        '경남': '155',
        '경상남도': '155'
    }

    return station_mapping.get(region_name, '108')  # 기본값: 서울

def format_historical_weather_data(data, region_name, date_str):
    """과거 날씨 데이터 포맷팅"""
    try:
        # 날짜 포맷팅
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        formatted_date = f"{year}년 {month}월 {day}일"

        weather_text = f"📅 <strong>{region_name} {formatted_date} 날씨 기록</strong>\n\n"

        # 기온 정보
        if 'avgTa' in data and data['avgTa']:
            weather_text += f"🌡️ <strong>평균기온</strong>: {data['avgTa']}°C\n"
        if 'maxTa' in data and data['maxTa']:
            weather_text += f"🔥 <strong>최고기온</strong>: {data['maxTa']}°C\n"
        if 'minTa' in data and data['minTa']:
            weather_text += f"❄️ <strong>최저기온</strong>: {data['minTa']}°C\n"

        # 강수량
        if 'sumRn' in data and data['sumRn'] and data['sumRn'].strip():
            rain_amount = float(data['sumRn'])
            if rain_amount > 0:
                weather_text += f"🌧️ <strong>강수량</strong>: {data['sumRn']}mm\n"
            else:
                weather_text += f"☀️ <strong>강수량</strong>: 0mm (맑음)\n"
        else:
            weather_text += f"☀️ <strong>강수량</strong>: 0mm (맑음)\n"

        # 바람
        if 'avgWs' in data and data['avgWs']:
            weather_text += f"💨 <strong>평균풍속</strong>: {data['avgWs']}m/s\n"
        if 'maxWs' in data and data['maxWs']:
            weather_text += f"🌪️ <strong>최대풍속</strong>: {data['maxWs']}m/s\n"

        # 습도
        if 'avgRhm' in data and data['avgRhm']:
            weather_text += f"💧 <strong>평균습도</strong>: {data['avgRhm']}%\n"

        # 일조시간
        if 'sumSs' in data and data['sumSs']:
            weather_text += f"☀️ <strong>일조시간</strong>: {data['sumSs']}시간\n"

        return weather_text

    except Exception as e:
        return f"❌ 과거 날씨 데이터 포맷팅 오류: {e}"

def simplify_historical_weather(historical_weather_text, region_name, date_str):
    """과거 날씨 데이터에서 평균 기온만 추출하여 단순화"""
    try:
        import re

        # 평균기온 정보 추출
        avg_temp_match = re.search(r'🌡️ <strong>평균기온</strong>: ([^°]+)°C', historical_weather_text)

        if avg_temp_match:
            avg_temp = avg_temp_match.group(1)
            return f"🌡️ <strong>평균기온</strong>: {avg_temp}°C"
        else:
            # 평균기온 정보가 없는 경우 대체 처리
            return "🌡️ <strong>기온 정보</strong>: 데이터 없음"

    except Exception as e:
        return f"🌡️ <strong>기온 정보</strong>: 처리 오류 ({e})"

def extract_date_from_query(query):
    """쿼리에서 날짜 추출"""
    import re
    import datetime

    query_lower = query.lower()

    # 상대적 날짜 패턴
    if '어제' in query_lower:
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        return yesterday.strftime('%Y%m%d')
    elif '지난주' in query_lower:
        last_week = datetime.datetime.now() - datetime.timedelta(days=7)
        return last_week.strftime('%Y%m%d')
    elif '지난달' in query_lower:
        last_month = datetime.datetime.now() - datetime.timedelta(days=30)
        return last_month.strftime('%Y%m%d')
    elif '작년' in query_lower or '지난해' in query_lower:
        last_year = datetime.datetime.now() - datetime.timedelta(days=365)
        return last_year.strftime('%Y%m%d')

    # 절대적 날짜 패턴 (YYYY-MM-DD, YYYY/MM/DD 등)
    date_patterns = [
        r'(\d{4})[.-/](\d{1,2})[.-/](\d{1,2})',  # 2023-10-15, 2023.10.15, 2023/10/15
        r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',  # 2023년 10월 15일
        r'(\d{1,2})월\s*(\d{1,2})일',              # 10월 15일 (올해)
        r'(\d{8})',                                # 20231015
    ]

    for pattern in date_patterns:
        match = re.search(pattern, query)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 3:
                    year, month, day = groups
                    if len(year) == 4:
                        return f"{year}{month.zfill(2)}{day.zfill(2)}"
                elif len(groups) == 2:  # 월일만 있는 경우 올해로 가정
                    month, day = groups
                    current_year = datetime.datetime.now().year
                    return f"{current_year}{month.zfill(2)}{day.zfill(2)}"
                elif len(groups) == 1 and len(groups[0]) == 8:  # YYYYMMDD
                    return groups[0]
            except:
                continue

    return None

def interactive_mode():
    """대화형 모드"""
    print("\n" + "="*60)
    print("🌟 하이브리드 최적화 여행 추천 RAG 시스템 (Amazon Bedrock)")
    print("="*60)
    print("사용법: 여행 지역과 기간을 입력하세요")
    print("예시: '부산 2박 3일 여행 추천', '제주도 맛집 추천'")
    print("특징: SQL 필터링 + 벡터 유사도를 결합한 고속 검색")
    print("AI 모델: Amazon Bedrock Claude")
    print("종료: 'quit' 또는 'exit' 입력")
    print("-"*60)
    
    while True:
        try:
            user_input = input("\n💬 여행 질문을 입력하세요: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '종료']:
                print("👋 여행 추천 시스템을 종료합니다!")
                break
                
            if not user_input:
                print("⚠️ 질문을 입력해주세요.")
                continue
            
            print("\n" + "-"*40)
            get_travel_recommendation(user_input, stream=True)
            print("-"*40)
            
        except KeyboardInterrupt:
            print("\n👋 여행 추천 시스템을 종료합니다!")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

# # LangGraph 여행 대화 시스템

# LangGraph 의존성 임포트 (선택적)
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("⚠️ LangGraph가 설치되지 않음. 기본 RAG 모드로 동작합니다.")
    LANGGRAPH_AVAILABLE = False

class TravelState(TypedDict):
    """여행 대화 상태 관리를 위한 TypedDict"""
    messages: List[str]
    query_type: str
    need_rag: bool
    need_search: bool
    need_tool: bool
    need_confirmation: bool  # 일정 확정 여부
    history: str
    rag_results: List
    search_results: List
    tool_results: dict
    travel_plan: dict  # 구조화된 여행 일정
    user_preferences: dict
    conversation_context: str
    formatted_ui_response: dict  # UI용 구조화된 응답

def classify_query(state: TravelState) -> TravelState:
    """향상된 쿼리 분류 - 여러 경로 동시 판단 (2단계 플로우 지원)"""
    if not state.get("messages"):
        return state

    user_input = state["messages"][-1] if state["messages"] else ""
    user_input_lower = user_input.lower()

    print(f"🔍 쿼리 분류 중: '{user_input}'")

    # 새로운 여행 요청 감지 (기존 일정이 있을 때)
    if state.get("travel_plan"):
        is_new_travel_request = any(keyword in user_input_lower for keyword in [
            "새로운", "다른", "새로", "다시", "또 다른", "새롭게", "다음",
            "박", "일", "여행", "추천", "일정", "계획"
        ]) and not any(confirm_keyword in user_input_lower for confirm_keyword in [
            "확정", "결정", "좋아", "마음에", "이걸로"
        ])

        if is_new_travel_request:
            print("🔄 새로운 여행 일정 요청 감지 - 기존 상태 초기화")
            # 기존 여행 계획 초기화
            state["travel_plan"] = {}
            state["user_preferences"] = {}
            state["conversation_context"] = ""
            state["formatted_ui_response"] = {}
    
    # 여행 일정 추천 관련 키워드
    travel_keywords = ["추천", "여행", "일정", "계획", "코스", "가볼만한", "여행지", "관광"]
    location_keywords = ["서울", "부산", "제주", "경기", "강원", "장소", "위치", "어디"]
    food_keywords = ["맛집", "음식", "식당", "먹을", "카페", "레스토랑"]
    booking_keywords = ["예약", "등록", "신청", "결제", "예매"]
    
    # 확정 키워드 (개선된 패턴 매칭)
    strong_confirmation_keywords = ["확정", "결정", "확인", "이걸로", "좋아", "맞아", "그래", "됐어", "완료", "ok", "오케이"]
    weak_confirmation_keywords = ["진행", "가자", "이거야", "네", "예", "응", "맞네", "좋네"]

    # 단일 확정 키워드 (짧은 답변)
    single_word_confirmations = ["확정", "결정", "좋아", "ok", "오케이", "네", "예", "응", "그래"]

    # 날씨 요청인지 먼저 확인 (현재/미래 + 과거 날씨 모두 포함)
    is_weather_request = is_weather_query(user_input) or is_historical_weather_query(user_input)

    # 복합적 분류 로직
    need_rag = any(keyword in user_input for keyword in travel_keywords) or is_weather_request
    need_search = any(keyword in user_input for keyword in location_keywords) and not is_weather_request
    need_tool = any(keyword in user_input for keyword in booking_keywords)

    # 음식 관련 질의도 RAG로 처리
    if any(keyword in user_input for keyword in food_keywords):
        need_rag = True

    # 개선된 확정 판단 로직
    has_strong_confirmation = any(keyword in user_input_lower for keyword in strong_confirmation_keywords)
    has_weak_confirmation = any(keyword in user_input_lower for keyword in weak_confirmation_keywords)

    # 짧은 단어 확정 (5글자 이하이면서 확정 키워드만 있는 경우)
    is_short_confirmation = (len(user_input_lower.strip()) <= 5 and
                            any(keyword == user_input_lower.strip() for keyword in single_word_confirmations))

    # 현재 상태에 여행 일정이 있는지 확인
    has_travel_plan = bool(state.get("travel_plan"))

    print(f"   🔍 확정 분석: 강한확정={has_strong_confirmation}, 약한확정={has_weak_confirmation}, 짧은확정={is_short_confirmation}")
    print(f"   📋 여행계획존재={has_travel_plan}, RAG필요={need_rag}")

    # 확정 판단 우선순위:
    # 1. 여행 일정이 있고 강한 확정 키워드 → 확정
    # 2. 여행 일정이 있고 짧은 확정 응답 → 확정
    # 3. 여행 일정이 있고 약한 확정 키워드 (RAG가 아닐 때) → 확정
    need_confirmation = False
    if has_travel_plan:
        if has_strong_confirmation or is_short_confirmation:
            need_confirmation = True
            print(f"   ✅ 확정 판단: 강한 확정 또는 짧은 확정")
        elif has_weak_confirmation and not need_rag:
            need_confirmation = True
            print(f"   ✅ 확정 판단: 약한 확정 (RAG 아님)")
        else:
            print(f"   ❌ 확정 불가: 조건 불충족")
    else:
        print(f"   ❌ 확정 불가: 여행 일정 없음")
    
    query_type = "complex" if sum([need_rag, need_search, need_tool]) > 1 else "simple"
    
    print(f"   분류 결과 - RAG: {need_rag}, Search: {need_search}, Tool: {need_tool}, 확정: {need_confirmation}")
    print(f"   여행 일정 존재: {has_travel_plan}")
    
    return {
        **state,
        "need_rag": need_rag,
        "need_search": need_search,
        "need_tool": need_tool,
        "need_confirmation": need_confirmation,
        "query_type": query_type
    }

def rag_processing_node(state: TravelState) -> TravelState:
    """RAG 기반 여행지 추천 처리 노드 (개선된 구조화 데이터 포함)"""
    if not state.get("messages"):
        return {
            **state,
            "conversation_context": "처리할 메시지가 없습니다."
        }

    user_query = state["messages"][-1]
    print(f"🧠 RAG 처리 시작: '{user_query}'")

    # 날씨 관련 질문인지 확인
    if is_weather_query(user_query):
        # 과거 날씨 요청인지 확인
        if is_historical_weather_query(user_query):
            print("📅 과거 날씨 요청 감지됨")

            # 쿼리에서 지역명과 날짜 추출 (컨텍스트 우선)
            region = extract_region_from_query(user_query)
            if not region:
                region = extract_region_from_context(state)
            date_str = extract_date_from_query(user_query)

            print(f"🔍 디버깅: region='{region}', date_str='{date_str}'")

            if region and date_str:
                print(f"📍 감지된 지역: {region}, 날짜: {date_str}")
                weather_info = get_historical_weather_info(region, date_str)

                return {
                    **state,
                    "conversation_context": weather_info
                }
            elif region and not date_str:
                return {
                    **state,
                    "conversation_context": f"🤔 {region}의 과거 날씨를 조회하려면 구체적인 날짜를 함께 말씀해주세요.\n예: '서울 어제 날씨', '부산 2023년 10월 15일 날씨'"
                }
            elif not region and date_str:
                # 컨텍스트에서 지역 찾기 시도
                context_region = extract_region_from_context(state)

                # 글로벌 상태에서도 찾기 시도
                if not context_region:
                    global current_travel_state
                    if current_travel_state.get("travel_plan", {}).get("region"):
                        context_region = current_travel_state["travel_plan"]["region"]

                if context_region:
                    print(f"📍 컨텍스트에서 발견된 지역: {context_region}")
                    weather_info = get_historical_weather_info(context_region, date_str)
                    return {
                        **state,
                        "conversation_context": f"📍 <strong>{context_region}</strong>의 과거 날씨 정보를 조회합니다.\n\n{weather_info}"
                    }

                return {
                    **state,
                    "conversation_context": f"🤔 과거 날씨를 조회하려면 지역명을 함께 말씀해주세요.\n예: '서울 어제 날씨', '부산 지난주 날씨'"
                }
            else:
                return {
                    **state,
                    "conversation_context": "🤔 과거 날씨 정보를 제공하려면 지역명과 날짜를 함께 말씀해주세요.\n예: '서울 어제 날씨', '부산 2023년 10월 15일 날씨'"
                }
        else:
            # 현재/미래 날씨 요청
            print("🌤️ 현재/미래 날씨 요청 감지됨")

            # 쿼리에서 지역명 추출 (컨텍스트 우선)
            region = extract_region_from_query(user_query)
            if not region:
                region = extract_region_from_context(state)

            if region:
                print(f"📍 감지된 지역: {region}")
                weather_info = get_weather_info(region)

                return {
                    **state,
                    "conversation_context": weather_info
                }
            else:
                # 지역명이 없으면 컨텍스트에서 지역 찾기 시도
                context_region = extract_region_from_context(state)

                if context_region:
                    print(f"📍 컨텍스트에서 발견된 지역: {context_region}")
                    weather_info = get_weather_info(context_region)
                    return {
                        **state,
                        "conversation_context": f"📍 <strong>{context_region}</strong>의 날씨 정보를 조회합니다.\n\n{weather_info}"
                    }

                return {
                    **state,
                    "conversation_context": "🤔 날씨 정보를 제공하려면 지역명을 함께 말씀해주세요. (예: '서울 날씨', '부산 날씨')"
                }

    try:
        # 하이브리드 검색으로 실제 장소 데이터 가져오기
        docs = retriever._get_relevant_documents(user_query)
        
        # 지역 필터링 강화 - 쿼리에서 지역명 추출하여 해당 지역 결과만 우선
        region_keywords = {
            '부산': ['부산', 'busan', '해운대', '광안리', '남포동', '서면', '기장', '동래', '사하', '북구', '동구', '서구', '중구', '영도', '부산진', '연제', '수영', '사상', '금정', '강서', '해운대구', '사하구'],
            '서울': ['서울', 'seoul', '강남', '홍대', '명동', '이태원', '인사동', '종로'],
            '제주도': ['제주도', '제주', '제주특별자치도', '서귀포', '한라산', '성산', '우도'],
            '경주': ['경주', '불국사', '석굴암', '첨성대'],
            '전주': ['전주', '한옥마을', '전라북도'],
            '대구': ['대구', 'daegu', '동성로'],
            '광주': ['광주', '무등산'],
            '춘천': ['춘천', '남이섬', '소양강', '강원도'],
            '강릉': ['강릉', '경포대', '정동진', '강릉시', '사천해변', '남항진', '경포해변', '안목해변', '주문진', '오죽헌', '참소리박물관'],
            '여수': ['여수', '오동도', '전라남도'],
            '인천': ['인천', '차이나타운', '월미도']
        }
        
        query_regions = []
        target_keywords = []
        
        for region, keywords in region_keywords.items():
            for keyword in keywords:
                if keyword in user_query.lower():
                    query_regions.append(region)
                    target_keywords.extend(keywords)
                    break
        
        # 지역 필터링 강화 - 정확한 지역만 매칭
        if query_regions:
            print(f"🎯 지역 필터링: {query_regions}")
            region_docs = []
            
            for doc in docs:
                doc_region = doc.metadata.get('region', '').lower()
                doc_city = doc.metadata.get('city', '').lower()
                
                # 정확한 지역 매칭만 허용 (다른 지역 장소 배제)
                is_relevant = False
                for region in query_regions:
                    region_lower = region.lower()
                    
                    # 서울 요청 시 서울특별시만 허용
                    if '서울' in region_lower:
                        if '서울' in doc_region and '강원' not in doc_region and '부산' not in doc_region:
                            is_relevant = True
                            break
                    # 부산 요청 시 부산광역시만 허용
                    elif '부산' in region_lower:
                        if '부산' in doc_region and '서울' not in doc_region:
                            is_relevant = True
                            break
                    # 강릉/강원도 요청 시 강원도만 허용
                    elif '강릉' in region_lower or '강원' in region_lower:
                        if '강원' in doc_region and '서울' not in doc_region:
                            is_relevant = True
                            break
                    # 제주 요청 시 제주도만 허용
                    elif '제주' in region_lower:
                        if '제주' in doc_region and '서울' not in doc_region:
                            is_relevant = True
                            break
                    # 기타 지역 정확한 매칭
                    elif region_lower in doc_region:
                        is_relevant = True
                        break
                
                if is_relevant:
                    region_docs.append(doc)
            
            if region_docs:
                docs = region_docs[:50]  # 필터링된 결과 사용
                print(f"📍 강화된 지역 필터링 결과: {len(docs)}개 문서 선별 (지역: {query_regions})")
            else:
                print(f"⚠️ 지역 필터링 결과 없음, 전체 결과에서 상위 20개 사용")
                docs = docs[:20]  # 전체 결과도 줄임
        
        # 구조화된 장소 데이터 추출
        structured_places = extract_structured_places(docs)
        
        # 개선된 여행 일정 생성 프롬프트
        # 지역 정보를 프롬프트에 포함
        region_context = f" 반드시 {', '.join(query_regions)} 지역 내의 장소만 추천하세요." if query_regions else ""
        
        enhanced_prompt = ChatPromptTemplate.from_template(f"""
당신은 여행 전문 어시스턴트입니다. 주어진 여행지 정보를 바탕으로 깔끔하고 구조화된 여행 일정을 작성해주세요.{region_context}

여행지 정보:
{{context}}

사용자 질문: {{question}}

중요한 제약사항:
- 주어진 여행지 정보에 포함된 장소들만 사용하세요
- 각 일차별로 시간대에 맞는 적절한 장소를 배치하세요
- 같은 지역 내에서만 일정을 구성하세요

출력 형식을 다음과 같이 맞춰주세요:

🏝️ <strong>지역명 여행 일정</strong>

<strong>[1일차]</strong>
• 09:00-12:00 <strong>장소명</strong> - 간단한 설명 (1줄)
• 12:00-13:00 <strong>식당명</strong> - 음식 종류 점심
• 14:00-17:00 <strong>장소명</strong> - 간단한 설명 (1줄)
• 18:00-19:00 <strong>식당명</strong> - 음식 종류 저녁

<strong>[2일차]</strong> (기간에 따라 추가)
...

💡 <strong>여행 팁</strong>: 지역 특색이나 주의사항

이 일정으로 확정하시겠어요?

답변:
        """)
        
        # 컨텍스트 생성
        context = format_docs(docs)
        
        # LLM으로 구조화된 응답 생성
        prompt_value = enhanced_prompt.invoke({"context": context, "question": user_query})
        raw_response = llm.invoke(prompt_value).content
        
        # 가독성을 위한 개행 처리
        formatted_response = format_travel_response_with_linebreaks(raw_response)
        
        # 상세한 여행 일정 파싱 (실제 장소 데이터 포함)
        travel_plan = parse_enhanced_travel_plan(formatted_response, user_query, structured_places)
        
        # UI용 구조화된 응답 생성
        formatted_ui_response = create_formatted_ui_response(travel_plan, formatted_response)
        
        # 여행 일정 생성 완료 - 사용자 확인 대기 상태
        # 자동 확정하지 않고 사용자의 확정 의사를 기다림

        # 🌤️ 여행지 날씨 정보 자동 추가
        region_for_weather = travel_plan.get('region', '') or extract_region_from_query(user_query)
        if region_for_weather:
            print(f"🌤️ {region_for_weather} 날씨 정보 조회 중...")
            weather_info = get_smart_weather_info(region_for_weather)

            # 여행 일정에 날씨 정보 통합 (여행 팁 앞에 삽입)
            if weather_info and not weather_info.startswith("❌"):
                # "💡 여행 팁" 앞에 날씨 정보 삽입
                if "💡" in formatted_response:
                    parts = formatted_response.split("💡", 1)
                    formatted_response_with_weather = f"""{parts[0]}

{weather_info}

💡{parts[1]}"""
                else:
                    # 여행 팁이 없으면 마지막에 추가
                    formatted_response_with_weather = f"""{formatted_response}

{weather_info}"""
            else:
                formatted_response_with_weather = formatted_response
        else:
            formatted_response_with_weather = formatted_response

        print(f"✅ RAG 처리 완료. 결과 길이: {len(formatted_response_with_weather)}")
        print(f"   추출된 장소 수: {len(structured_places)}")

        return {
            **state,
            "rag_results": docs,
            "travel_plan": travel_plan,
            "conversation_context": formatted_response_with_weather,
            "formatted_ui_response": formatted_ui_response
        }
        
    except Exception as e:
        print(f"❌ RAG 처리 오류: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "rag_results": [],
            "conversation_context": f"여행 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"
        }

def search_processing_node(state: TravelState) -> TravelState:
    """장소 검색 처리 노드"""
    if not state.get("messages"):
        return {
            **state,
            "conversation_context": "검색할 메시지가 없습니다."
        }
    
    user_query = state["messages"][-1]
    print(f"📍 장소 검색 처리: '{user_query}'")
    
    try:
        # 기존 search_places 함수 사용
        docs = search_places(user_query)

        # 검색 결과를 간단하게 포맷팅
        if docs:
            search_summary = ""  # 불필요한 "N개 찾았습니다" 메시지 제거
        else:
            search_summary = "검색 결과가 없습니다."

        return {
            **state,
            "search_results": docs,
            "conversation_context": search_summary
        }
        
    except Exception as e:
        print(f"❌ 장소 검색 오류: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "search_results": [],
            "conversation_context": f"장소 검색 중 오류가 발생했습니다: {str(e)}"
        }

def tool_execution_node(state: TravelState) -> TravelState:
    """예약/등록 처리 노드"""
    if not state.get("messages"):
        return state
    
    user_query = state["messages"][-1]
    print(f"🔧 도구 실행: '{user_query}'")
    
    # 실제 예약 시스템 연동은 향후 구현
    # 현재는 모의 응답 제공
    mock_result = {
        "status": "pending",
        "message": "예약 기능은 현재 준비 중입니다. 고객센터로 문의해주세요.",
        "action_required": "manual_booking"
    }
    
    return {
        **state,
        "tool_results": mock_result
    }

def general_chat_node(state: TravelState) -> TravelState:
    """일반 대화 처리 노드"""
    if not state.get("messages"):
        return state
    
    user_query = state["messages"][-1]
    print(f"💬 일반 대화 처리: '{user_query}'")
    
    # 간단한 일반 대화 응답
    general_prompt = ChatPromptTemplate.from_template("""
당신은 친근한 여행 어시스턴트입니다. 
사용자와 자연스럽게 대화하며 여행 관련 도움을 제공하세요.

사용자 메시지: {question}

답변 지침:
- 친근하고 도움이 되는 톤으로 답변하세요
- 여행과 관련된 질문이면 구체적인 정보를 요청하세요
- 간단하고 명확하게 답변하세요

답변:
    """)
    
    try:
        prompt_value = general_prompt.invoke({"question": user_query})
        response = llm.invoke(prompt_value).content
        
        return {
            **state,
            "conversation_context": response
        }
        
    except Exception as e:
        print(f"❌ 일반 대화 처리 오류: {e}")
        return {
            **state,
            "conversation_context": "죄송합니다. 일시적인 오류가 발생했습니다."
        }

def normalize_place_name(place_name: str) -> str:
    """장소명 정규화 (매칭 정확도 향상) - 부가 정보 제거"""
    if not place_name:
        return ""

    # 접두어 제거
    name = place_name.strip()
    if name.startswith("이름: "):
        name = name[3:].strip()
    if name.startswith("<strong>"):
        name = name[8:].strip()
    if name.endswith("</strong>"):
        name = name[:-9].strip()

    # 부가 정보 패턴 제거 (한국관광 품질인증 등)
    name = re.sub(r'\[한국관광\s*품질인증[^\]]*\]', '', name)  # [한국관광 품질인증/Korea Quality] 제거
    name = re.sub(r'\[Korea\s*Quality[^\]]*\]', '', name)      # [Korea Quality] 제거  
    name = re.sub(r'\([^)]*품질인증[^)]*\)', '', name)         # (품질인증 관련) 제거
    name = re.sub(r'\s+', ' ', name)                          # 연속 공백 정리

    # 공백 정리
    name = ' '.join(name.split())

    return name.lower()

def find_place_in_itinerary(place_name: str, itinerary: list) -> int:
    """일정에서 장소가 속한 일차 찾기 (개선된 매칭)"""
    normalized_place = normalize_place_name(place_name)

    for day_info in itinerary:
        day_num = day_info.get("day", 1)

        for schedule in day_info.get("schedule", []):
            schedule_place = normalize_place_name(schedule.get("place_name", ""))

            # 정확한 매칭
            if normalized_place == schedule_place:
                return day_num

            # 포함 관계 매칭 (더 긴 이름이 짧은 이름을 포함)
            if len(normalized_place) >= 2 and len(schedule_place) >= 2:
                if (normalized_place in schedule_place and len(normalized_place) >= len(schedule_place) * 0.5) or \
                   (schedule_place in normalized_place and len(schedule_place) >= len(normalized_place) * 0.5):
                    return day_num

    return 0  # 매칭되지 않음

def extract_places_by_day(itinerary: list) -> dict:
    """일차별로 장소 목록 추출"""
    places_by_day = {}

    for day_info in itinerary:
        day_num = day_info.get("day", 1)
        places_by_day[day_num] = []

        for schedule in day_info.get("schedule", []):
            place_name = normalize_place_name(schedule.get("place_name", ""))
            if place_name and place_name not in places_by_day[day_num]:
                places_by_day[day_num].append(place_name)

    return places_by_day

def confirmation_processing_node(state: TravelState) -> TravelState:
    """일정 확정 처리 노드 (2단계 플로우)"""
    print(f"🎯 확정 처리 요청")

    # 디버깅 정보
    current_travel_plan = state.get("travel_plan", {})
    global_travel_plan = current_travel_state.get("travel_plan", {})
    print(f"   📋 State travel_plan: {bool(current_travel_plan)}")
    print(f"   🌐 Global travel_plan: {bool(global_travel_plan)}")

    # 현재 상태에 여행 일정이 없으면 전역 상태 확인
    if not current_travel_plan:
        if global_travel_plan:
            print(f"   🔄 전역 상태에서 여행 계획 복원")
            state["travel_plan"] = global_travel_plan
            current_travel_plan = global_travel_plan

    # 여전히 여행 일정이 없으면 안내 메시지
    if not current_travel_plan:
        response = """
🤔 <strong>확정하고 싶으신 여행 일정이 없는 것 같아요!</strong>

📝 <strong>확정 절차</strong>:
1. 먼저 여행 일정을 요청해주세요
   예: "부산 3박 4일 여행 추천해줘"
2. 생성된 일정을 확인하신 후
3. "확정", "좋아", "이걸로 해줘" 등으로 확정 의사를 표현해주세요

✈️ 그러면 바로 지도에서 여행지를 확인하실 수 있어요!

💡 지금 바로 어떤 여행 일정을 원하시는지 말씀해주세요!
        """.strip()
        
        return {
            **state,
            "conversation_context": response,
            "tool_results": {
                "action": "request_travel_plan",
                "message": "여행 일정 먼저 요청 필요"
            }
        }
    
    print(f"✅ 여행 일정 확정 처리")
    
    travel_plan = state["travel_plan"]
    
    # 일정 확정 처리
    from datetime import datetime
    confirmed_plan = {
        **travel_plan,
        "status": "confirmed",
        "confirmed_at": datetime.now().isoformat(),
        "ready_for_booking": True,
        "plan_id": generate_plan_id()  # 고유 ID 생성
    }
    
    # 확정 응답 생성
    itinerary_summary = ""
    if confirmed_plan.get("duration"):
        # duration에서 일수 정보 추출하여 표시
        duration_str = confirmed_plan["duration"]
        itinerary_summary = f"{duration_str} 일정"
    elif "itinerary" in confirmed_plan and confirmed_plan["itinerary"]:
        itinerary_summary = f"총 {len(confirmed_plan['itinerary'])}일 일정"
    
    places_summary = ""
    if "places" in confirmed_plan and confirmed_plan["places"]:
        place_names = [place["name"] for place in confirmed_plan["places"][:3] if place["name"]]
        if place_names:
            places_summary = f"주요 방문지: {', '.join(place_names)}"
            if len(confirmed_plan["places"]) > 3:
                places_summary += f" 외 {len(confirmed_plan['places']) - 3}곳"
    
    # 지도 표시를 위한 장소 파라미터 구성 (메타데이터 활용)
    places_list = []
    day_numbers_list = []
    source_tables_list = []

    if "places" in confirmed_plan and confirmed_plan["places"]:
        total_days = len(confirmed_plan.get("itinerary", []))
        if total_days == 0:
            total_days = 1

        # 장소를 일차별로 정확하게 배치 (개선된 매칭)
        places_to_process = confirmed_plan["places"]  # 모든 장소 포함

        # 일차별 장소 목록 추출 (정확한 매칭을 위해)
        itinerary = confirmed_plan.get("itinerary", [])
        places_by_day = extract_places_by_day(itinerary)

        print(f"🗓️ 일차별 장소 분석: {places_by_day}")

        for idx, place in enumerate(places_to_process):
            # 메타데이터에서 직접 정보 추출 (벡터 업데이트 후)
            table_name = place.get("table_name", "nature")
            place_id = place.get("place_id")

            # place_id 검증 - 실제 DB에 존재하는 ID만 허용
            if not place_id or place_id.startswith('temp_'):
                print(f"⚠️ 유효하지 않은 place_id - 장소 '{place.get('name', 'Unknown')}' 스킵 (place_id: {place_id})")
                continue
            
            # 무효한 장소명 체크
            invalid_names = ['무등산 주상절리대', '기본장소', 'unknown', '']
            if place.get('name', '') in invalid_names:
                print(f"⚠️ 무효한 장소명 - 장소 '{place.get('name', 'Unknown')}' 스킵")
                continue

            # 장소 ID 생성 (table_name_place_id 형태)
            place_identifier = f"{table_name}_{place_id}"

            places_list.append(place_identifier)
            source_tables_list.append(table_name)

            # 개선된 일차 매칭
            place_name = place.get("name", "")
            day_num = find_place_in_itinerary(place_name, itinerary)

            # 매칭되지 않은 경우 처리
            if day_num == 0:
                print(f"⚠️ '{place_name}' 매칭 실패, 대안 방법 시도")

                # 카테고리별로 적절한 일차에 배치
                category = place.get("category", "")

                if "식당" in category or "맛집" in category or "음식" in category:
                    # 식사 장소는 기존 식사 시간대가 있는 일차에 배치
                    for day_info in itinerary:
                        for schedule in day_info.get("schedule", []):
                            if any(keyword in schedule.get("description", "") for keyword in ["점심", "저녁", "식사"]):
                                day_num = day_info.get("day", 1)
                                break
                        if day_num > 0:
                            break

                # 여전히 매칭되지 않으면 가장 적은 장소가 있는 일차에 배치
                if day_num == 0:
                    if places_by_day:
                        min_places_day = min(places_by_day.keys(), key=lambda x: len(places_by_day[x]))
                        day_num = min_places_day
                    else:
                        # 최후의 수단: 순서대로 균등 분배
                        day_num = (idx % max(total_days, 1)) + 1

                print(f"📍 '{place_name}' -> {day_num}일차 배치")

            day_numbers_list.append(str(day_num))

        print(f"🗺️ 지도 표시용 장소 구성 완료:")
        print(f"   장소 목록: {places_list[:5]}{'...' if len(places_list) > 5 else ''}")
        print(f"   일차 배정: {day_numbers_list[:5]}{'...' if len(day_numbers_list) > 5 else ''}")
        print(f"   테이블 목록: {source_tables_list[:5]}{'...' if len(source_tables_list) > 5 else ''}")

    # 날짜 계산 (duration에서 박수 추출)
    from datetime import datetime, timedelta

    duration_str = confirmed_plan.get('duration', '2박 3일')
    days_match = re.search(r'(\d+)일', duration_str)
    days = int(days_match.group(1)) if days_match else 2

    # 시작일을 오늘로 설정
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=days-1)).strftime('%Y-%m-%d')

    # URL 파라미터 생성
    import urllib.parse
    places_param = ','.join(places_list)
    day_numbers_param = ','.join(day_numbers_list)
    source_tables_param = ','.join(source_tables_list)

    map_url = f"/map?places={urllib.parse.quote(places_param)}&dayNumbers={urllib.parse.quote(day_numbers_param)}&sourceTables={urllib.parse.quote(source_tables_param)}&startDate={start_date}&endDate={end_date}&days={days}&baseAttraction=general"

    print(f"🔗 생성된 지도 URL: {map_url[:100]}{'...' if len(map_url) > 100 else ''}")
    
    # 지도 표시용 장소 정보 (DB에서 정확한 정보 조회)
    map_places = []
    if "places" in confirmed_plan and confirmed_plan["places"]:
        for place in confirmed_plan["places"]:
            place_id = place.get("place_id", place.get("id", ""))
            table_name = place.get("table_name", "")

            # DB에서 정확한 정보 조회
            if place_id and table_name and place_id != "unknown":
                db_place = get_place_from_recommendations(place_id, table_name)
                if db_place:
                    place_info = {
                        "name": db_place.get("name", ""),
                        "category": db_place.get("category", ""),
                        "table_name": db_place.get("table_name", ""),
                        "place_id": db_place.get("place_id", ""),
                        "city": db_place.get("city", ""),
                        "region": db_place.get("region", "")
                    }
                    # 위치 정보 추가
                    if db_place.get("latitude") and db_place.get("longitude"):
                        place_info["lat"] = db_place["latitude"]
                        place_info["lng"] = db_place["longitude"]
                    map_places.append(place_info)
                    continue

            # DB 조회 실패 시 기존 정보 사용 (fallback)
            place_info = {
                "name": place.get("name", ""),
                "category": place.get("category", ""),
                "table_name": table_name,
                "place_id": place_id,
                "city": place.get("city", ""),
                "region": place.get("region", "")
            }
            # 위치 정보가 있으면 추가
            if place.get("latitude") and place.get("longitude"):
                place_info["lat"] = place["latitude"]
                place_info["lng"] = place["longitude"]
            map_places.append(place_info)
    
    response = f"""
🎉 <strong>여행 일정이 확정되었습니다!</strong>

📋 <strong>확정된 일정 정보:</strong>
• <strong>지역</strong>: {confirmed_plan.get('region', 'N/A')}
• <strong>기간</strong>: {confirmed_plan.get('duration', 'N/A')}
• <strong>일정</strong>: {itinerary_summary}
• <strong>장소</strong>: {places_summary}

🗺️ <strong>지도에서 여행지를 확인하세요!</strong>
확정된 여행지들이 지도에 표시됩니다.

🔄 <strong>지도 페이지로 이동 중...</strong>
    """
    
    return {
        **state,
        "travel_plan": confirmed_plan,
        "conversation_context": response,
        "tool_results": {
            "action": "redirect_to_map",
            "data": confirmed_plan,
            "redirect_url": map_url,
            "places": map_places
        }
    }

def generate_plan_id() -> str:
    """여행 계획 고유 ID 생성"""
    import uuid
    import time
    
    # 타임스탬프 + UUID 조합으로 고유 ID 생성
    timestamp = str(int(time.time()))[-6:]  # 마지막 6자리
    unique_id = str(uuid.uuid4())[:8]  # UUID 첫 8자리
    
    return f"plan_{timestamp}_{unique_id}"

def create_formatted_ui_response(travel_plan: dict, raw_response: str) -> dict:
    """프론트엔드 UI용 구조화된 응답 생성"""
    
    # 응답에서 여행 팁 추출
    travel_tips = ""
    if "💡" in raw_response:
        tips_section = raw_response.split("💡")[1] if "💡" in raw_response else ""
        if tips_section:
            travel_tips = tips_section.split("이 일정으로 확정하시겠어요?")[0].strip()
    
    formatted_response = {
        "type": "travel_plan",
        "title": f"{travel_plan.get('region', '여행지')} {travel_plan.get('duration', '')} 여행 일정",
        "region": travel_plan.get('region', ''),
        "duration": travel_plan.get('duration', ''),
        "total_days": len(travel_plan.get('itinerary', [])),
        "total_places": len(travel_plan.get('places', [])),
        "confidence_score": travel_plan.get('confidence_score', 0),
        "itinerary": [],
        "travel_tips": travel_tips,
        "has_confirmation": True,
        "confirmation_message": "이 일정으로 확정하시겠어요?",
        "plan_id": travel_plan.get('plan_id')
    }
    
    # 일차별 일정 구조화
    for day_info in travel_plan.get('itinerary', []):
        day_data = {
            "day": day_info.get('day', 1),
            "title": f"{day_info.get('day', 1)}일차",
            "activities": []
        }
        
        for schedule_item in day_info.get('schedule', []):
            activity = {
                "time": schedule_item.get('time', ''),
                "place_name": schedule_item.get('place_name', ''),
                "description": schedule_item.get('description', ''),
                "category": schedule_item.get('category', ''),
                "is_meal": is_meal_activity(schedule_item.get('description', '')),
                "place_info": schedule_item.get('place_info')
            }
            day_data["activities"].append(activity)
        
        formatted_response["itinerary"].append(day_data)
    
    # 주요 장소 정보
    formatted_response["places"] = [
        {
            "name": place.get('name', ''),
            "category": place.get('category', ''),
            "description": place.get('description', ''),
            "similarity_score": place.get('similarity_score', 0)
        }
        for place in travel_plan.get('places', [])[:5]  # 상위 5개
    ]
    
    return formatted_response

def is_meal_activity(description: str) -> bool:
    """식사 관련 활동인지 판단"""
    meal_keywords = ['점심', '저녁', '아침', '식사', '맛집', '카페', '식당', '레스토랑']
    return any(keyword in description for keyword in meal_keywords)

def format_travel_response_with_linebreaks(response: str) -> str:
    """여행 응답에 적절한 개행 문자를 추가하여 가독성 향상"""
    
    # 기본적인 개행 처리
    formatted = response
    
    # 일차별 제목 앞에 개행 추가
    formatted = formatted.replace("<strong>[", "\n\n<strong>[")
    
    # 각 일정 항목 앞에 개행 추가 (• 기호 기준)
    formatted = formatted.replace("• ", "\n• ")
    
    # 여행 팁 섹션 앞에 개행 추가
    formatted = formatted.replace("💡 <strong>여행 팁</strong>", "\n\n💡 <strong>여행 팁</strong>")
    
    # 확정 안내 앞에 개행 추가
    formatted = formatted.replace("이 일정으로 확정", "\n\n이 일정으로 확정")
    
    # 제목 앞 불필요한 개행 제거
    if formatted.startswith("\n\n"):
        formatted = formatted[2:]
    
    # 연속된 개행 정리 (3개 이상 -> 2개)
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)
    
    return formatted.strip()

def integrate_response_node(state: TravelState) -> TravelState:
    """여러 노드의 결과를 통합하여 최종 응답 생성"""
    print(f"🔄 응답 통합 중...")
    
    response_parts = []
    
    # 확정 처리가 필요한 경우 확정 노드로 처리
    if state.get("need_confirmation") and state.get("travel_plan"):
        print("🎯 확정 처리 필요 - confirmation_processing_node로 이동")
        return confirmation_processing_node(state)
    
    # RAG 결과 우선
    if state.get("conversation_context"):
        response_parts.append(state["conversation_context"])
    
    # Search 결과 추가
    if state.get("search_results"):
        search_summary = f"검색된 장소: {len(state['search_results'])}곳"
        response_parts.append(search_summary)
    
    # Tool 결과 추가
    if state.get("tool_results") and state["tool_results"].get("message"):
        response_parts.append(f"🔧 {state['tool_results']['message']}")
    
    # 응답이 없으면 기본 응답
    if not response_parts:
        response_parts.append("안녕하세요! 여행 관련 질문이 있으시면 언제든 말씀해주세요. 😊")
    
    integrated_response = "\n\n".join(response_parts)
    
    return {
        **state,
        "conversation_context": integrated_response
    }

def get_place_from_recommendations(place_id: str, table_name: str) -> dict:
    """place_recommendations 테이블에서 place_id와 table_name으로 정확한 정보 조회"""
    try:
        from sqlalchemy import text

        # DB 연결
        engine = shared_engine

        with engine.connect() as conn:
            # place_id와 table_name으로 정확한 조회
            search_query = """
            SELECT place_id, table_name, name, region, city, category,
                   latitude, longitude, overview
            FROM place_recommendations
            WHERE place_id = :place_id AND table_name = :table_name
            LIMIT 1
            """

            result = conn.execute(text(search_query), {
                "place_id": place_id,
                "table_name": table_name
            })
            row = result.fetchone()

            if row:
                return {
                    "place_id": str(row.place_id),
                    "table_name": row.table_name,
                    "name": row.name,
                    "region": row.region,
                    "city": row.city,
                    "category": row.category,
                    "latitude": row.latitude if hasattr(row, 'latitude') else None,
                    "longitude": row.longitude if hasattr(row, 'longitude') else None,
                    "overview": row.overview if hasattr(row, 'overview') else "",
                    "description": f"장소: {row.name}"
                }
            else:
                print(f"❌ place_recommendations에서 찾을 수 없음: place_id={place_id}, table_name={table_name}")
                return None

    except Exception as e:
        print(f"place_recommendations 검색 오류: {e}")
        return None

def find_place_in_recommendations(place_name: str) -> dict:
    """place_recommendations 테이블에서 장소명으로 실제 데이터 검색 (정규화된 이름으로 검색)"""
    try:
        from sqlalchemy import text

        # DB 연결
        engine = shared_engine
        
        # 정규화된 장소명으로 검색
        normalized_name = normalize_place_name(place_name)
        print(f"   🔎 DB 검색 - 원본: '{place_name}' -> 정규화: '{normalized_name}'")

        with engine.connect() as conn:
            # 1. 정규화된 이름으로 정확한 매칭 시도
            search_query = """
            SELECT place_id, table_name, name, region, city, category
            FROM place_recommendations
            WHERE LOWER(REPLACE(REPLACE(name, '[한국관광 품질인증/Korea Quality]', ''), '[Korea Quality]', '')) ILIKE :exact_term
            LIMIT 1
            """
            
            result = conn.execute(text(search_query), {'exact_term': f"%{normalized_name}%"})
            row = result.fetchone()
            
            # 2. 정확한 매칭 실패 시 부분 매칭 시도
            if not row:
                search_query = """
                SELECT place_id, table_name, name, region, city, category
                FROM place_recommendations
                WHERE name ILIKE :partial_term
                LIMIT 1
                """
                
                result = conn.execute(text(search_query), {'partial_term': f"%{normalized_name}%"})
                row = result.fetchone()

            if row:
                print(f"   ✅ DB 매칭 성공: '{row.name}' (ID: {row.place_id})")
                return {
                    'name': row.name,
                    'place_id': str(row.place_id) if row.place_id else "1",
                    'table_name': row.table_name or 'accommodation',
                    'region': row.region or '서울특별시',
                    'city': row.city or '서울시',
                    'category': row.category or '숙박',
                    'description': f'장소: {row.name}',
                    'similarity_score': 0.9
                }
            else:
                print(f"   ❌ DB에서 매칭 실패: '{normalized_name}' 찾을 수 없음")

        return None

    except Exception as e:
        print(f"place_recommendations 검색 오류: {e}")
        return None

def find_real_place_id(place_name: str, table_name: str, region: str = "") -> str:
    """장소명으로 실제 DB에서 place_id 조회"""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models_attractions import Nature, Restaurant, Shopping, Accommodation, Humanities, LeisureSports
        
        # 테이블 매핑
        table_models = {
            "nature": Nature,
            "restaurants": Restaurant,
            "shopping": Shopping,
            "accommodation": Accommodation,
            "humanities": Humanities,
            "leisure_sports": LeisureSports
        }
        
        if table_name not in table_models:
            print(f"❌ 지원하지 않는 table_name: {table_name}")
            return None  # 기본값 "1" 대신 None 반환
            
        # DB 연결
        import os
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:1234@localhost:5432/witple')
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            table_model = table_models[table_name]
            
            # 장소명으로 검색 (정확한 매칭 우선)
            query = session.query(table_model).filter(table_model.name.ilike(f"%{place_name}%"))
            
            # 지역 정보가 있으면 추가 필터링
            if region:
                query = query.filter(table_model.region.ilike(f"%{region}%"))
            
            place = query.first()
            
            if place:
                return str(place.id)
            else:
                # 매칭되지 않으면 None 반환 (무등산 주상절리대 fallback 방지)
                print(f"❌ 장소명 '{place_name}'이 {table_name} 테이블에서 찾을 수 없음")
                return None
                
        finally:
            session.close()
            
    except Exception as e:
        print(f"place_id 조회 오류: {e}")
        return None  # 오류 시 기본값 "1" 대신 None 반환

def extract_structured_places(docs: List[Document]) -> List[dict]:
    """RAG 검색 결과에서 구조화된 장소 정보 추출 (업데이트된 메타데이터 활용)"""
    structured_places = []

    for doc in docs[:20]:  # 상위 20개만 처리
        try:
            # 메타데이터에서 직접 정보 추출 (벡터 업데이트 후)
            metadata = doc.metadata or {}

            # 메타데이터에서 place_id와 table_name 추출
            place_id = metadata.get("place_id")
            table_name = metadata.get("table_name")

            # place_id와 table_name이 있으면 DB에서 정확한 정보 조회
            if place_id and table_name and place_id != "1":
                db_place = get_place_from_recommendations(place_id, table_name)
                if db_place:
                    place_info = {
                        **db_place,  # DB에서 가져온 정확한 정보 사용
                        "description": doc.page_content[:200],  # 첫 200자
                        "similarity_score": metadata.get('similarity_score', 0)
                    }
                else:
                    # DB 조회 실패 시 메타데이터 사용 (fallback)
                    place_info = {
                        "name": metadata.get("name", "장소명 미상"),
                        "category": metadata.get("category", ""),
                        "region": metadata.get("region", ""),
                        "city": metadata.get("city", ""),
                        "table_name": table_name,
                        "place_id": place_id,
                        "description": doc.page_content[:200],
                        "similarity_score": metadata.get('similarity_score', 0)
                    }
            else:
                # 메타데이터가 불완전한 경우 기존 방식 사용
                place_info = {
                    "name": metadata.get("name", ""),
                    "category": metadata.get("category", ""),
                    "region": metadata.get("region", ""),
                    "city": metadata.get("city", ""),
                    "table_name": metadata.get("table_name", "nature"),
                    "place_id": place_id or "unknown",  # "1" 대신 "unknown" 사용
                    "description": doc.page_content[:200],
                    "similarity_score": metadata.get('similarity_score', 0)
                }

            # 메타데이터에 name이 없으면 문서 내용에서 추출 (호환성 보장)
            if not place_info["name"]:
                content = doc.page_content
                first_line = content.split('\n')[0] if content else ""
                if first_line and len(first_line) < 50:
                    # "이름: " 접두어 제거
                    name = first_line.strip()
                    if name.startswith("이름: "):
                        name = name[3:].strip()
                    place_info["name"] = name
                else:
                    # 패턴으로 장소명 추출
                    import re
                    name_patterns = [
                        r'([가-힣]{2,20}(?:공원|박물관|맛집|카페|시장|궁|절|타워|센터|몰|해수욕장|산|섬))',
                        r'([가-힣]{2,20}(?:식당|레스토랑))',
                    ]

                    for pattern in name_patterns:
                        match = re.search(pattern, content)
                        if match:
                            place_info["name"] = match.group(1)
                            break

                    if not place_info["name"]:
                        words = content.split()[:3]
                        place_info["name"] = " ".join(words) if words else "장소명 미상"

            # table_name이 없으면 카테고리로 매핑 (호환성 보장)
            if not place_info["table_name"] or place_info["table_name"] == "nature":
                category_to_table = {
                    "한식": "restaurants", "중식": "restaurants", "양식": "restaurants",
                    "일식": "restaurants", "카페": "restaurants", "식당": "restaurants",
                    "맛집": "restaurants", "자연": "nature", "관광": "nature",
                    "문화": "humanities", "쇼핑": "shopping",
                    "레포츠": "leisure_sports", "스포츠": "leisure_sports",
                    "숙박": "accommodation", "펜션": "accommodation", "호텔": "accommodation"
                }
                place_info["table_name"] = category_to_table.get(place_info["category"], "nature")

            # 위치 정보 추출
            place_info["latitude"] = metadata.get("latitude")
            place_info["longitude"] = metadata.get("longitude")

            structured_places.append(place_info)

        except Exception as e:
            print(f"장소 정보 추출 오류: {e}")
            continue

    return structured_places

def extract_places_from_response(response: str, structured_places: List[dict]) -> List[dict]:
    """LLM 응답에서 실제 언급된 장소들만 추출하여 매칭"""
    
    # 응답에서 <strong>장소명</strong> 패턴으로 장소 추출
    place_pattern = r'<strong>([^<]+)</strong>'
    mentioned_places = re.findall(place_pattern, response)
    
    # 매칭된 장소들 저장
    matched_places = []
    
    # 일정 관련 키워드 필터링 (더 정밀하게)
    ignore_keywords = ['일차', '여행', '일정', '팁', '정보', '확정', '[', ']']
    # 지역명만 포함하는 경우는 제외 (예: "부산", "서울")
    region_only_keywords = ['부산', '서울', '제주', '강릉', '대구', '광주', '전주', '경주']
    
    for mentioned_place in mentioned_places:
        mentioned_place = mentioned_place.strip()
    
        # 일정 관련 키워드 제외
        if any(keyword in mentioned_place for keyword in ignore_keywords):
            continue
            
        # 지역명만 단독으로 나오는 경우 제외 (예: "부산", "서울")
        if mentioned_place.strip() in region_only_keywords:
            continue
        
        # 너무 짧거나 긴 장소명 제외
        if len(mentioned_place) < 2 or len(mentioned_place) > 50:  # 길이 제한 완화
            print(f"🚫 장소명 길이 부적합: '{mentioned_place}' (길이: {len(mentioned_place)})")
            continue
        
        print(f"🔍 장소 매칭 시도: '{mentioned_place}'")
            
        # structured_places에서 가장 유사한 장소 찾기 (정규화된 이름으로 비교)
        best_match = None
        best_score = 0
        
        # 언급된 장소명 정규화 
        mentioned_place_normalized = normalize_place_name(mentioned_place)
        print(f"   📝 정규화된 이름: '{mentioned_place}' -> '{mentioned_place_normalized}'")
        
        for place in structured_places:
            place_name = place.get("name", "").strip()
            place_name_normalized = normalize_place_name(place_name)

            # LLM이 생성한 장소는 모두 포함 (지역 필터링 제거)
            # LLM이 이미 적절한 판단을 했다고 신뢰
            
            # 정규화된 이름으로 정확히 일치하는 경우
            if mentioned_place_normalized == place_name_normalized:
                best_match = place
                best_score = 1.0
                print(f"   ✅ 정확 매칭: '{mentioned_place_normalized}' == '{place_name_normalized}'")
                break
            
            # 부분 문자열 매칭 (정규화된 이름으로)
            if (mentioned_place_normalized and place_name_normalized and 
                (mentioned_place_normalized in place_name_normalized or place_name_normalized in mentioned_place_normalized)):
                # 더 긴 매칭일수록 높은 점수
                score = min(len(mentioned_place_normalized), len(place_name_normalized)) / max(len(mentioned_place_normalized), len(place_name_normalized))
                if score > best_score:
                    best_score = score
                    best_match = place
                    print(f"   📈 부분 매칭: '{mentioned_place_normalized}' <-> '{place_name_normalized}' (점수: {score:.2f})")
        
        # 매칭 점수를 더 관대하게 (0.2 -> 0.1) 서울 지역 장소 포함성 향상
        if best_match and best_score >= 0.1:
            if best_match not in matched_places:
                print(f"✅ 장소 매칭 성공: '{mentioned_place}' -> '{best_match.get('name', 'Unknown')}' (점수: {best_score:.2f})")
                matched_places.append(best_match)
        else:
            # 매칭 실패한 경우
            if not best_match:
                print(f"❌ 매칭 실패: '{mentioned_place}' (구조화된 장소에서 찾을 수 없음)")
            elif best_score < 0.1:
                print(f"❌ 매칭 점수 부족: '{mentioned_place}' (최고 점수: {best_score:.2f} < 0.1)")
            
            # DB에서 직접 검색 시도
            if len(mentioned_place) >= 2:
                print(f"🔎 DB에서 장소 검색 시도: '{mentioned_place}'")
                actual_place = find_place_in_recommendations(mentioned_place)
                if actual_place:
                    print(f"✅ DB에서 찾음: '{actual_place.get('name', 'Unknown')}'")
                    matched_places.append(actual_place)
                else:
                    print(f"❌ DB에서도 찾을 수 없음: '{mentioned_place}' - 지도 표시에서 제외")
    
    return matched_places

def parse_enhanced_travel_plan(response: str, user_query: str, structured_places: List[dict]) -> dict:
    """향상된 여행 일정 파싱 (실제 장소 데이터 포함)"""

    # 기본 정보 추출
    regions, cities, categories = extract_location_and_category(user_query)
    duration = extract_duration(user_query)

    # 일차별 구조 파싱 (더 유연한 패턴)
    day_patterns = [
        r'<strong>\[(\d+)일차\]</strong>',  # <strong>[1일차]</strong>
        r'\[(\d+)일차\]',                    # [1일차]
        r'(\d+)일차',                        # 1일차
        r'<strong>(\d+)일차</strong>'         # <strong>1일차</strong>
    ]

    # 가장 많이 매칭되는 패턴 사용
    best_pattern = None
    best_matches = []

    for pattern in day_patterns:
        matches = re.findall(pattern, response)
        if len(matches) > len(best_matches):
            best_matches = matches
            best_pattern = pattern

    itinerary = []

    if best_pattern and best_matches:
        print(f"🗓️ 일차 패턴 인식: {len(best_matches)}개 일차 발견")

        # 응답을 일차별로 분할
        day_sections = re.split(best_pattern, response)

        for i in range(1, len(day_sections), 2):  # 홀수 인덱스가 일차 번호, 짝수가 내용
            if i + 1 < len(day_sections):
                day_num_str = day_sections[i]
                day_content = day_sections[i + 1]

                try:
                    day_num = int(day_num_str)
                except ValueError:
                    continue

                # 해당 일차의 일정 파싱
                day_schedule = parse_day_schedule(day_content, structured_places)

                if day_schedule:  # 일정이 있을 때만 추가
                    itinerary.append({
                        "day": day_num,
                        "schedule": day_schedule
                    })
    else:
        print(f"⚠️ 일차 패턴 인식 실패, 단일 일정으로 처리")
        # 일차 구분 없이 전체를 하나의 일정으로 처리
        single_day_schedule = parse_day_schedule(response, structured_places)
        if single_day_schedule:
            itinerary.append({
                "day": 1,
                "schedule": single_day_schedule
            })

    # 실제 응답에 포함된 장소들만 추출 (LLM 판단 신뢰)
    response_places = extract_places_from_response(response, structured_places)

    # 상세 여행 계획 구조
    enhanced_plan = {
        "region": regions[0] if regions else "미지정",
        "cities": cities,
        "duration": duration,
        "categories": list(set(categories + [place["category"] for place in response_places if place.get("category")])),
        "itinerary": itinerary,
        "places": response_places,  # 실제 응답에 포함된 장소들만
        "raw_response": response,
        "status": "draft",
        "created_at": "2025-09-13T00:00:00Z",  # 실제로는 datetime.now()
        "total_places": len(structured_places),
        "confidence_score": calculate_plan_confidence(structured_places, response)
    }

    print(f"✨ 일정 파싱 완료: {len(itinerary)}일차, 총 {sum(len(day.get('schedule', [])) for day in itinerary)}개 일정")

    return enhanced_plan

def parse_day_schedule(day_content: str, structured_places: List[dict]) -> List[dict]:
    """하루 일정 파싱 (개선된 패턴 인식)"""

    schedule = []

    # 더 유연한 패턴들 (다양한 형식 지원)
    patterns = [
        # • 09:00-12:00 <strong>장소명</strong> - 설명
        r'•\s*(\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?)\s*<strong>([^<\n]+)</strong>\s*-\s*([^\n]+)',
        # • 09:00 <strong>장소명</strong> - 설명 (단일 시간)
        r'•\s*(\d{1,2}:\d{2})\s*<strong>([^<\n]+)</strong>\s*-\s*([^\n]+)',
        # • <strong>장소명</strong> (09:00-12:00) - 설명
        r'•\s*<strong>([^<\n]+)</strong>\s*\((\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?)\)\s*-\s*([^\n]+)',
        # 시간 없이: • <strong>장소명</strong> - 설명
        r'•\s*<strong>([^<\n]+)</strong>\s*-\s*([^\n]+)'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, day_content)

        for match in matches:
            if len(match) == 3:
                if pattern == patterns[2]:  # 3번째 패턴 (장소명이 첫 번째)
                    place_name, time_range, description = match
                else:
                    time_range, place_name, description = match
            elif len(match) == 2:  # 시간 없는 경우
                place_name, description = match
                time_range = ""
            else:
                continue

            # 장소명 정리
            place_name_clean = normalize_place_name(place_name)

            # 구조화된 장소에서 매칭되는 정보 찾기 (개선된 매칭)
            matched_place = None
            best_score = 0

            for place in structured_places:
                place_name_normalized = normalize_place_name(place.get("name", ""))

                # 정확한 매칭
                if place_name_clean == place_name_normalized:
                    matched_place = place
                    break

                # 부분 매칭
                if place_name_clean and place_name_normalized:
                    if place_name_clean in place_name_normalized or place_name_normalized in place_name_clean:
                        score = min(len(place_name_clean), len(place_name_normalized)) / max(len(place_name_clean), len(place_name_normalized))
                        if score > best_score:
                            best_score = score
                            matched_place = place

            schedule_item = {
                "time": time_range.strip() if time_range else "",
                "place_name": place_name.strip(),
                "description": description.strip(),
                "category": matched_place.get("category", "") if matched_place else "",
                "place_info": matched_place
            }
            schedule.append(schedule_item)

    # 중복 제거 (같은 장소명과 시간)
    seen = set()
    unique_schedule = []
    for item in schedule:
        key = (item["place_name"], item["time"])
        if key not in seen:
            seen.add(key)
            unique_schedule.append(item)

    return unique_schedule

def calculate_plan_confidence(structured_places: List[dict], response: str) -> float:
    """여행 계획의 신뢰도 점수 계산"""
    
    score = 0.0
    max_score = 100.0
    
    # 장소 정보 품질 (40점)
    if structured_places:
        avg_similarity = sum(place.get("similarity_score", 0) for place in structured_places) / len(structured_places)
        score += avg_similarity * 40
    
    # 응답 구조화 정도 (30점)
    structure_indicators = ["<strong>[", "일차]", "•", ":**", "💡"]
    structure_score = sum(10 for indicator in structure_indicators if indicator in response)
    score += min(structure_score, 30)
    
    # 응답 길이 적절성 (20점)
    response_length = len(response)
    if 200 <= response_length <= 1000:
        score += 20
    elif 100 <= response_length <= 1500:
        score += 15
    else:
        score += 10
    
    # 시간 정보 포함 여부 (10점)
    time_patterns = re.findall(r'\d{2}:\d{2}', response)
    if len(time_patterns) >= 3:
        score += 10
    elif len(time_patterns) >= 1:
        score += 5
    
    return min(score, max_score) / max_score

def parse_travel_plan(response: str, user_query: str) -> dict:
    """응답에서 여행 일정 구조 추출"""
    
    # 지역 추출
    regions, cities, categories = extract_location_and_category(user_query)
    
    # 시간 패턴 찾기 (09:00, 12:00 등)
    time_pattern = r'\d{2}:\d{2}'
    times = re.findall(time_pattern, response)
    
    # 장소명 추출 (간단한 패턴 매칭)
    location_pattern = r'[가-힣]{2,10}(?:공원|박물관|맛집|카페|시장|궁|절|타워|센터|몰)'
    locations = re.findall(location_pattern, response)
    
    return {
        "region": regions[0] if regions else "미지정",
        "cities": cities,
        "duration": extract_duration(user_query),
        "locations": list(set(locations)),  # 중복 제거
        "times": times,
        "categories": categories,
        "raw_response": response,
        "status": "draft"
    }

def extract_duration(query: str) -> str:
    """쿼리에서 여행 기간 추출"""
    duration_patterns = [
        r'(\d+)박\s*(\d+)일',
        r'(\d+)일',
        r'당일',
        r'하루'
    ]
    
    for pattern in duration_patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(0)
    
    return "미지정"

def route_execution(state: TravelState) -> str:
    """단일 노드 실행을 위한 라우팅 결정 (우선순위 기반)"""
    
    # 확정 요청이 최고 우선순위
    if state.get("need_confirmation"):
        return "confirmation_processing"
    
    # RAG가 가장 중요한 기능
    if state.get("need_rag"):
        return "rag_processing"
    
    # 장소 검색
    if state.get("need_search"):
        return "search_processing"
    
    # 도구 실행
    if state.get("need_tool"):
        return "tool_execution"
    
    # 기본: 일반 채팅
    return "general_chat"

def check_completion(state: TravelState) -> Literal["continue", "end"]:
    """대화 완료 여부 확인"""
    # 확정된 일정이 있고 도구 실행 결과가 있으면 종료
    if (state.get("travel_plan", {}).get("status") == "confirmed" and 
        state.get("tool_results", {}).get("action") == "redirect_to_planning_page"):
        return "end"
    
    # 기본적으로 대화 지속
    return "continue"

# LangGraph 워크플로우 구성
def create_travel_workflow():
    """여행 추천 LangGraph 워크플로우 생성"""
    if not LANGGRAPH_AVAILABLE:
        return None
    
    workflow = StateGraph(TravelState)
    
    # 노드 추가
    workflow.add_node("classify", classify_query)
    workflow.add_node("rag_processing", rag_processing_node)
    workflow.add_node("search_processing", search_processing_node)
    workflow.add_node("tool_execution", tool_execution_node)
    workflow.add_node("general_chat", general_chat_node)
    workflow.add_node("confirmation_processing", confirmation_processing_node)
    workflow.add_node("integrate_response", integrate_response_node)
    
    # 엣지 구성
    workflow.add_edge(START, "classify")
    workflow.add_conditional_edges("classify", route_execution)
    
    # 모든 처리 노드들이 통합 노드로 수렴
    workflow.add_edge("rag_processing", "integrate_response")
    workflow.add_edge("search_processing", "integrate_response")
    workflow.add_edge("tool_execution", "integrate_response")
    workflow.add_edge("general_chat", "integrate_response")
    workflow.add_edge("confirmation_processing", "integrate_response")
    
    # 완료 확인
    workflow.add_conditional_edges(
        "integrate_response",
        check_completion,
        {
            "continue": END,  # 추가 대화 없이 종료로 변경
            "end": END
        }
    )
    
    return workflow.compile()

# 전역 워크플로우 인스턴스
travel_workflow = create_travel_workflow() if LANGGRAPH_AVAILABLE else None

# 개선된 상태 관리: 세션 대신 인메모리 상태 (새 추천시 덮어쓰기)
current_travel_state = {
    "last_query": "",
    "travel_plan": {},
    "places": [],
    "context": "",
    "timestamp": None
}

def get_current_travel_state_ref():
    """현재 여행 상태 반환 (참조 동기화를 위한 함수)"""
    global current_travel_state
    return current_travel_state

async def get_travel_recommendation_langgraph_stream(query: str):
    """LangGraph 기반 실시간 스트리밍 여행 추천"""
    global current_travel_state
    import asyncio
    import datetime

    if not travel_workflow:
        # LangGraph 미사용 시 기존 함수로 폴백
        yield {'type': 'status', 'content': 'LangGraph 시스템 준비 중...'}
        result = get_travel_recommendation(query, stream=False)

        # 텍스트를 청크로 나누어 스트리밍
        chunks = [result[i:i+10] for i in range(0, len(result), 10)]
        for chunk in chunks:
            yield {'type': 'content', 'content': chunk}
            await asyncio.sleep(0.1)

        yield {'type': 'metadata', 'travel_plan': {}, 'tool_results': {}}
        return

    print(f"🚀 LangGraph 스트리밍 워크플로우 실행: '{query}'")

    try:
        # 확정이 아닌 새 여행 추천 요청시에만 기존 상태 초기화
        is_confirmation = any(keyword in query.lower() for keyword in ["확정", "결정", "좋아", "이걸로", "ok", "오케이"])
        is_new_travel_request = any(keyword in query.lower() for keyword in ["추천", "여행", "일정", "계획", "박", "일"])

        if is_confirmation and current_travel_state.get("travel_plan"):
            print("🎯 확정 요청 - 기존 상태 유지")
            # 기존 상태 유지하면서 마지막 쿼리만 업데이트
            current_travel_state["last_query"] = query
            current_travel_state["timestamp"] = datetime.datetime.now().isoformat()
        elif is_new_travel_request and not is_confirmation:
            print("🔄 새로운 여행 추천 - 기존 상태 초기화")
            current_travel_state = {
                "last_query": query,
                "travel_plan": {},
                "places": [],
                "context": "",
                "timestamp": datetime.datetime.now().isoformat()
            }
        else:
            print("🔍 기타 요청 - 기존 상태 유지하며 쿼리 추가")
            # 날씨 질문 등 기타 요청시 기존 상태 유지
            current_travel_state["last_query"] = query
            current_travel_state["timestamp"] = datetime.datetime.now().isoformat()

        # 상태 생성
        if not conversation_history:
            conversation_history = []

        # 메시지 히스토리에 새 쿼리 추가
        messages = conversation_history + [query]

        # 전역 상태에서 기존 여행 계획 가져오기 (컨텍스트 유지)
        existing_travel_plan = current_travel_state.get("travel_plan", {})
        print(f"🔄 기존 여행 계획 상태: {bool(existing_travel_plan)}")

        initial_state = {
            "messages": messages,
            "query_type": "unknown",
            "need_rag": False,
            "need_search": False,
            "need_tool": False,
            "need_confirmation": False,
            "history": " ".join(messages),
            "rag_results": [],
            "search_results": [],
            "tool_results": {},
            "travel_plan": existing_travel_plan,  # 기존 여행 계획 포함
            "user_preferences": {},
            "conversation_context": "",
            "formatted_ui_response": {}
        }

        yield {'type': 'status', 'content': '🔍 여행 요청을 분석하고 있습니다...'}

        # 워크플로우 실행 (스트리밍)
        response_text = ""
        final_state = None

        # LangGraph 워크플로우를 단계별로 실행하면서 스트리밍
        for step_output in travel_workflow.stream(initial_state):
            print(f"🔄 워크플로우 단계: {step_output}")

            # 각 단계의 출력을 분석해서 스트리밍 데이터 생성
            if isinstance(step_output, dict):
                for node_name, node_state in step_output.items():
                    if node_name == "classify_query":
                        yield {'type': 'status', 'content': '📋 질문 유형을 분석했습니다...'}
                    elif node_name == "handle_rag":
                        yield {'type': 'status', 'content': '🔍 관련 여행지 정보를 검색했습니다...'}
                    elif node_name == "generate_response":
                        yield {'type': 'status', 'content': '✨ AI가 추천을 생성하고 있습니다...'}

                        # 응답 텍스트가 있으면 스트리밍
                        if 'conversation_context' in node_state:
                            new_content = node_state['conversation_context']
                            if new_content and new_content != response_text:
                                chunk = new_content[len(response_text):]
                                response_text = new_content

                                # 텍스트를 작은 청크로 스트리밍
                                for char in chunk:
                                    yield {'type': 'content', 'content': char}
                                    await asyncio.sleep(0.02)

                    final_state = node_state

        # 최종 상태 업데이트
        if final_state:
            # places는 tool_results가 아닌 travel_plan에서 직접 가져오기
            places = []
            if final_state.get("tool_results", {}).get("places"):
                # 확정 시 tool_results에서 places 가져오기
                places = final_state.get("tool_results", {}).get("places", [])
            elif final_state.get("travel_plan", {}).get("places"):
                # 일반 여행 추천 시 travel_plan에서 places 가져오기
                places = final_state.get("travel_plan", {}).get("places", [])

            current_travel_state.update({
                "travel_plan": final_state.get('travel_plan', {}),
                "places": places,
                "context": final_state.get('conversation_context', ''),
                "last_query": query,
                "timestamp": datetime.datetime.now().isoformat()
            })
            print(f"💾 스트리밍 여행 상태 저장 완료: {len(places)}개 장소")

            # 메타데이터 전송
            yield {
                'type': 'metadata',
                'travel_plan': final_state.get('travel_plan', {}),
                'action_required': final_state.get('tool_results', {}).get('action_required'),
                'tool_results': final_state.get('tool_results', {})
            }

        print("✅ LangGraph 스트리밍 워크플로우 완료!")

    except Exception as e:
        print(f"❌ LangGraph 스트리밍 워크플로우 오류: {e}")
        yield {'type': 'status', 'content': f'⚠️ 처리 중 오류가 발생했습니다: {str(e)}'}

        # 오류 시 기존 시스템으로 폴백
        result = get_travel_recommendation(query, stream=False)
        yield {'type': 'content', 'content': result}
        yield {'type': 'metadata', 'travel_plan': {}, 'tool_results': {}}

def get_travel_recommendation_langgraph(query: str, conversation_history: List[str] = None, session_id: str = "default") -> dict:
    """LangGraph 기반 여행 추천 (개선된 상태 관리 - 새 추천시 덮어쓰기)"""
    import datetime

    if not travel_workflow:
        # LangGraph 미사용 시 기존 함수로 폴백
        response = get_travel_recommendation(query, stream=False)
        return {
            "response": response,
            "travel_plan": {},
            "action_required": None,
            "conversation_context": response
        }
    
    print(f"🚀 LangGraph 워크플로우 실행: '{query}' (세션: {session_id})")
    
    try:
        # 대화 기록이 있으면 포함 (현재는 단일 메시지만 처리)
        messages = [query]
        if conversation_history and isinstance(conversation_history, list):
            messages = conversation_history + [query]
        
        # 쿼리 타입 분석
        is_confirmation = any(keyword in query.lower() for keyword in ["확정", "결정", "좋아", "이걸로", "ok", "오케이"])
        is_new_travel_request = any(keyword in query.lower() for keyword in ["추천", "여행", "일정", "계획", "박", "일"])
        is_weather_query = any(keyword in query.lower() for keyword in ["날씨", "기온", "온도"])

        global current_travel_state

        # 디버깅 정보
        print(f"🔍 쿼리 분석: 확정={is_confirmation}, 새여행={is_new_travel_request}, 날씨={is_weather_query}")
        print(f"🔍 기존 상태: {bool(current_travel_state.get('travel_plan'))}")

        # 새 여행 추천일 때만 상태 초기화 (확정이 아닌 경우에만)
        if is_new_travel_request and not is_confirmation:
            print("🔄 새로운 여행 추천 - 상태 초기화")
            current_travel_state.clear()
            current_travel_state.update({
                "last_query": query,
                "travel_plan": {},
                "places": [],
                "context": "",
                "timestamp": datetime.datetime.now().isoformat()
            })
        else:
            print("💾 기존 상태 유지")
            current_travel_state["last_query"] = query
            current_travel_state["timestamp"] = datetime.datetime.now().isoformat()

        # 전역 상태에서 기존 여행 계획 가져오기
        existing_travel_plan = current_travel_state.get("travel_plan", {})
        print(f"🔄 사용할 여행 계획: {bool(existing_travel_plan)}")

        # 초기 상태 설정 (간소화)
        initial_state = {
            "messages": messages,
            "query_type": "",
            "need_rag": False,
            "need_search": False,
            "need_tool": False,
            "need_confirmation": False,
            "history": " ".join(messages),
            "rag_results": [],
            "search_results": [],
            "tool_results": {},
            "travel_plan": existing_travel_plan,  # 기존 여행 계획 포함
            "user_preferences": {},
            "conversation_context": "",
            "formatted_ui_response": {}
        }

        # 워크플로우 실행
        final_state = travel_workflow.invoke(initial_state)

        # 전역 상태 업데이트 (새 추천으로 덮어쓰기)
        if final_state.get("travel_plan"):
            # places는 tool_results가 아닌 travel_plan에서 직접 가져오기
            places = []
            if final_state.get("tool_results", {}).get("places"):
                # 확정 시 tool_results에서 places 가져오기
                places = final_state.get("tool_results", {}).get("places", [])
            elif final_state.get("travel_plan", {}).get("places"):
                # 일반 여행 추천 시 travel_plan에서 places 가져오기
                places = final_state.get("travel_plan", {}).get("places", [])

            current_travel_state.update({
                "travel_plan": final_state.get("travel_plan", {}),
                "places": places,
                "context": final_state.get("conversation_context", ""),
                "last_query": query,
                "timestamp": datetime.datetime.now().isoformat()
            })
            print(f"💾 새로운 여행 상태 저장 완료: {len(places)}개 장소")
        
        # 구조화된 응답 반환
        tool_results = final_state.get("tool_results", {})
        return {
            "response": final_state.get("conversation_context", "응답을 생성할 수 없습니다."),
            "travel_plan": final_state.get("travel_plan", {}),
            "action_required": tool_results.get("action"),
            "redirect_url": tool_results.get("redirect_url"),
            "places": tool_results.get("places"),
            "raw_state": final_state,
            "success": True
        }
        
    except Exception as e:
        print(f"❌ LangGraph 워크플로우 오류: {e}")
        # 오류 시 기존 시스템으로 폴백
        response = get_travel_recommendation(query, stream=False)
        return {
            "response": response,
            "travel_plan": {},
            "action_required": None,
            "conversation_context": response,
            "success": False,
            "error": str(e)
        }

# =============================================================================
# 메인 실행부
# =============================================================================

if __name__ == "__main__":
    # AWS 자격 증명 확인
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        print("⚠️ 경고: AWS 자격 증명이 설정되지 않았습니다.")
        print("환경변수 AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY를 설정하거나")
        print("AWS CLI로 자격 증명을 구성해주세요.")
        print("자세한 내용: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html")
        sys.exit(1)
    
    print("\n🚀 하이브리드 최적화 RAG 시스템 (Amazon Bedrock) 초기화 완료!")
    print("📊 특징: SQL 1차 필터링 + 벡터 2차 검색으로 고속 정확 검색")
    print("🤖 AI 모델: Amazon Bedrock Claude")

    # 백엔드 시작 시 인기 문서 사전 캐싱
    print("🔥 인기 문서 사전 캐싱 시작...")
    if llm_cache.preload_popular_documents():
        print("✅ 인기 문서 캐싱 완료")

    # 주요 지역 문서 사전 캐싱
    print("🏗️ 주요 지역 문서 사전 캐싱 시작...")
    major_regions = ['서울특별시', '부산광역시', '제주특별자치도', '경기도']
    for region in major_regions:
        if llm_cache.preload_region_documents(region):
            print(f"✅ {region} 캐싱 완료")

    print("🎯 Redis 문서 캐시 프리로딩 완료!")

    try:
        interactive_mode()
            
    except KeyboardInterrupt:
        print("\n👋 시스템을 종료합니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")