"""
RAG 처리 파이프라인 최적화 시스템
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import asyncio

from core.travel_context import get_travel_context
from utils.entity_extractor import detect_query_entities
from utils.travel_planner import parse_travel_dates, parse_enhanced_travel_plan
from utils.travel_planner import create_formatted_ui_response, format_travel_response_with_linebreaks
from utils.response_parser import extract_structured_places
from utils.travel_plan_storage import save_travel_plan
from utils.db_context import SafeDBOperation
from langchain_core.prompts import ChatPromptTemplate


@dataclass
class ProcessingContext:
    """RAG 처리 컨텍스트"""
    # 입력 정보
    query: str
    user_id: str
    session_id: str

    # 단계별 결과
    extracted_entities: Optional[Dict[str, Any]] = None
    search_results: Optional[List[Any]] = None
    filtered_documents: Optional[List[Any]] = None
    structured_places: Optional[List[Dict]] = None
    travel_plan: Optional[Dict] = None
    response_text: Optional[str] = None
    formatted_response: Optional[str] = None
    formatted_ui_response: Optional[Dict] = None

    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.metadata['start_time'] = time.time()
        self.metadata['stage_times'] = {}


class ProcessingStage(ABC):
    """처리 스테이지 추상 클래스"""

    @abstractmethod
    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """스테이지 처리"""
        pass

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """스테이지 이름"""
        pass

    def _record_stage_time(self, context: ProcessingContext):
        """스테이지 처리 시간 기록"""
        current_time = time.time()
        stage_start = context.metadata.get('stage_start_time', current_time)
        context.metadata['stage_times'][self.stage_name] = current_time - stage_start


class EntityExtractionStage(ProcessingStage):
    """엔티티 추출 스테이지"""

    @property
    def stage_name(self) -> str:
        return "entity_extraction"

    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """엔티티 추출 처리"""
        context.metadata['stage_start_time'] = time.time()
        print(f"🧠 {self.stage_name} 시작: '{context.query}'")

        try:
            travel_context = get_travel_context()
            entities = detect_query_entities(
                context.query,
                travel_context.llm,
                travel_context.db_catalogs
            )

            context.extracted_entities = entities

            travel_dates = entities.get("travel_dates", "미정")
            duration = entities.get("duration", "미정")
            parsed_dates = parse_travel_dates(travel_dates, duration)

            # 메타데이터에 추가 정보 저장
            context.metadata['travel_dates'] = travel_dates
            context.metadata['duration'] = duration
            context.metadata['parsed_dates'] = parsed_dates

            print(f"📅 추출된 여행 날짜: '{travel_dates}', 기간: '{duration}'")
            print(f"🗓️ 파싱된 날짜 정보: {parsed_dates}")

        except Exception as e:
            print(f"❌ {self.stage_name} 오류: {e}")
            context.metadata[f'{self.stage_name}_error'] = str(e)
            # 기본값으로 진행
            context.extracted_entities = {}

        finally:
            self._record_stage_time(context)

        return context


class VectorSearchStage(ProcessingStage):
    """벡터 검색 스테이지"""

    @property
    def stage_name(self) -> str:
        return "vector_search"

    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """벡터 검색 처리"""
        context.metadata['stage_start_time'] = time.time()
        print(f"🔍 {self.stage_name} 시작")

        try:
            travel_context = get_travel_context()

            # 하이브리드 검색으로 문서 가져오기
            print(f"🔍 검색 쿼리: '{context.query}'")
            docs = travel_context.retriever._get_relevant_documents(context.query)
            print(f"📄 초기 검색 결과: {len(docs)}개 문서")

            context.search_results = docs
            context.metadata['initial_docs_count'] = len(docs)

        except Exception as e:
            print(f"❌ {self.stage_name} 오류: {e}")
            context.metadata[f'{self.stage_name}_error'] = str(e)
            context.search_results = []

        finally:
            self._record_stage_time(context)

        return context


class RegionFilteringStage(ProcessingStage):
    """지역 필터링 스테이지"""

    @property
    def stage_name(self) -> str:
        return "region_filtering"

    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """지역 필터링 처리"""
        context.metadata['stage_start_time'] = time.time()
        print(f"🎯 {self.stage_name} 시작")

        try:
            docs = context.search_results or []
            entities = context.extracted_entities or {}

            # 지역 필터링 적용
            target_regions = entities.get('regions', []) + entities.get('cities', [])

            if target_regions:
                print(f"🎯 지역 필터링 대상: {target_regions}")
                filtered_docs = self._filter_documents_by_region(docs, target_regions)

                if filtered_docs:
                    context.filtered_documents = filtered_docs
                    print(f"✅ 지역 필터링 완료: {len(filtered_docs)}개 문서 선별")
                else:
                    print(f"⚠️ 지역 필터링 결과 없음, 전체 결과 사용")
                    context.filtered_documents = docs
            else:
                context.filtered_documents = docs

            # 문서 수 제한
            context.filtered_documents = context.filtered_documents[:35]
            print(f"📄 최종 문서 수: {len(context.filtered_documents)}개 (상위 35개로 제한)")

            context.metadata['filtered_docs_count'] = len(context.filtered_documents)

        except Exception as e:
            print(f"❌ {self.stage_name} 오류: {e}")
            context.metadata[f'{self.stage_name}_error'] = str(e)
            context.filtered_documents = context.search_results or []

        finally:
            self._record_stage_time(context)

        return context

    def _filter_documents_by_region(self, docs: List[Any], target_regions: List[str]) -> List[Any]:
        """지역별 문서 필터링"""
        filtered_docs = []

        for doc in docs:
            doc_region = doc.metadata.get('region', '').lower()
            doc_city = doc.metadata.get('city', '').lower()

            # 지역/도시 매칭 확인
            is_relevant = False
            for region in target_regions:
                region_lower = region.lower()

                # 지역명 매칭
                if region_lower in doc_region or region_lower in doc_city:
                    is_relevant = True
                    break

                # 약어 매칭
                region_short = region_lower.replace('특별시', '').replace('광역시', '').replace('특별자치도', '').replace('도', '')
                if region_short and (region_short in doc_region or region_short in doc_city):
                    is_relevant = True
                    break

            if is_relevant:
                filtered_docs.append(doc)

        return filtered_docs


class PlaceExtractionStage(ProcessingStage):
    """장소 추출 스테이지"""

    @property
    def stage_name(self) -> str:
        return "place_extraction"

    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """구조화된 장소 데이터 추출"""
        context.metadata['stage_start_time'] = time.time()
        print(f"🏗️ {self.stage_name} 시작")

        try:
            docs = context.filtered_documents or []

            # 구조화된 장소 데이터 추출
            structured_places = extract_structured_places(docs)
            context.structured_places = structured_places

            print(f"🏗️ 구조화된 장소 추출 완료: {len(structured_places)}개")
            context.metadata['structured_places_count'] = len(structured_places)

        except Exception as e:
            print(f"❌ {self.stage_name} 오류: {e}")
            context.metadata[f'{self.stage_name}_error'] = str(e)
            context.structured_places = []

        finally:
            self._record_stage_time(context)

        return context


class ResponseGenerationStage(ProcessingStage):
    """응답 생성 스테이지"""

    @property
    def stage_name(self) -> str:
        return "response_generation"

    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """LLM 응답 생성"""
        context.metadata['stage_start_time'] = time.time()
        print(f"🤖 {self.stage_name} 시작")

        try:
            travel_context = get_travel_context()
            docs = context.filtered_documents or []
            entities = context.extracted_entities or {}

            # 컨텍스트 생성
            search_context = self._build_search_context(docs)
            available_places = self._extract_place_names(docs)
            region_constraint = self._build_region_constraint(entities)

            enhanced_context = f"""
