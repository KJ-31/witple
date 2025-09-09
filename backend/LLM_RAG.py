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
from typing import List, Any
from sqlalchemy import create_engine, text
import sys
import os

# =============================================================================
# AWS 설정 및 초기화
# =============================================================================

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

# =============================================================================
# 설정 및 초기화
# =============================================================================

# 데이터베이스 연결 설정
CONNECTION_STRING = "postgresql+psycopg://postgres:witple123!@witple-pub-database.cfme8csmytkv.ap-northeast-2.rds.amazonaws.com:5432/witple_db"

# LLM 모델 설정 (Amazon Bedrock - Claude)
print("🤖 Amazon Bedrock Claude 모델 초기화 중...")
try:
    llm = ChatBedrock(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",  # Claude 3 Haiku
        # model_id="anthropic.claude-3-sonnet-20240229-v1:0",  # Claude 3 Sonnet (더 강력)
        region_name=AWS_REGION,
        credentials_profile_name=None,  # 기본 자격증명 사용
        model_kwargs={
            "temperature": 0.2,  # 낮을수록 일관된 답변 제공
            "max_tokens": 2000,  # 최대 토큰 수
            "top_p": 0.9,
        }
    )
except Exception as e:
    print(f"❌ Bedrock LLM 초기화 실패: {e}")
    print("환경변수나 AWS CLI 설정을 확인해주세요.")
    sys.exit(1)

# 임베딩 모델 설정 (384차원) - 로컬 HuggingFace 모델 사용
print("🧠 임베딩 모델 초기화 중...")
embeddings = HuggingFaceEmbeddings(
    model_name='sentence-transformers/all-MiniLM-L12-v2'
)

# Amazon Bedrock Embeddings 사용하려면 아래 코드로 교체:
# from langchain_aws import BedrockEmbeddings
# embeddings = BedrockEmbeddings(
#     model_id="amazon.titan-embed-text-v1",
#     boto3_session=boto3_session
# )

# =============================================================================
# 벡터스토어 연결
# =============================================================================

print("🔗 벡터스토어 연결 중...")
vectorstore = PGVector(
    embeddings=embeddings,
    collection_name="place_recommendations",  # 이관된 데이터가 있는 collection
    connection=CONNECTION_STRING,
    pre_delete_collection=False,  # 기존 데이터 보존
)

# =============================================================================
# 지역 및 키워드 인식 시스템
# =============================================================================

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
    
    # 지역 매칭 (부분 문자열 포함)
    for region in REGIONS:
        if region in query or region.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '') in query:
            found_regions.append(region)
    
    # 도시 매칭
    for city in CITIES:
        if city in query:
            found_cities.append(city)
    
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
            engine = create_engine(CONNECTION_STRING)
            
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

# 하이브리드 최적화 Retriever 생성
retriever = HybridOptimizedRetriever(vectorstore, k=10000, score_threshold=0.5, max_sql_results=5000)

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
    - 카테고리가 다르더라도 명소라 생각되면 답변해주세요
    - 중복된 추천은 반드시 제거해주세요
    - 한국어로 자연스럽게 작성하세요

답변:
""")

# =============================================================================
# RAG 체인 구성
# =============================================================================

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

# =============================================================================
# 주요 기능 함수들
# =============================================================================

def search_places(query):
    """여행지 검색 함수 (하이브리드 최적화)"""
    try:
        print(f"🔍 하이브리드 검색: '{query}'")
        
        # HybridOptimizedRetriever 직접 사용
        docs = retriever._get_relevant_documents(query)
        
        return docs
        
    except Exception as e:
        print(f"❌ 검색 오류: {e}")
        return []

def get_travel_recommendation(query, stream=True):
    """여행 추천 생성 함수 (스트림 지원)"""
    try:
        print(f"📍 여행 추천 요청: '{query}'")
        print("🔍 하이브리드 검색 시작...")
        
        if stream:
            return get_travel_recommendation_stream(query)
        else:
            # 기존 방식
            response = rag_chain.invoke(query)
            print("✅ 여행 추천 완료!")
            return response
        
    except Exception as e:
        print(f"❌ 추천 생성 오류: {e}")
        return "죄송합니다. 여행 추천을 생성하는 중 오류가 발생했습니다."

def get_travel_recommendation_stream(query):
    """스트림 방식 여행 추천 생성 (Amazon Bedrock 지원)"""
    try:
        # 검색 실행
        docs = retriever._get_relevant_documents(query)
        context = format_docs(docs)
        
        # 프롬프트 준비
        prompt_value = rag_prompt.invoke({"context": context, "question": query})
        
        print("🤖 Amazon Bedrock Claude 답변 생성 중...")
        print("─" * 40)
        
        # 스트림으로 답변 생성
        full_response = ""
        for chunk in llm.stream(prompt_value):
            if hasattr(chunk, 'content'):
                content = chunk.content
            else:
                content = str(chunk)
            
            if content:
                print(content, end='', flush=True)
                full_response += content
        
        print("\n" + "─" * 40)
        print("✅ 여행 추천 완료!")
        
        return full_response
        
    except Exception as e:
        print(f"❌ 스트림 추천 생성 오류: {e}")
        return "죄송합니다. 여행 추천을 생성하는 중 오류가 발생했습니다."

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
    
    try:
        interactive_mode()
            
    except KeyboardInterrupt:
        print("\n👋 시스템을 종료합니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

# =============================================================================
# 설치 및 설정 가이드
# =============================================================================

"""
Amazon Bedrock 사용을 위한 설정 가이드:

1. 필요한 패키지 설치:
   pip install boto3 langchain-aws

2. AWS 자격 증명 설정:
   방법 1: 환경변수 설정
   export AWS_ACCESS_KEY_ID="your-access-key"
   export AWS_SECRET_ACCESS_KEY="your-secret-key"
   
   방법 2: AWS CLI 설정
   aws configure
   
   방법 3: IAM Role (EC2에서 실행 시)

3. Amazon Bedrock 모델 액세스 권한:
   - AWS 콘솔에서 Bedrock 서비스로 이동
   - Model access 메뉴에서 원하는 모델 액세스 요청
   - Claude 모델: Anthropic Claude v2, Claude 3 Haiku, Claude 3 Sonnet 등

4. 지원되는 리전:
   - us-east-1 (버지니아 북부)
   - us-west-2 (오레곤)
   - ap-southeast-1 (싱가포르)
   등 (최신 정보는 AWS 문서 확인)

5. 비용 주의사항:
   - Bedrock은 사용량 기반 과금
   - 입력/출력 토큰 수에 따라 비용 발생
   - 모델별로 가격이 다름 (Claude 3 Haiku < Sonnet < Opus)

사용 예시:
python sample.py
"""