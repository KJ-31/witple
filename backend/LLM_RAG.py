import boto3
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_postgres import PGVector
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
# 미사용 import 제거됨 (hashlib, numpy, pickle)

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
            "temperature": 0.1,         # 약간 높여서 빠른 응답 (0.2 → 0.3)
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


# # 벡터스토어 연결 (필수)

print("🔗 벡터스토어 연결 중...")
vectorstore = PGVector(
    embeddings=embeddings,
    collection_name="place_recommendations",
    connection=os.getenv('DATABASE_URL'),
    pre_delete_collection=False,
)
print("✅ 벡터스토어 연결 성공")

# DB 카탈로그는 초기화 함수에서 로드될 예정

# # LLM 기반 엔티티 인식 시스템 (하드코딩된 상수 제거됨)

# 숙소 카테고리 상수화 (보안 개선)
ACCOMMODATION_CATEGORIES = ['숙소', '호텔', '펜션', '모텔', '게스트하우스', '리조트']

def is_accommodation(category: str) -> bool:
    """카테고리가 숙소 관련인지 판단"""
    if not category:
        return False
    return any(keyword in category for keyword in ACCOMMODATION_CATEGORIES)

def detect_query_entities(query: str) -> dict:
    """LLM을 사용하여 쿼리에서 구조화된 엔티티 및 여행 인텐트 추출"""
    try:
        entity_extraction_prompt = ChatPromptTemplate.from_template("""
당신은 한국 여행 쿼리를 분석하는 전문가입니다.
주어진 쿼리에서 지역명, 도시명, 카테고리, 키워드와 여행 인텐트를 추출해주세요.

쿼리: "{query}"

다음 JSON 형태로 정확히 응답해주세요:
{{
    "regions": ["지역명들"],
    "cities": ["도시명들"],
    "categories": ["카테고리들"],
    "keywords": ["기타 키워드들"],
    "intent": "여행 인텐트",
    "travel_type": "여행 유형",
    "duration": "여행 기간",
    "travel_dates": "여행 날짜"
}}

추출 규칙:
1. 지역명: 경기도, 서울특별시, 부산광역시 등의 광역 행정구역
2. 도시명: 강릉, 제주, 부산, 서울 등의 구체적 도시/지역
3. 카테고리: 맛집, 관광지, 자연, 쇼핑, 레포츠, 카페, 한식, 일식, 중식, 양식 등
4. 키워드: 2박3일, 가족여행, 데이트, 혼자, 친구 등의 부가 정보
5. intent: "travel_planning"(여행 일정), "place_search"(장소 검색), "weather"(날씨), "general"(일반)
6. travel_type: "family"(가족), "couple"(커플), "friends"(친구), "solo"(혼자), "business"(출장), "general"(일반)
7. duration: "당일", "1박2일", "2박3일", "3박4일", "장기", "미정" 등
8. travel_dates: 구체적인 날짜를 YYYY-MM-DD 형식으로 변환, 상대적 날짜, 또는 "미정"

**날짜 변환 규칙**:
- "10월 4일" → "2025-10-04" (현재 연도 기준)
- "4일부터" → "2025-09-04" (현재 월 기준)
- "내일" → 내일 날짜로 계산
- "이번 주말" → "이번 주말" (그대로 유지)
- "다음 달" → "다음 달" (그대로 유지)
- "2025-10-04" → "2025-10-04" (이미 형식화된 경우 그대로)

예시:
- "부산 2박3일 10월 4일부터" → {{"regions": ["부산광역시"], "cities": ["부산"], "categories": [], "keywords": ["2박3일"], "intent": "travel_planning", "travel_type": "general", "duration": "2박3일", "travel_dates": "2025-10-04"}}
- "제주도 이번 주말" → {{"regions": ["제주특별자치도"], "cities": ["제주"], "categories": [], "keywords": [], "intent": "travel_planning", "travel_type": "general", "duration": "미정", "travel_dates": "이번 주말"}}
- "서울 12월 25일부터 27일까지" → {{"regions": ["서울특별시"], "cities": ["서울"], "categories": [], "keywords": [], "intent": "travel_planning", "travel_type": "general", "duration": "미정", "travel_dates": "2025-12-25부터 2025-12-27까지"}}
""")

        entity_chain = entity_extraction_prompt | llm

        response = entity_chain.invoke({"query": query})

        # JSON 파싱 시도
        import json
        import re

        # 응답에서 JSON 부분만 추출
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if json_match:
            entities = json.loads(json_match.group())

            # 기본 구조 보장 (새로운 필드 추가)
            result = {
                "regions": entities.get("regions", []),
                "cities": entities.get("cities", []),
                "categories": entities.get("categories", []),
                "keywords": entities.get("keywords", []),
                "intent": entities.get("intent", "general"),
                "travel_type": entities.get("travel_type", "general"),
                "duration": entities.get("duration", "미정"),
                "travel_dates": entities.get("travel_dates", "미정")
            }

            print(f"🧠 LLM 엔티티 추출 성공: {result}")
            print(f"🧠 추출된 travel_dates: '{result.get('travel_dates', 'N/A')}'")
            return result
        else:
            print(f"⚠️ LLM 응답에서 JSON 파싱 실패: {response.content}")
            return {"regions": [], "cities": [], "categories": [], "keywords": [], "intent": "general", "travel_type": "general", "duration": "미정", "travel_dates": "미정"}

    except Exception as e:
        print(f"❌ LLM 엔티티 추출 오류: {e}")
        # 폴백: 기존 하드코딩 방식 사용
        return _fallback_entity_extraction(query)