사용 가능한 장소 목록 (총 {len(available_places)}개):
{chr(10).join([f"• {place}" for place in available_places])}

상세 정보:
{search_context}
"""

            print(f"📝 컨텍스트 길이: {len(enhanced_context)} 문자")
            print(f"🔗 사용 가능한 장소 수: {len(available_places)}개")

            # LLM 프롬프트 생성
            enhanced_prompt = self._create_travel_prompt()

            # LLM으로 응답 생성
            prompt_value = enhanced_prompt.invoke({
                "context": enhanced_context,
                "question": context.query,
                "region_constraint": region_constraint
            })

            raw_response = travel_context.llm.invoke(prompt_value).content
            context.response_text = raw_response

            # 가독성을 위한 개행 처리
            formatted_response = format_travel_response_with_linebreaks(raw_response)
            context.formatted_response = formatted_response

            print(f"🤖 LLM 응답 길이: {len(raw_response)} 문자")
            context.metadata['response_length'] = len(raw_response)

        except Exception as e:
            print(f"❌ {self.stage_name} 오류: {e}")
            context.metadata[f'{self.stage_name}_error'] = str(e)
            context.response_text = "응답 생성 중 오류가 발생했습니다."
            context.formatted_response = context.response_text

        finally:
            self._record_stage_time(context)

        return context

    def _build_search_context(self, docs: List[Any]) -> str:
        """검색 컨텍스트 구성"""
        context_parts = []
        for doc in docs:
            context_parts.append(doc.page_content)
        return "\n\n".join(context_parts)

    def _extract_place_names(self, docs: List[Any]) -> List[str]:
        """문서에서 장소명 추출"""
        available_places = []
        for doc in docs:
            place_name = doc.page_content.split('\n')[0] if doc.page_content else "알 수 없는 장소"
            if "이름:" in place_name:
                place_name = place_name.split("이름:")[-1].strip()
            available_places.append(place_name)
        return available_places

    def _build_region_constraint(self, entities: Dict[str, Any]) -> str:
        """지역 제약 조건 구성"""
        target_regions = entities.get('regions', []) + entities.get('cities', [])
        if target_regions:
            return f"\n\n⚠️ 중요: 반드시 다음 지역의 장소들만 추천해주세요: {', '.join(target_regions)}\n"
        return ""

    def _create_travel_prompt(self) -> ChatPromptTemplate:
        """여행 추천 프롬프트 생성"""
        return ChatPromptTemplate.from_template("""
