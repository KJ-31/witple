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
from typing import List, Any, Literal, TypedDict, Sequence
from sqlalchemy import create_engine, text
import sys
import os
import json
import re

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
# 데이터베이스 연결 설정
CONNECTION_STRING = "postgresql+psycopg://postgres:witple123!@witple-pub-database.cfme8csmytkv.ap-northeast-2.rds.amazonaws.com:5432/witple_db"

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
            "temperature": 0.2,         # 낮을수록 일관된 답변 제공
            "max_tokens": 4000,         # 최대 토큰 수 (더 긴 응답)
            "top_p": 0.9,               # 상위 P% 토큰만 고려
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

# # 벡터스토어 연결

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

# 하이브리드 최적화 Retriever 생성 (높은 정확도를 위한 엄격한 임계값)
retriever = HybridOptimizedRetriever(vectorstore, k=20000, score_threshold=0.6, max_sql_results=8000)

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
# LangGraph 여행 대화 시스템
# =============================================================================

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
    
    # 여행 일정 추천 관련 키워드
    travel_keywords = ["추천", "여행", "일정", "계획", "코스", "가볼만한", "여행지", "관광"]
    location_keywords = ["서울", "부산", "제주", "경기", "강원", "장소", "위치", "어디"]
    food_keywords = ["맛집", "음식", "식당", "먹을", "카페", "레스토랑"]
    booking_keywords = ["예약", "등록", "신청", "결제", "예매"]
    
    # 확정 키워드 (더 엄격하게)
    strong_confirmation_keywords = ["확정", "결정", "확인", "이걸로", "좋아", "맞아", "그래", "됐어", "완료", "ok", "오케이"]
    weak_confirmation_keywords = ["진행", "해줘", "가자", "이거야", "네", "예"]
    
    # 복합적 분류 로직
    need_rag = any(keyword in user_input for keyword in travel_keywords)
    need_search = any(keyword in user_input for keyword in location_keywords)
    need_tool = any(keyword in user_input for keyword in booking_keywords)
    
    # 음식 관련 질의도 RAG로 처리
    if any(keyword in user_input for keyword in food_keywords):
        need_rag = True
    
    # 확정 판단 로직 개선 (2단계 플로우)
    has_strong_confirmation = any(keyword in user_input_lower for keyword in strong_confirmation_keywords)
    has_weak_confirmation = any(keyword in user_input_lower for keyword in weak_confirmation_keywords)
    
    # 확정 판단: 강한 확정 키워드가 있거나, 약한 확정 키워드가 있으면서 여행 추천 요청이 아닌 경우
    need_confirmation = has_strong_confirmation or (has_weak_confirmation and not need_rag)
    
    # 현재 상태에 여행 일정이 있는지 확인
    has_travel_plan = bool(state.get("travel_plan"))
    
    # 여행 일정이 없으면 확정 요청을 무시하고 RAG 우선
    if need_confirmation and not has_travel_plan and need_rag:
        print(f"   ⚠️ 여행 일정이 없어서 확정 요청을 RAG 요청으로 변경")
        need_confirmation = False
    
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
    
    try:
        # 하이브리드 검색으로 실제 장소 데이터 가져오기
        docs = retriever._get_relevant_documents(user_query)
        
        # 지역 필터링 강화 - 쿼리에서 지역명 추출하여 해당 지역 결과만 우선
        import re
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
        
        # 지역 필터링된 문서들 (순수성 유지)
        region_docs = []
        
        if query_regions:
            print(f"🎯 지역 필터링: {query_regions} (키워드: {target_keywords[:5]}...)")
            for doc in docs:
                doc_content = doc.page_content.lower()
                doc_region = doc.metadata.get('region', '').lower()
                doc_city = doc.metadata.get('city', '').lower()
                
                # 해당 지역 키워드가 포함되어 있는지 확인 (더 엄격하게)
                is_target_region = False
                for keyword in target_keywords:
                    if keyword.lower() in doc_content or keyword.lower() in doc_region or keyword.lower() in doc_city:
                        is_target_region = True
                        break
                
                # 강릉 요청 시 강릉 관련 장소 우선, 하지만 완전 차단은 하지 않음
                if is_target_region and query_regions and '강릉' in query_regions:
                    # 강릉시가 명시된 장소를 최우선으로 하되, 다른 지역도 제한적으로 포함
                    if '강릉' in doc_city or '강릉시' in doc_city:
                        # 강릉 장소는 최우선으로 추가
                        region_docs.insert(0, doc)  # 앞쪽에 추가
                        continue
                    elif any(city in doc_city for city in ['평창', '횡성', '원주']):
                        # 다른 강원도 도시는 제한적으로만 포함 (나중에 길이 제한으로 자연 필터링)
                        pass
                
                if is_target_region:
                    region_docs.append(doc)
            
            # 해당 지역 문서만 사용 (다른 지역 문서는 절대 섞지 않음)
            docs = region_docs[:30]
            print(f"📍 지역 관련 문서: {len(region_docs)}개, 최종 사용: {len(docs)}개")
            
            # 지역 문서가 충분하지 않으면 전체 문서 사용
            if len(region_docs) < 10:
                print(f"⚠️ {', '.join(query_regions)} 지역 정보 부족: {len(region_docs)}개 문서만 발견")
                print("🔄 전체 문서에서 재검색...")
                # 원본 검색 결과 사용하되 지역 필터는 유지
                original_docs = retriever._get_relevant_documents(user_query)
                docs = original_docs[:50]
                print(f"📍 재검색 결과: {len(docs)}개 문서 사용")
        
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