def _fallback_entity_extraction(query: str) -> dict:
    """폴백: DB 카탈로그 기반 단순 문자열 매칭 (LLM 실패시)"""
    found_regions = []
    found_cities = []
    found_categories = []

    # DB 카탈로그가 로드되지 않은 경우 빈 결과 반환
    if not _db_catalogs.get("regions"):
        print("⚠️ DB 카탈로그가 로드되지 않음, 빈 결과 반환")
        return {"regions": [], "cities": [], "categories": [], "keywords": []}

    # DB 카탈로그 기반 단순 문자열 매칭
    for region in _db_catalogs.get("regions", []):
        if region in query or region.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '') in query:
            found_regions.append(region)

    for city in _db_catalogs.get("cities", []):
        if city in query:
            found_cities.append(city)

    for category in _db_catalogs.get("categories", []):
        if category in query:
            found_categories.append(category)

    return {
        "regions": found_regions,
        "cities": found_cities,
        "categories": found_categories,
        "keywords": [],
        "intent": "general",
        "travel_type": "general",
        "duration": "미정",
        "travel_dates": "미정"
    }

def classify_query_intent(query: str, has_travel_plan: bool = False) -> dict:
    """키워드 기반 쿼리 의도 분류 (LLM 호출 최소화)"""
    print(f"🔧 키워드 기반 의도 분류 사용 (LLM 호출 없음)")
    return _fallback_intent_classification(query, has_travel_plan)

def _fallback_intent_classification(query: str, has_travel_plan: bool = False) -> dict:
    """폴백: 단순 키워드 기반 의도 분류"""
    query_lower = query.lower()

    # 확정 관련 키워드
    if has_travel_plan and any(word in query_lower for word in ["확정", "결정", "좋아", "네", "예", "응", "ok"]):
        return {
            "primary_intent": "confirmation",
            "secondary_intent": "none",
            "confidence_level": "medium",
            "confirmation_type": "weak",
            "requires_rag": False,
            "requires_search": False
        }

    # 날씨 관련
    if any(word in query_lower for word in ["날씨", "기온", "비", "눈"]):
        return {
            "primary_intent": "weather",
            "secondary_intent": "none",
            "confidence_level": "high",
            "confirmation_type": "none",
            "requires_rag": True,
            "requires_search": False
        }

    # 기본 여행 계획
    return {
        "primary_intent": "travel_planning",
        "secondary_intent": "none",
        "confidence_level": "low",
        "confirmation_type": "none",
        "requires_rag": True,
        "requires_search": False
    }

def extract_location_and_category(query: str):
    """쿼리에서 지역명과 카테고리를 정확히 추출 (LLM 기반 + DB 정규화)"""
    try:
        # 1단계: LLM으로 엔티티 추출
        raw_entities = detect_query_entities(query)

        # 2단계: DB 카탈로그 기반 정규화
        normalized_entities = normalize_entities(raw_entities)

        # 기존 반환 형식 유지 (하위 호환성)
        return (
            normalized_entities["regions"],
            normalized_entities["cities"],
            normalized_entities["categories"]
        )

    except Exception as e:
        print(f"⚠️ 엔티티 추출 중 오류, 폴백 사용: {e}")
        # 최종 폴백: 기존 하드코딩 방식
        fallback_entities = _fallback_entity_extraction(query)
        return (
            fallback_entities["regions"],
            fallback_entities["cities"],
            fallback_entities["categories"]
        )

# DB 카탈로그 캐시 (앱 시작시 프리로드)
_db_catalogs = {
    "regions": [],
    "cities": [],
    "categories": []
}

def load_db_catalogs():
    """앱 시작시 DB에서 실제 지역/도시/카테고리 목록을 Redis에 캐시"""
    try:
        print("📖 DB 카탈로그 프리로드 중...")

        with shared_engine.connect() as conn:
            # 실제 DB에서 distinct 값들 조회
            regions_query = text("""
                SELECT DISTINCT cmetadata->>'region' as region
                FROM langchain_pg_embedding
                WHERE cmetadata->>'region' IS NOT NULL
                AND cmetadata->>'region' != ''
                ORDER BY region
            """)

            cities_query = text("""
                SELECT DISTINCT cmetadata->>'city' as city
                FROM langchain_pg_embedding
                WHERE cmetadata->>'city' IS NOT NULL
                AND cmetadata->>'city' != ''
                ORDER BY city
            """)

            categories_query = text("""
                SELECT DISTINCT cmetadata->>'category' as category
                FROM langchain_pg_embedding
                WHERE cmetadata->>'category' IS NOT NULL
                AND cmetadata->>'category' != ''
                ORDER BY category
            """)

            # 결과 저장
            regions_result = conn.execute(regions_query).fetchall()
            cities_result = conn.execute(cities_query).fetchall()
            categories_result = conn.execute(categories_query).fetchall()

            _db_catalogs["regions"] = [row.region for row in regions_result if row.region]
            _db_catalogs["cities"] = [row.city for row in cities_result if row.city]
            _db_catalogs["categories"] = [row.category for row in categories_result if row.category]

            print(f"✅ DB 카탈로그 로드 완료:")
            print(f"   - 지역: {len(_db_catalogs['regions'])}개")
            print(f"   - 도시: {len(_db_catalogs['cities'])}개")
            print(f"   - 카테고리: {len(_db_catalogs['categories'])}개")

            # Redis 캐시 저장 기능 제거됨

        return True

    except Exception as e:
        print(f"⚠️ DB 카탈로그 로드 실패: {e}")
        # 폴백: 최소한의 빈 배열로 초기화
        _db_catalogs["regions"] = []
        _db_catalogs["cities"] = []
        _db_catalogs["categories"] = []
        return False