당신은 한국 여행 전문가입니다. 사용자의 여행 요청에 대해 구체적이고 실용적인 여행 일정을 작성해주세요.

다음 여행지 정보를 참고하여 답변하세요:
{context}

{region_constraint}

사용자 질문: {question}

다음 형식으로 답변해주세요:

<strong>[지역명] [기간] 여행 일정</strong><br>

<strong>[1일차]</strong>
• 09:00-XX:XX <strong>장소명</strong> - 간단한 설명 (1줄) <br>
• 12:00-13:00 <strong>식당명</strong> - 음식 종류 점심 <br>
• XX:XX-XX:XX <strong>장소명</strong> - 간단한 설명 (1줄) <br>
• 18:00-19:00 <strong>식당명</strong> - 음식 종류 저녁 <br>
<br>

<strong>[2일차]</strong> (기간에 따라 추가)
...

시간 표시 규칙:
- 시작시간은 명시하되, 종료시간은 활동 특성에 따라 유동적으로 설정
- 각 활동 옆에 예상 소요시간을 괄호로 표시
- 다음 활동 시작 전 충분한 여유시간 확보

💡 <strong>여행 팁</strong>: 지역 특색이나 주의사항
<br>
이 일정으로 확정하시겠어요?

주의사항:
1. 반드시 제공된 장소 목록에서만 선택하세요
2. 시간대별로 논리적인 동선을 고려하세요
3. 식사 시간을 포함하여 현실적인 일정을 짜세요
4. 각 장소에 대한 간단한 설명을 포함하세요
5. 사용자 확정 질문을 마지막에 포함하세요
""")


class TravelPlanParsingStage(ProcessingStage):
    """여행 일정 파싱 스테이지"""

    @property
    def stage_name(self) -> str:
        return "travel_plan_parsing"

    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """여행 일정 파싱 처리"""
        context.metadata['stage_start_time'] = time.time()
        print(f"🔧 {self.stage_name} 시작")

        try:
            formatted_response = context.formatted_response or ""
            structured_places = context.structured_places or []
            travel_dates = context.metadata.get('travel_dates', '미정')

            # 상세한 여행 일정 파싱
            travel_plan = parse_enhanced_travel_plan(
                formatted_response,
                context.query,
                structured_places,
                travel_dates
            )

            # 파싱된 날짜 정보 업데이트
            parsed_dates = context.metadata.get('parsed_dates', {})
            if parsed_dates:
                travel_plan['parsed_dates'] = parsed_dates

            # 파싱된 일차 수를 기반으로 days 정보 업데이트
            parsed_days_count = len(travel_plan.get("days", []))
            if parsed_days_count > 0:
                print(f"🔢 파싱된 일차 수: {parsed_days_count}개")
                if "parsed_dates" in travel_plan:
                    travel_plan["parsed_dates"]["days"] = f"{parsed_days_count}일"

            context.travel_plan = travel_plan

            # UI용 구조화된 응답 생성
            formatted_ui_response = create_formatted_ui_response(travel_plan, formatted_response)
            context.formatted_ui_response = formatted_ui_response

            print(f"✅ 여행 일정 파싱 완료")
            context.metadata['travel_plan_days'] = len(travel_plan.get("days", []))
            context.metadata['travel_plan_places'] = len(travel_plan.get("places", []))

        except Exception as e:
            print(f"❌ {self.stage_name} 오류: {e}")
            context.metadata[f'{self.stage_name}_error'] = str(e)
            context.travel_plan = {}
            context.formatted_ui_response = {}

        finally:
            self._record_stage_time(context)

        return context


class DataPersistenceStage(ProcessingStage):
    """데이터 저장 스테이지"""

    @property
    def stage_name(self) -> str:
        return "data_persistence"

    async def process(self, context: ProcessingContext) -> ProcessingContext:
        """데이터베이스 저장 처리"""
        context.metadata['stage_start_time'] = time.time()
        print(f"💾 {self.stage_name} 시작")

        try:
            travel_plan = context.travel_plan or {}

            def safe_save_travel_plan(db, **kwargs):
                """안전한 여행 계획 저장"""
                result = save_travel_plan(db, **kwargs)
                if result:
                    return {"id": result.id, "title": result.title}
                return None

            saved_plan_info = SafeDBOperation.execute_with_retry(
                safe_save_travel_plan,
                user_id=context.user_id,
                travel_plan=travel_plan,
                query=context.query,
                raw_response=context.response_text,
                formatted_response=context.formatted_response,
                ui_response=context.formatted_ui_response,
                session_id=context.session_id
            )

            if saved_plan_info:
                print(f"💾 여행 계획 DB 저장 성공: ID {saved_plan_info['id']}")
                # travel_plan에 DB ID 추가
                if context.travel_plan:
                    context.travel_plan["db_id"] = saved_plan_info["id"]
                context.metadata['saved_plan_id'] = saved_plan_info['id']
            else:
                print(f"⚠️ 여행 계획 DB 저장 실패")
                context.metadata['save_failed'] = True

        except Exception as e:
            print(f"❌ {self.stage_name} 오류: {e}")
            context.metadata[f'{self.stage_name}_error'] = str(e)

        finally:
            self._record_stage_time(context)

        return context


class RAGProcessingPipeline:
    """RAG 처리 파이프라인"""

    def __init__(self, stages: List[ProcessingStage]):
        self.stages = stages

    async def process(self, query: str, user_id: str, session_id: str) -> Dict[str, Any]:
        """파이프라인 실행"""
        context = ProcessingContext(
            query=query,
            user_id=user_id,
            session_id=session_id
        )

        print(f"🚀 RAG 파이프라인 시작: {len(self.stages)}개 스테이지")

        for stage in self.stages:
            stage_start = time.time()
            try:
                print(f"▶️ {stage.stage_name} 스테이지 시작")
                context = await stage.process(context)

                stage_duration = time.time() - stage_start
                context.metadata[f"{stage.stage_name}_duration"] = stage_duration
                print(f"✅ {stage.stage_name} 완료 ({stage_duration:.2f}초)")

            except Exception as e:
                stage_duration = time.time() - stage_start
                context.metadata[f"{stage.stage_name}_error"] = str(e)
                context.metadata[f"{stage.stage_name}_duration"] = stage_duration
                print(f"❌ {stage.stage_name} 실패: {e}")
                raise ProcessingError(f"Failed at {stage.stage_name}: {e}")

        # 총 처리 시간 기록
        total_duration = time.time() - context.metadata['start_time']
        context.metadata["total_duration"] = total_duration

        print(f"🏁 RAG 파이프라인 완료 ({total_duration:.2f}초)")

        # 결과 반환
        return self._build_result(context)

    def _build_result(self, context: ProcessingContext) -> Dict[str, Any]:
        """결과 구성"""
        return {
            "content": context.formatted_response or "응답을 생성할 수 없습니다.",
            "type": "text",
            "travel_plan": context.travel_plan or {},
            "formatted_ui_response": context.formatted_ui_response or {},
            "rag_results": context.filtered_documents or [],
            "metadata": context.metadata
        }


class ProcessingError(Exception):
    """파이프라인 처리 에러"""
    pass


def create_default_rag_pipeline() -> RAGProcessingPipeline:
    """기본 RAG 파이프라인 생성"""
    stages = [
        EntityExtractionStage(),
        VectorSearchStage(),
        RegionFilteringStage(),
        PlaceExtractionStage(),
        ResponseGenerationStage(),
        TravelPlanParsingStage(),
        DataPersistenceStage()
    ]
    return RAGProcessingPipeline(stages)


# 성능 최적화를 위한 캐시된 파이프라인 인스턴스
_cached_pipeline: Optional[RAGProcessingPipeline] = None


def get_rag_pipeline() -> RAGProcessingPipeline:
    """캐시된 RAG 파이프라인 조회"""
    global _cached_pipeline
    if _cached_pipeline is None:
        _cached_pipeline = create_default_rag_pipeline()
    return _cached_pipeline