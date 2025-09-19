import boto3
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_postgres import PGVector
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from typing import List, Any, Literal, TypedDict, Optional
from sqlalchemy import text
from database import engine as shared_engine
import sys
import os
import json
import re
import datetime
import hashlib
import redis

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






# Weather 모듈 import
from weather import (
    get_weather_info,
    get_smart_weather_info,
    is_weather_query,
    is_historical_weather_query,
    get_historical_weather_info,
    extract_date_from_query,
    extract_region_from_query
)

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
    
    query_type = "complex" if sum([need_rag, need_search]) > 1 else "simple"
    
    print(f"   분류 결과 - RAG: {need_rag}, Search: {need_search}, 확정: {need_confirmation}")
    print(f"   여행 일정 존재: {has_travel_plan}")
    
    return {
        **state,
        "need_rag": need_rag,
        "need_search": need_search,
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
        
        # 지역 필터링 개선 (더 포괄적으로)
        if query_regions:
            print(f"🎯 지역 필터링: {query_regions}")
            region_docs = []
            
            for doc in docs:
                doc_region = doc.metadata.get('region', '').lower()
                doc_city = doc.metadata.get('city', '').lower()
                
                # 포괄적인 지역 매칭
                is_relevant = False
                for region in query_regions:
                    region_lower = region.lower()
                    
                    # 1. 정확한 지역명 매칭
                    if region_lower in doc_region:
                        is_relevant = True
                        break
                    
                    # 2. 특정 지역 요청 시 해당 광역시/도 전체 포함
                    elif '강릉' in region_lower and '강원' in doc_region:
                        is_relevant = True  # 강릉 요청 시 강원도 전체 포함
                        break
                    elif '부산' in region_lower and ('부산' in doc_region or '부산' in doc_city):
                        is_relevant = True  # 부산 요청 시 부산 전체 포함
                        break  
                    elif '서울' in region_lower and ('서울' in doc_region or '서울' in doc_city):
                        is_relevant = True  # 서울 요청 시 서울 전체 포함
                        break
                    elif '제주' in region_lower and '제주' in doc_region:
                        is_relevant = True  # 제주 요청 시 제주도 전체 포함
                        break
                
                if is_relevant:
                    region_docs.append(doc)
            
            if region_docs:
                docs = region_docs[:50]  # 더 많은 결과 허용
                print(f"📍 지역 필터링 결과: {len(docs)}개 문서 선별")
            else:
                print(f"⚠️ 지역 필터링 결과 없음, 전체 결과 사용")
                docs = docs[:50]
        
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
    """장소명 정규화 (매칭 정확도 향상)"""
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

            # place_id가 없거나 "1"이면 스킵 (무등산 주상절리대 방지)
            if not place_id or place_id == "1":
                print(f"⚠️ place_id 없음 - 장소 '{place.get('name', 'Unknown')}' 스킵")
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
    """place_recommendations 테이블에서 장소명으로 실제 데이터 검색 (벡터 업데이트 후 불필요)"""
    # 벡터 업데이트 후에는 메타데이터에 place_id, table_name이 포함되므로
    # 이 함수는 호환성을 위해서만 유지
    try:
        from sqlalchemy import text

        # DB 연결
        engine = shared_engine

        with engine.connect() as conn:
            # 유사한 이름으로 검색 (대소문자 구분 없이) - psycopg3 스타일
            search_query = """
            SELECT place_id, table_name, name, region, city, category
            FROM place_recommendations
            WHERE name ILIKE :search_term
            LIMIT 1
            """

            result = conn.execute(text(search_query), {'search_term': f"%{place_name}%"})
            row = result.fetchone()

            if row:
                return {
                    'name': row.name,
                    'place_id': str(row.place_id) if row.place_id else "1",
                    'table_name': row.table_name or 'nature',
                    'region': row.region or '강원특별자치도',
                    'city': row.city or '미지정',
                    'category': row.category or '관광',
                    'description': f'장소: {row.name}',
                    'similarity_score': 0.9
                }

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
        if len(mentioned_place) < 2 or len(mentioned_place) > 30:
            continue
            
        # structured_places에서 가장 유사한 장소 찾기
        best_match = None
        best_score = 0
        
        for place in structured_places:
            place_name = place.get("name", "").strip()

            # LLM이 생성한 장소는 모두 포함 (지역 필터링 제거)
            # LLM이 이미 적절한 판단을 했다고 신뢰
            
            # 정확히 일치하는 경우
            if mentioned_place == place_name:
                best_match = place
                best_score = 1.0
                break
            
            # 부분 문자열 매칭
            if mentioned_place in place_name or place_name in mentioned_place:
                # 더 긴 매칭일수록 높은 점수
                score = min(len(mentioned_place), len(place_name)) / max(len(mentioned_place), len(place_name))
                if score > best_score:
                    best_score = score
                    best_match = place
        
        # 매칭 점수가 0.2 이상이면 추가 (더 관대하게)
        if best_match and best_score >= 0.2:
            if best_match not in matched_places:
                matched_places.append(best_match)
        elif not best_match and len(mentioned_place) >= 3:
            # 실제 place_recommendations 테이블에서 해당 장소 검색
            actual_place = find_place_in_recommendations(mentioned_place)
            if actual_place:
                matched_places.append(actual_place)
            else:
                # 정말 찾을 수 없는 경우만 가상 장소 생성
                virtual_place = {
                    'name': mentioned_place,
                    'category': '관광',
                    'region': '강원특별자치도',
                    'city': '강릉시' if '강릉' in mentioned_place else '미지정',
                    'table_name': 'nature',
                    'place_id': "1",  # 찾을 수 없는 경우 기본 ID
                    'description': f'LLM 추천 장소: {mentioned_place}',
                    'similarity_score': 0.8
                }
                matched_places.append(virtual_place)
    
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
    workflow.add_node("general_chat", general_chat_node)
    workflow.add_node("confirmation_processing", confirmation_processing_node)
    workflow.add_node("integrate_response", integrate_response_node)
    
    # 엣지 구성
    workflow.add_edge(START, "classify")
    workflow.add_conditional_edges("classify", route_execution)
    
    # 모든 처리 노드들이 통합 노드로 수렴
    workflow.add_edge("rag_processing", "integrate_response")
    workflow.add_edge("search_processing", "integrate_response")
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


async def get_travel_recommendation_langgraph(query: str, conversation_history: List[str] = None, session_id: str = "default") -> dict:
    """LangGraph 기반 여행 추천 (개선된 상태 관리 - 새 추천시 덮어쓰기)"""
    import datetime

    if not travel_workflow:
        # LangGraph 미사용 시 에러 반환
        return {
            "response": "죄송합니다. 현재 여행 추천 시스템을 초기화하는 중입니다.",
            "travel_plan": {},
            "action_required": None,
            "conversation_context": "시스템 초기화 중",
            "success": False,
            "error": "LangGraph workflow not available"
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

        # 워크플로우 실행 (비동기)
        final_state = await travel_workflow.ainvoke(initial_state)

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
        # 오류 시 에러 응답 반환
        return {
            "response": f"죄송합니다. 처리 중 오류가 발생했습니다: {str(e)}",
            "travel_plan": {},
            "action_required": None,
            "conversation_context": f"Error: {str(e)}",
            "success": False,
            "error": str(e)
        }