def normalize_entities(entities: dict, use_fuzzy: bool = True) -> dict:
    """추출된 엔티티를 DB 카탈로그 기반으로 정규화"""
    try:
        normalized = {
            "regions": [],
            "cities": [],
            "categories": [],
            "keywords": entities.get("keywords", [])
        }

        # 간단한 문자열 매칭으로 정규화
        for entity_region in entities.get("regions", []):
            for db_region in _db_catalogs["regions"]:
                # 부분 매칭 또는 정확 매칭
                if (entity_region in db_region or db_region in entity_region or
                    entity_region.replace('특별시','').replace('광역시','').replace('도','') in db_region):
                    if db_region not in normalized["regions"]:
                        normalized["regions"].append(db_region)

        for entity_city in entities.get("cities", []):
            for db_city in _db_catalogs["cities"]:
                if entity_city in db_city or db_city in entity_city:
                    if db_city not in normalized["cities"]:
                        normalized["cities"].append(db_city)

        for entity_category in entities.get("categories", []):
            for db_category in _db_catalogs["categories"]:
                if entity_category in db_category or db_category in entity_category:
                    if db_category not in normalized["categories"]:
                        normalized["categories"].append(db_category)

        print(f"🔄 엔티티 정규화: {entities} → {normalized}")
        return normalized

    except Exception as e:
        print(f"⚠️ 엔티티 정규화 오류: {e}")
        return entities

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
                print("⚠️ SQL 필터링 결과 없음, 전체 벡터 검색 실행")
                docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=min(500, self.k))
                filtered_docs = []
                for doc, score in docs_with_scores:
                    if score >= self.score_threshold:
                        doc.metadata['similarity_score'] = round(score, 3)
                        doc.metadata['search_method'] = 'pgvector_full'
                        filtered_docs.append(doc)
                print(f"✅ 전체 벡터 검색 완료: {len(filtered_docs)}개 문서")
                return filtered_docs
            
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
            
            # 조건이 없으면 전체 검색 실행
            if not regions and not cities and not categories:
                print("🔍 지역/카테고리 정보 없음, 전체 텍스트 검색 실행")
                sql_query = text("""
                    SELECT document, cmetadata
                    FROM langchain_pg_embedding
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'place_recommendations')
                    ORDER BY RANDOM()
                    LIMIT :limit
                """)

                with engine.connect() as conn:
                    results = conn.execute(sql_query, {"limit": min(self.max_sql_results, 1000)}).fetchall()

                docs = []
                for row in results:
                    metadata = row.cmetadata or {}
                    metadata['search_method'] = 'sql_random'
                    docs.append(Document(page_content=row.document, metadata=metadata))

                print(f"📊 전체 텍스트 검색: {len(docs)}개 문서 반환")
                return docs
            
            # SQL 조건 구성
            conditions = []
            
            # SQL 조건과 파라미터 구성
            params = {}
            param_counter = 0

            if regions:
                region_conditions = []
                for region in regions:
                    # 서울특별시 -> 서울로 변환하여 검색
                    region_simple = region.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '')
                    param_name = f"region_{param_counter}"
                    region_conditions.append(f"cmetadata->>'region' ILIKE :{param_name}")
                    params[param_name] = f'%{region_simple}%'
                    param_counter += 1
                conditions.append(f"({' OR '.join(region_conditions)})")
            
            if cities:
                city_conditions = []
                for city in cities:
                    # city 필드와 region 필드 모두에서 검색 (서울의 경우)
                    city_simple = city.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '')

                    # city 필드 검색
                    city_param = f"city_{param_counter}"
                    city_conditions.append(f"cmetadata->>'city' ILIKE :{city_param}")
                    params[city_param] = f'%{city_simple}%'
                    param_counter += 1

                    # region 필드 검색
                    region_param = f"city_region_{param_counter}"
                    city_conditions.append(f"cmetadata->>'region' ILIKE :{region_param}")
                    params[region_param] = f'%{city_simple}%'
                    param_counter += 1

                conditions.append(f"({' OR '.join(city_conditions)})")
            
            if categories:
                category_conditions = []
                for category in categories:
                    param_name = f"category_{param_counter}"
                    category_conditions.append(f"cmetadata->>'category' ILIKE :{param_name}")
                    params[param_name] = f'%{category}%'
                    param_counter += 1
                conditions.append(f"({' OR '.join(category_conditions)})")
            
            where_clause = " OR ".join(conditions)
            
            # 숙소 필터링을 위한 파라미터 추가
            for i, accommodation in enumerate(ACCOMMODATION_CATEGORIES):
                param_name = f"exclude_accommodation_{i}"
                params[param_name] = f'%{accommodation}%'

            # 숙소 제외 조건 구성
            accommodation_excludes = " AND ".join([
                f"cmetadata->>'category' NOT ILIKE :exclude_accommodation_{i}"
                for i in range(len(ACCOMMODATION_CATEGORIES))
            ])

            params['max_results'] = self.max_sql_results

            sql_query = f"""
                SELECT document, cmetadata, embedding
                FROM langchain_pg_embedding
                WHERE ({where_clause})
                AND {accommodation_excludes}
                LIMIT :max_results
            """
            
            print(f"🗄️ SQL 필터링 실행 (파라미터 바인딩)...")

            with engine.connect() as conn:
                result = conn.execute(text(sql_query), params)
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
    
    
    def _vector_search_on_candidates(self, query: str, candidate_docs: List[Document]) -> List[Document]:
        """PGVector를 사용한 벡터 유사도 계산"""
        try:
            # PGVector 벡터 검색
            print("🔄 PGVector 벡터 검색")
            all_docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=self.k)

            # 후보 문서의 내용으로 매칭
            candidate_contents = {doc.page_content for doc in candidate_docs}

            filtered_docs = []
            for doc, score in all_docs_with_scores:
                # 숙소 카테고리 필터링
                category = doc.metadata.get('category', '')
                accommodation_keywords = ['숙소', '호텔', '펜션', '모텔', '게스트하우스', '리조트', '한옥', '관광호텔', '유스호스텔', '텔', '레지던스']
                is_accommodation = any(keyword in category for keyword in accommodation_keywords)

                if is_accommodation:
                    print(f"🚫 PGVector 숙소 필터링: {category} - {doc.page_content[:30]}...")
                    continue

                if doc.page_content in candidate_contents and score >= self.score_threshold:
                    # 유사도 점수를 metadata에 추가
                    doc.metadata['similarity_score'] = round(score, 3)
                    doc.metadata['search_method'] = 'pgvector_hybrid'
                    filtered_docs.append(doc)

                    # 충분한 결과를 얻으면 중단 (성능 최적화)
                    if len(filtered_docs) >= 50:
                        break

            print(f"✅ PGVector 검색 완료: {len(filtered_docs)}개 문서")
            return filtered_docs

        except Exception as e:
            print(f"❌ 벡터 유사도 계산 오류: {e}")
            return []
    