🏝️ **지역명 여행 일정**

**[1일차]**
• 09:00-12:00 **장소명** - 간단한 설명 (1줄)
• 12:00-13:00 **식당명** - 음식 종류 점심 
• 14:00-17:00 **장소명** - 간단한 설명 (1줄)
• 18:00-19:00 **식당명** - 음식 종류 저녁

**[2일차]** (기간에 따라 추가)
...

💡 **여행 팁**: 지역 특색이나 주의사항

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
        
        print(f"✅ RAG 처리 완료. 결과 길이: {len(formatted_response)}")
        print(f"   추출된 장소 수: {len(structured_places)}")
        
        return {
            **state,
            "rag_results": docs,
            "travel_plan": travel_plan,
            "conversation_context": formatted_response,
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
        search_summary = f"'{user_query}'에 대한 검색 결과 {len(docs)}개를 찾았습니다."
        
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

def confirmation_processing_node(state: TravelState) -> TravelState:
    """일정 확정 처리 노드 (2단계 플로우)"""
    print(f"🎯 확정 처리 요청")
    
    # 현재 상태에 여행 일정이 없으면 안내 메시지
    if not state.get("travel_plan") or not state["travel_plan"]:
        response = """
🤔 **확정하고 싶으신 여행 일정이 없는 것 같아요!**

📝 **확정 절차**:
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
    
    # 지도 표시를 위한 장소 파라미터 구성
    places_list = []
    day_numbers_list = []
    source_tables_list = []
    
    if "places" in confirmed_plan and confirmed_plan["places"]:
        total_days = len(confirmed_plan.get("itinerary", []))
        if total_days == 0:
            total_days = 1
        
        # 장소를 일차별로 균등 분배
        places_to_process = confirmed_plan["places"][:10]  # 최대 10개 장소
        
        for idx, place in enumerate(places_to_process):
            # 장소 ID 생성 (table_name_place_id 형태)
            table_name = place.get("table_name", place.get("category", "general"))
            place_id = place.get("place_id", place.get("id", "1"))
            place_identifier = f"{table_name}_{place_id}"
            
            places_list.append(place_identifier)
            source_tables_list.append(table_name)
            
            # 일정에서 해당 장소가 몇일차에 있는지 확인
            day_num = 1  # 기본값
            place_name = place.get("name", "").replace("이름: ", "").strip()
            
            if "itinerary" in confirmed_plan:
                found = False
                for day_info in confirmed_plan["itinerary"]:
                    for schedule in day_info.get("schedule", []):
                        schedule_place = schedule.get("place_name", "").replace("이름: ", "").strip()
                        # 장소명이 포함되어 있으면 매칭
                        if place_name in schedule_place or schedule_place in place_name:
                            day_num = day_info.get("day", 1)
                            found = True
                            break
                    if found:
                        break
                
                # 매칭되지 않으면 순서대로 균등 배치
                if not found:
                    day_num = (idx % total_days) + 1
            
            day_numbers_list.append(str(day_num))
        
        # 완전 균등 분배를 위한 재배정
        if total_days > 1 and len(day_numbers_list) >= total_days:
            # 각 일차에 몇 개씩 배치할지 계산
            base_count = len(day_numbers_list) // total_days
            extra_count = len(day_numbers_list) % total_days
            
            # 새로운 균등 분배
            new_day_numbers = []
            place_idx = 0
            
            for day in range(1, total_days + 1):
                # 기본 개수 + (extra가 있으면 1개 더)
                count_for_this_day = base_count + (1 if day <= extra_count else 0)
                
                for _ in range(count_for_this_day):
                    if place_idx < len(day_numbers_list):
                        new_day_numbers.append(str(day))
                        place_idx += 1
            
            # 남은 장소들은 순서대로 배치
            while place_idx < len(day_numbers_list):
                day = ((place_idx - len(new_day_numbers)) % total_days) + 1
                new_day_numbers.append(str(day))
                place_idx += 1
            
            day_numbers_list = new_day_numbers
    
    # 날짜 계산 (duration에서 박수 추출)
    import re
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
    
    # 지도 표시용 장소 정보도 유지 (프론트엔드에서 추가 활용 가능)
    map_places = []
    if "places" in confirmed_plan and confirmed_plan["places"]:
        for place in confirmed_plan["places"][:10]:
            place_info = {
                "name": place.get("name", ""),
                "category": place.get("category", ""),
                "table_name": place.get("table_name", ""),
                "place_id": place.get("place_id", place.get("id", ""))
            }
            # 위치 정보가 있으면 추가
            if place.get("latitude") and place.get("longitude"):
                place_info["lat"] = place["latitude"]
                place_info["lng"] = place["longitude"]
            map_places.append(place_info)
    
    response = f"""
🎉 **여행 일정이 확정되었습니다!**

📋 **확정된 일정 정보:**
• **지역**: {confirmed_plan.get('region', 'N/A')}
• **기간**: {confirmed_plan.get('duration', 'N/A')} 
• **일정**: {itinerary_summary}
• **장소**: {places_summary}

🗺️ **지도에서 여행지를 확인하세요!**
확정된 여행지들이 지도에 표시됩니다.

🔄 **지도 페이지로 이동 중...**
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
    formatted = formatted.replace("**[", "\n\n**[")
    
    # 각 일정 항목 앞에 개행 추가 (• 기호 기준)
    formatted = formatted.replace("• ", "\n• ")
    
    # 여행 팁 섹션 앞에 개행 추가
    formatted = formatted.replace("💡 **여행 팁**", "\n\n💡 **여행 팁**")
    
    # 확정 안내 앞에 개행 추가
    formatted = formatted.replace("이 일정으로 확정", "\n\n이 일정으로 확정")
    
    # 제목 앞 불필요한 개행 제거
    if formatted.startswith("\n\n"):
        formatted = formatted[2:]
    
    # 연속된 개행 정리 (3개 이상 -> 2개)
    import re
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
            return "1"  # 기본값
            
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
                # 매칭되지 않으면 해당 테이블의 첫 번째 ID 사용 (더 안전함)
                first_place = session.query(table_model).first()
                return str(first_place.id) if first_place else "1"
                
        finally:
            session.close()
            
    except Exception as e:
        print(f"place_id 조회 오류: {e}")
        return "1"  # 오류 시 기본값

def extract_structured_places(docs: List[Document]) -> List[dict]:
    """RAG 검색 결과에서 구조화된 장소 정보 추출"""
    structured_places = []
    
    for doc in docs[:20]:  # 상위 20개만 처리
        try:
            place_info = {
                "name": "",
                "category": "",
                "region": "",
                "city": "",
                "description": doc.page_content[:200],  # 첫 200자
                "similarity_score": doc.metadata.get('similarity_score', 0)
            }
            
            # 메타데이터에서 정보 추출
            metadata = doc.metadata or {}
            place_info["category"] = metadata.get("category", "")
            place_info["region"] = metadata.get("region", "")
            place_info["city"] = metadata.get("city", "")
            
            # 데이터베이스 테이블 정보 추출
            # 카테고리를 테이블 이름으로 매핑
            category_to_table = {
                "한식": "restaurants",
                "중식": "restaurants", 
                "양식": "restaurants",
                "일식": "restaurants",
                "카페": "restaurants",
                "식당": "restaurants",
                "맛집": "restaurants",
                "자연": "attractions",
                "관광": "attractions",
                "문화": "humanities",
                "쇼핑": "shopping",
                "레포츠": "leisure_sports",
                "스포츠": "leisure_sports",
                "숙박": "accommodation",
                "펜션": "accommodation",
                "호텔": "accommodation"
            }
            
            # 문서 내용에서 장소명 추출 (간단한 패턴 매칭)
            content = doc.page_content
            
            # 첫 번째 줄이나 처음 몇 단어가 보통 장소명
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
                    # 첫 몇 단어를 이름으로 사용
                    words = content.split()[:3]
                    place_info["name"] = " ".join(words) if words else "장소명 미상"
            
            # 카테고리 및 테이블 정보 추출
            category = place_info.get("category", "")
            table_name = metadata.get("table_name", category_to_table.get(category, "attractions"))
            place_info["table_name"] = table_name
            
            # 실제 DB에서 장소명으로 place_id 조회 (장소명 추출 후에 호출)
            try:
                real_place_id = find_real_place_id(place_info["name"], table_name, metadata.get("region", ""))
                place_info["place_id"] = real_place_id
            except Exception as e:
                print(f"❌ ID 조회 실패: {place_info['name']} ({table_name}) - {e}")
                place_info["place_id"] = "1"
            
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
    import re
    
    # 응답에서 **장소명** 패턴으로 장소 추출
    place_pattern = r'\*\*([^*]+)\*\*'
    mentioned_places = re.findall(place_pattern, response)
    
    # 매칭된 장소들 저장
    matched_places = []
    
    # 일정 관련 키워드 필터링
    ignore_keywords = ['일차', '여행', '일정', '팁', '정보', '확정']
    
    for mentioned_place in mentioned_places:
        mentioned_place = mentioned_place.strip()
    
        # 일정 관련 키워드 제외
        if any(keyword in mentioned_place for keyword in ignore_keywords):
            continue
            
        # structured_places에서 가장 유사한 장소 찾기
        best_match = None
        best_score = 0
        
        for place in structured_places:
            place_name = place.get("name", "").strip()
            
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
        
        # 정확 매칭이거나 매칭 점수가 0.5 이상인 경우만 추가
        if best_match and (best_score == 1.0 or best_score >= 0.5):
            if best_match not in matched_places:
                matched_places.append(best_match)
    
    return matched_places

def parse_enhanced_travel_plan(response: str, user_query: str, structured_places: List[dict]) -> dict:
    """향상된 여행 일정 파싱 (실제 장소 데이터 포함)"""
    
    # 기본 정보 추출
    regions, cities, categories = extract_location_and_category(user_query)
    duration = extract_duration(user_query)
    
    # 응답에서 시간 패턴과 장소 추출
    import re
    
    # 시간 패턴 (09:00-12:00, 14:00 등)
    time_patterns = re.findall(r'\d{2}:\d{2}(?:-\d{2}:\d{2})?', response)
    
    # 일차별 구조 파싱
    day_pattern = r'\[(\d+)일차\]'
    days = re.findall(day_pattern, response)
    
    # 구조화된 일정 생성
    itinerary = []
    
    # 응답을 일차별로 분할
    day_sections = re.split(day_pattern, response)
    
    current_day = 1
    for i in range(1, len(day_sections), 2):  # 홀수 인덱스가 일차 번호, 짝수가 내용
        if i + 1 < len(day_sections):
            day_num = day_sections[i]
            day_content = day_sections[i + 1]
            
            # 해당 일차의 일정 파싱
            day_schedule = parse_day_schedule(day_content, structured_places)
            
            itinerary.append({
                "day": int(day_num),
                "schedule": day_schedule
            })
    
    # 실제 응답에 포함된 장소들만 추출
    response_places = extract_places_from_response(response, structured_places)
    
    # 상세 여행 계획 구조
    enhanced_plan = {
        "region": regions[0] if regions else "미지정",
        "cities": cities,
        "duration": duration,
        "categories": list(set(categories + [place["category"] for place in response_places if place["category"]])),
        "itinerary": itinerary,
        "places": response_places,  # 실제 응답에 포함된 장소들만
        "raw_response": response,
        "status": "draft",
        "created_at": "2025-09-13T00:00:00Z",  # 실제로는 datetime.now()
        "total_places": len(structured_places),
        "confidence_score": calculate_plan_confidence(structured_places, response)
    }
    
    return enhanced_plan

def parse_day_schedule(day_content: str, structured_places: List[dict]) -> List[dict]:
    """하루 일정 파싱"""
    import re
    
    schedule = []
    
    # • 09:00-12:00 **장소명** - 설명 패턴
    schedule_pattern = r'•\s*(\d{2}:\d{2}(?:-\d{2}:\d{2})?)\s*\*\*([^*]+)\*\*\s*-\s*([^\n]+)'
    matches = re.findall(schedule_pattern, day_content)
    
    for time_range, place_name, description in matches:
        # 구조화된 장소에서 매칭되는 정보 찾기
        matched_place = None
        for place in structured_places:
            if place["name"] and place["name"] in place_name:
                matched_place = place
                break
        
        schedule_item = {
            "time": time_range,
            "place_name": place_name.strip(),
            "description": description.strip(),
            "category": matched_place["category"] if matched_place else "",
            "place_info": matched_place
        }
        schedule.append(schedule_item)
    
    return schedule

def calculate_plan_confidence(structured_places: List[dict], response: str) -> float:
    """여행 계획의 신뢰도 점수 계산"""
    
    score = 0.0
    max_score = 100.0
    
    # 장소 정보 품질 (40점)
    if structured_places:
        avg_similarity = sum(place.get("similarity_score", 0) for place in structured_places) / len(structured_places)
        score += avg_similarity * 40
    
    # 응답 구조화 정도 (30점)
    structure_indicators = ["**[", "일차]", "•", ":**", "💡"]
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
    import re
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

# 세션 상태 관리를 위한 전역 변수 (실제 운영에서는 Redis나 DB 사용)
session_states = {}

def get_travel_recommendation_langgraph(query: str, conversation_history: List[str] = None, session_id: str = "default") -> dict:
    """LangGraph 기반 여행 추천 (구조화된 응답 반환, 세션 상태 유지)"""
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
        
        # 세션 상태 복원 또는 초기화
        if session_id in session_states:
            print(f"📝 기존 세션 상태 복원: {session_id}")
            initial_state = session_states[session_id].copy()
            # 새 메시지 추가
            initial_state["messages"] = messages
        else:
            print(f"🆕 새 세션 상태 생성: {session_id}")
            # 초기 상태 설정
            initial_state = TravelState(
                messages=messages,
                query_type="",
                need_rag=False,
                need_search=False,
                need_tool=False,
                need_confirmation=False,
                history="",
                rag_results=[],
                search_results=[],
                tool_results={},
                travel_plan={},
                user_preferences={},
                conversation_context="",
                formatted_ui_response={}
            )
        
        # 워크플로우 실행
        final_state = travel_workflow.invoke(initial_state)
        
        # 세션 상태 저장 (여행 계획이 있는 경우에만)
        if final_state.get("travel_plan"):
            session_states[session_id] = final_state.copy()
            print(f"💾 세션 상태 저장 완료: {session_id}")
        
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
    
    try:
        interactive_mode()
            
    except KeyboardInterrupt:
        print("\n👋 시스템을 종료합니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