# 하이브리드 최적화 Retriever 생성 (sentence-transformers 모델에 최적화된 임계값)
retriever = HybridOptimizedRetriever(vectorstore, k=50000, score_threshold=0.3, max_sql_results=8000)

# =============================================================================
# 주요 기능 함수들 (LangGraph 워크플로우 사용)
# =============================================================================

def format_docs(docs):
    """검색된 문서들을 텍스트로 포맷팅 (유사도 점수 포함, 상위 30개로 제한)"""
    if not docs:
        return "NO_RELEVANT_DATA"  # 관련 데이터 없음을 나타내는 특별한 마커

    # 상위 30개 문서만 선택
    docs = docs[:30]
    print(f"📄 LLM에 전달할 문서 수: {len(docs)}개 (상위 30개로 제한)")

    formatted_docs = []
    for i, doc in enumerate(docs, 1):
        # 유사도 점수 추출
        similarity_score = doc.metadata.get('similarity_score', 'N/A')
        content = f"[여행지 {i}] (유사도: {similarity_score})\n{doc.page_content}"

        if doc.metadata:
            meta_info = []
            for key, value in doc.metadata.items():
                if value and key not in ['original_id', 'similarity_score', '_embedding', 'search_method']:  # 내부 키 제외
                    meta_info.append(f"{key}: {value}")
            if meta_info:
                content += f"\n({', '.join(meta_info)})"
        formatted_docs.append(content)

    return "\n\n".join(formatted_docs)

def search_places(query):
    """여행지 검색 함수 (하이브리드 최적화 + Redis 캐싱)"""
    try:
        print(f"🔍 하이브리드 검색: '{query}'")

        # 캐시 기능 제거됨

        print("🔍 새로운 검색 실행...")

        # HybridOptimizedRetriever 직접 사용
        docs = retriever._get_relevant_documents(query)

        # 캐시 기능 제거됨

        return docs

    except Exception as e:
        print(f"❌ 검색 오류: {e}")
        return []


# Weather 모듈에서 필요한 함수만 import (지역 추출용)
from weather import (
    extract_region_from_query
)

def parse_travel_dates(travel_dates: str, duration: str = "") -> dict:
    """여행 날짜 문자열을 파싱하여 startDate, endDate, days 반환"""
    import re
    from datetime import datetime, timedelta

    print(f"🔧 parse_travel_dates 호출: travel_dates='{travel_dates}', duration='{duration}'")

    result = {
        "startDate": "",
        "endDate": "",
        "days": ""
    }

    if not travel_dates or travel_dates == "미정":
        print(f"📅 날짜 정보 없음, duration에서 일수 추출 시도")
        # duration에서 일수 추출 시도
        if duration:
            duration_match = re.search(r'(\d+)박', duration)
            if duration_match:
                nights = int(duration_match.group(1))
                result["days"] = str(nights + 1)  # 박 + 1 = 일
                print(f"📅 duration에서 추출: {nights}박 → {result['days']}일")
            else:
                print(f"📅 duration에서 박수 추출 실패: '{duration}'")
        else:
            print(f"📅 duration도 없음")
        return result

    try:
        # 1. YYYY-MM-DD 형태의 날짜들 먼저 추출
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        dates = re.findall(date_pattern, travel_dates)
        print(f"📅 YYYY-MM-DD 형태 추출: {dates}")

        # 2. 자연어 날짜 추출 및 변환
        if not dates:
            print(f"📅 자연어 날짜 파싱 시도")
            current_year = datetime.now().year
            current_month = datetime.now().month

            # "N월 N일" 패턴 추출
            month_day_pattern = r'(\d{1,2})월\s*(\d{1,2})일'
            month_day_matches = re.findall(month_day_pattern, travel_dates)
            if month_day_matches:
                for month, day in month_day_matches:
                    formatted_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
                    dates.append(formatted_date)
                    print(f"📅 {month}월 {day}일 → {formatted_date}")

            # "N일부터" 패턴 (현재 월 기준)
            if not dates:
                day_pattern = r'(\d{1,2})일부터'
                day_matches = re.findall(day_pattern, travel_dates)
                if day_matches:
                    day = day_matches[0]
                    formatted_date = f"{current_year}-{current_month:02d}-{int(day):02d}"
                    dates.append(formatted_date)
                    print(f"📅 {day}일부터 → {formatted_date}")

            # "내일" 처리
            if "내일" in travel_dates and not dates:
                tomorrow = datetime.now() + timedelta(days=1)
                formatted_date = tomorrow.strftime('%Y-%m-%d')
                dates.append(formatted_date)
                print(f"📅 내일 → {formatted_date}")

        print(f"📅 최종 추출된 날짜들: {dates}")

        if len(dates) >= 2:
            # 시작일과 종료일이 모두 있는 경우
            print(f"📅 시작일과 종료일 모두 있음: {dates[0]} ~ {dates[1]}")
            start_date = datetime.strptime(dates[0], '%Y-%m-%d')
            end_date = datetime.strptime(dates[1], '%Y-%m-%d')

            result["startDate"] = dates[0]
            result["endDate"] = dates[1]
            result["days"] = str((end_date - start_date).days + 1)
            print(f"📅 계산된 일수: {result['days']}일")

        elif len(dates) == 1:
            # 시작일만 있는 경우 - duration에서 종료일 계산
            print(f"📅 시작일만 있음: {dates[0]}, duration으로 종료일 계산")
            start_date = datetime.strptime(dates[0], '%Y-%m-%d')
            result["startDate"] = dates[0]

            # duration에서 일수 추출
            if duration:
                duration_match = re.search(r'(\d+)박', duration)
                if duration_match:
                    nights = int(duration_match.group(1))
                    days = nights + 1
                    end_date = start_date + timedelta(days=days-1)
                    result["endDate"] = end_date.strftime('%Y-%m-%d')
                    result["days"] = str(days)
                    print(f"📅 계산된 종료일: {result['endDate']}, 일수: {result['days']}")
                else:
                    print(f"📅 duration에서 박수 추출 실패: '{duration}'")

        # 상대적 날짜 처리 ("이번 주말", "다음 달" 등)
        elif "이번 주말" in travel_dates:
            print(f"📅 이번 주말 처리")
            today = datetime.now()
            # 이번 주 토요일 찾기
            days_until_saturday = (5 - today.weekday()) % 7
            if days_until_saturday == 0 and today.weekday() == 5:  # 오늘이 토요일
                saturday = today
            else:
                saturday = today + timedelta(days=days_until_saturday)
            sunday = saturday + timedelta(days=1)

            result["startDate"] = saturday.strftime('%Y-%m-%d')
            result["endDate"] = sunday.strftime('%Y-%m-%d')
            result["days"] = "2"
            print(f"📅 이번 주말: {result['startDate']} ~ {result['endDate']}")

        elif "다음 주말" in travel_dates:
            print(f"📅 다음 주말 처리")
            today = datetime.now()
            # 다음 주 토요일 찾기
            days_until_next_saturday = ((5 - today.weekday()) % 7) + 7
            saturday = today + timedelta(days=days_until_next_saturday)
            sunday = saturday + timedelta(days=1)

            result["startDate"] = saturday.strftime('%Y-%m-%d')
            result["endDate"] = sunday.strftime('%Y-%m-%d')
            result["days"] = "2"
            print(f"📅 다음 주말: {result['startDate']} ~ {result['endDate']}")

        else:
            print(f"📅 날짜 패턴 매칭 안됨, duration만으로 일수 추출 시도")
            if duration:
                duration_match = re.search(r'(\d+)박', duration)
                if duration_match:
                    nights = int(duration_match.group(1))
                    result["days"] = str(nights + 1)
                    print(f"📅 duration에서만 추출: {nights}박 → {result['days']}일")

        # 과거 날짜 검증 - 불가능한 날짜 안내
        today = datetime.now().date()
        if result.get("startDate"):
            try:
                start_date = datetime.strptime(result["startDate"], '%Y-%m-%d').date()
                if start_date < today:
                    print(f"❌ 과거 날짜 감지: {result['startDate']} - 불가능한 날짜")
                    # 과거 날짜인 경우 결과를 초기화하고 에러 메시지 추가
                    result = {
                        "startDate": "",
                        "endDate": "",
                        "days": "",
                        "error": f"선택하신 날짜 {result['startDate']}는 과거 날짜입니다. 오늘 이후의 날짜를 선택해주세요."
                    }
                    print(f"📅 과거 날짜로 인한 파싱 실패")
                    return result
            except:
                pass

        # 날짜 파싱 결과 테스트 출력
        if any(result.values()):
            print(f"✅ 날짜 파싱 성공 - startDate: {result.get('startDate', 'N/A')}, endDate: {result.get('endDate', 'N/A')}, days: {result.get('days', 'N/A')}")
        else:
            print(f"❌ 날짜 파싱 실패 - 모든 필드 비어있음")

        print(f"📅 최종 날짜 파싱 결과: {result}")
        return result

    except Exception as e:
        print(f"⚠️ 날짜 파싱 오류: {e}")
        import traceback
        traceback.print_exc()
        # duration에서라도 일수 추출
        if duration:
            duration_match = re.search(r'(\d+)박', duration)
            if duration_match:
                nights = int(duration_match.group(1))
                result["days"] = str(nights + 1)
                print(f"📅 오류 발생, duration에서만 추출: {nights}박 → {result['days']}일")
        print(f"📅 오류 후 최종 결과: {result}")
        return result

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
    """LLM 기반 쿼리 분류 - 하드코딩 제거"""
    if not state.get("messages"):
        return state

    user_input = state["messages"][-1] if state["messages"] else ""
    has_travel_plan = bool(state.get("travel_plan"))

    print(f"🔍 LLM 기반 쿼리 분류: '{user_input}'")

    try:
        # LLM 기반 의도 분류
        intent_result = classify_query_intent(user_input, has_travel_plan)

        # 새로운 여행 요청 감지 (기존 로직 유지)
        if has_travel_plan and intent_result["primary_intent"] == "travel_planning":
            # 새로운 여행 일정 요청으로 판단되면 상태 초기화
            print("🔄 새로운 여행 일정 요청 감지 - 기존 상태 초기화")
            state["travel_plan"] = {}
            state["user_preferences"] = {}
            state["conversation_context"] = ""
            state["formatted_ui_response"] = {}
            has_travel_plan = False  # 상태 업데이트

        # LLM 결과를 기존 변수명으로 매핑
        need_rag = intent_result["requires_rag"]
        need_search = intent_result["requires_search"]
        need_confirmation = (intent_result["primary_intent"] == "confirmation" and
                            intent_result["confirmation_type"] != "none")

        # 날씨 요청은 LLM에서 이미 분류됨

        print(f"🧠 LLM 분류 결과:")
        print(f"   - 주요 의도: {intent_result['primary_intent']}")
        print(f"   - 확정 유형: {intent_result['confirmation_type']}")
        print(f"   - RAG 필요: {need_rag}")
        print(f"   - 검색 필요: {need_search}")
        print(f"   - 확정 필요: {need_confirmation}")

    except Exception as e:
        print(f"⚠️ LLM 분류 실패, 폴백 사용: {e}")
        # 폴백: 기본값
        need_rag = True
        need_search = False
        need_confirmation = False
        # 폴백에서는 날씨 요청 기본 함수 활용
    
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

    # 날씨 관련 처리는 제거 - 이제 여행 일정에서 날짜만 추출하여 활용
    # 여행 날짜 정보 추출 (map 파라미터 전달용)
    print(f"🔍 사용자 쿼리: '{user_query}'")
    query_entities = detect_query_entities(user_query)
    print(f"🔍 전체 엔티티: {query_entities}")

    travel_dates = query_entities.get("travel_dates", "미정")
    duration = query_entities.get("duration", "미정")
    print(f"📅 추출된 여행 날짜: '{travel_dates}', 기간: '{duration}'")

    # 날짜 파싱 (startDate, endDate, days 형태로 변환)
    parsed_dates = parse_travel_dates(travel_dates, duration)
    print(f"🗓️ 파싱된 날짜 정보: {parsed_dates}")

    # 파싱 결과 검증
    if parsed_dates.get("startDate") or parsed_dates.get("endDate") or parsed_dates.get("days"):
        print(f"✅ 날짜 파싱 성공!")
    else:
        print(f"⚠️ 날짜 파싱 실패 - 빈 결과")

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

        # 지역 매칭 (정확한 지역명 우선 순위로)
        print(f"🔍 지역 매칭 대상 쿼리: '{user_query.lower()}'")

        for region, keywords in region_keywords.items():
            for keyword in keywords:
                if keyword in user_query.lower():
                    # 중복 방지
                    if region not in query_regions:
                        query_regions.append(region)
                        target_keywords.extend(keywords)
                        print(f"🎯 지역 매칭: '{keyword}' → {region}")
                    break

        # 가장 구체적인 지역명만 사용 (중복 제거)
        if len(query_regions) > 1:
            print(f"⚠️ 여러 지역 매칭됨: {query_regions}, 첫 번째만 사용")
            query_regions = query_regions[:1]
        
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
                    
                    # 2. 특정 지역 요청 시 정확한 도시 매칭
                    elif '강릉' in region_lower and ('강릉' in doc_city or '강릉시' in doc_city):
                        is_relevant = True  # 강릉 요청 시 강릉시만 포함
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
                docs = region_docs[:35]  # 지역 필터링된 문서 선별
                print(f"📍 지역 필터링 결과: {len(docs)}개 문서 선별")
            else:
                print(f"⚠️ 지역 필터링 결과 없음, 전체 결과 사용")
                docs = docs[:35]
        
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
- 정보가 없는 장소는 절대 추가하지 마세요  
- 확실하지 않은 정보는 추측하지 마세요

시간 배치 규칙:
- 관광지 방문: 2-4시간 (장소 특성에 따라 조절)
- 박물관/미술관: 1.5-3시간
- 자연 명소: 2-5시간  
- 쇼핑/시장: 1-2시간
- 체험 활동: 1-3시간
- 식사 시간: 점심 12:00-13:00, 저녁 18:00-19:00 (고정)
- 이동 시간: 30분-1시간 (거리에 따라)

시간 조절 기준:
- 주어진 여행지 정보에서 각 장소의 특성을 파악하세요
- 규모가 큰 관광지는 더 많은 시간을 배정하세요
- 연속된 장소들의 지리적 위치를 고려하여 이동시간을 반영하세요
- 하루 총 활동시간이 8-10시간을 넘지 않도록 조절하세요

출력 형식을 다음과 같이 맞춰주세요:

🏝️ <strong>지역명 여행 일정</strong>

<strong>[1일차]</strong>
• 09:00-XX:XX <strong>장소명</strong> - 간단한 설명 (1줄)
• 12:00-13:00 <strong>식당명</strong> - 음식 종류 점심
• XX:XX-XX:XX <strong>장소명</strong> - 간단한 설명 (1줄)
• 18:00-19:00 <strong>식당명</strong> - 음식 종류 저녁

<strong>[2일차]</strong> (기간에 따라 추가)
...

시간 표시 규칙:
- 시작시간은 명시하되, 종료시간은 활동 특성에 따라 유동적으로 설정
- 각 활동 옆에 예상 소요시간을 괄호로 표시
- 다음 활동 시작 전 충분한 여유시간 확보

💡 <strong>여행 팁</strong>: 지역 특색이나 주의사항

이 일정으로 확정하시겠어요?

답변 과정:
1. 먼저 주어진 여행지 정보에서 사용 가능한 장소들을 확인하세요
2. 각 일차별로 시간대에 맞는 장소를 배치하세요  
3. 정보가 없는 부분은 명시적으로 표시하세요

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
        print(f"🔧 parse_enhanced_travel_plan 호출 전:")
        print(f"   - travel_dates: '{travel_dates}'")
        print(f"   - parsed_dates: {parsed_dates}")
        travel_plan = parse_enhanced_travel_plan(formatted_response, user_query, structured_places, travel_dates)
        print(f"🔧 parse_enhanced_travel_plan 호출 후:")
        print(f"   - travel_plan에 포함된 parsed_dates: {travel_plan.get('parsed_dates')}")
        
        # UI용 구조화된 응답 생성
        formatted_ui_response = create_formatted_ui_response(travel_plan, formatted_response)
        
        # 여행 일정 생성 완료 - 사용자 확인 대기 상태
        # 자동 확정하지 않고 사용자의 확정 의사를 기다림

        # 날씨 정보는 map 파라미터로 전달될 예정이므로 제거

        print(f"✅ RAG 처리 완료. 결과 길이: {len(formatted_response)}")
        print(f"   추출된 장소 수: {len(structured_places)}")

        # 최종 state 반환 전 디버깅
        final_state = {
            **state,
            "rag_results": docs,
            "travel_plan": travel_plan,
            "travel_dates": travel_dates,  # 원본 날짜 정보
            "parsed_dates": parsed_dates,  # map 파라미터 전달용 파싱된 날짜 정보
            "conversation_context": formatted_response,
            "formatted_ui_response": formatted_ui_response
        }

        print(f"🔧 === rag_processing_node 최종 반환 ===")
        print(f"🔧 final_state의 travel_dates: {final_state.get('travel_dates')}")
        print(f"🔧 final_state의 parsed_dates: {final_state.get('parsed_dates')}")
        print(f"🔧 final_state의 travel_plan 내 parsed_dates: {final_state.get('travel_plan', {}).get('parsed_dates')}")

        return final_state
        
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

    # 날짜 계산 (parseddates 우선 사용)
    from datetime import datetime, timedelta
    
    # state에서 parseddates 정보 가져오기
    parsed_dates = state.get("parsed_dates", {})
    print(f"🔍 confirmation_processing_node에서 받은 parsed_dates: {parsed_dates}")
    print(f"🔍 state의 모든 키: {list(state.keys())}")

    # travel_plan에서도 확인
    travel_plan_parsed_dates = state.get("travel_plan", {}).get("parsed_dates", {})
    print(f"🔍 travel_plan 내 parsed_dates: {travel_plan_parsed_dates}")

    # 둘 중 하나라도 있으면 사용
    if not parsed_dates and travel_plan_parsed_dates:
        parsed_dates = travel_plan_parsed_dates
        print(f"🔄 travel_plan에서 parsed_dates 가져옴: {parsed_dates}")
    
    if parsed_dates and parsed_dates.get("startDate") and parsed_dates.get("endDate"):
        # 사용자가 입력한 날짜 사용
        start_date = parsed_dates["startDate"]
        end_date = parsed_dates["endDate"]
        days = parsed_dates.get("days", 2)
        print(f"✅ 사용자 지정 날짜 사용: {start_date} ~ {end_date}")
    else:
        # fallback: duration에서 계산
        duration_str = confirmed_plan.get('duration', '2박 3일')
        days_match = re.search(r'(\d+)일', duration_str)
        days = int(days_match.group(1)) if days_match else 2
        
        # 기존 방식 (오늘 기준)
        start_date = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=days-1)).strftime('%Y-%m-%d')
        print(f"⚠️ 기본 날짜 사용 (오늘 기준): {start_date} ~ {end_date}")

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
    """장소명으로 실제 DB에서 place_id 조회 (공통 엔진 사용)"""
    try:
        from sqlalchemy.orm import sessionmaker
        from models_attractions import Nature, Restaurant, Shopping, Humanities, LeisureSports

        # 테이블 매핑 (숙소 제외)
        table_models = {
            "nature": Nature,
            "restaurants": Restaurant,
            "shopping": Shopping,
            "humanities": Humanities,
            "leisure_sports": LeisureSports
        }

        if table_name not in table_models:
            print(f"❌ 지원하지 않는 table_name: {table_name}")
            return None  # 기본값 "1" 대신 None 반환

        # 공통 엔진 사용 (중복 생성 방지)
        Session = sessionmaker(bind=shared_engine)
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

    for doc in docs[:25]:  # 상위 25개 처리
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
                    # 숙소 관련 카테고리 제외
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
                # 가상 장소 생성하지 않음 - 실제 존재하는 장소만 사용
                print(f"⚠️ 장소를 찾을 수 없습니다: {mentioned_place}")
    
    return matched_places

def parse_enhanced_travel_plan(response: str, user_query: str, structured_places: List[dict], travel_dates: str = "미정") -> dict:
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

    # 파싱된 날짜 정보 생성
    print(f"🔧 enhanced_plan 생성 중 - travel_dates: '{travel_dates}', duration: '{duration}'")
    plan_parsed_dates = parse_travel_dates(travel_dates, duration)
    print(f"🔧 enhanced_plan 내부에서 생성된 parsed_dates: {plan_parsed_dates}")

    # 상세 여행 계획 구조
    enhanced_plan = {
        "region": regions[0] if regions else "미지정",
        "cities": cities,
        "duration": duration,
        "travel_dates": travel_dates,  # 추출된 여행 날짜 추가
        "parsed_dates": plan_parsed_dates,  # 파싱된 날짜 정보 추가
        "categories": list(set(categories + [place["category"] for place in response_places if place.get("category")])),
        "itinerary": itinerary,
        "places": response_places,  # 실제 응답에 포함된 장소들만
        "raw_response": response,
        "status": "draft",
        "created_at": "2025-09-13T00:00:00Z",  # 실제로는 datetime.now()
        "total_places": len(structured_places),
        "confidence_score": calculate_plan_confidence(structured_places, response)
    }

    print(f"🔧 최종 enhanced_plan의 parsed_dates: {enhanced_plan.get('parsed_dates')}")

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
                "timestamp": "auto"
            })
        else:
            print("💾 기존 상태 유지")
            current_travel_state["last_query"] = query
            current_travel_state["timestamp"] = "auto"

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
                "timestamp": "auto"
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
            "travel_dates": final_state.get("travel_dates"),  # 최상위 레벨에 추가
            "parsed_dates": final_state.get("parsed_dates"),  # 최상위 레벨에 추가
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

# 시스템 초기화: DB 카탈로그 로드
try:
    print("🚀 시스템 초기화: DB 카탈로그 로드 중...")
    load_db_catalogs()
except Exception as e:
    print(f"⚠️ DB 카탈로그 초기화 실패: {e}")
