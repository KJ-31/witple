"""
여행 추천 시스템 설정 및 초기화
"""
import os
import sys
import boto3
from langchain_aws import ChatBedrock
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from botocore.config import Config
from core.travel_context import TravelContext, initialize_travel_context


class TravelSystemConfig:
    """여행 시스템 설정 클래스"""

    def __init__(self):
        # AWS 설정
        self.aws_region = os.getenv('AWS_REGION')
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')

        # 모델 설정
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
        self.embedding_model = 'sentence-transformers/all-MiniLM-L12-v2'

        # DB 설정
        self.database_url = os.getenv('DATABASE_URL')
        self.collection_name = "place_recommendations"

        # 초기화된 객체들
        self.boto3_session = None
        self.llm = None
        self.embeddings = None
        self.vectorstore = None

    def initialize_aws_session(self):
        """AWS 세션 초기화"""
        try:
            self.boto3_session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
            print("✅ AWS 세션 초기화 성공")
            return True
        except Exception as e:
            print(f"❌ AWS 세션 생성 실패: {e}")
            return False

    def initialize_llm(self):
        """LLM 모델 초기화"""
        print("🤖 Amazon Bedrock Claude 모델 초기화 중...")
        try:
            # Retry 설정으로 과도한 재시도 방지
            retry_config = Config(
                retries={
                    'max_attempts': 3,  # 최대 2회만 재시도
                    'mode': 'adaptive'  # 적응적 재시도 모드
                }
            )

            # boto3 클라이언트에 직접 retry 설정 적용
            bedrock_client = self.boto3_session.client(
                'bedrock-runtime',
                region_name=self.aws_region,
                config=retry_config
            )

            self.llm = ChatBedrock(
                model_id=self.model_id,
                client=bedrock_client,
                model_kwargs={
                    "temperature": 0.2,
                    "max_tokens": 3000,
                    "top_p": 0.8,
                }
            )
            print("✅ LLM 초기화 성공")
            return True
        except Exception as e:
            print(f"❌ Bedrock LLM 초기화 실패: {e}")
            print("환경변수나 AWS CLI 설정을 확인해주세요.")
            return False

    def initialize_embeddings(self):
        """임베딩 모델 초기화"""
        print("🧠 Sentence Transformers 임베딩 모델 초기화 중...")
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model,
            )
            print("✅ 임베딩 모델 초기화 성공")
            return True
        except Exception as e:
            print(f"❌ 임베딩 모델 초기화 실패: {e}")
            return False

    def initialize_vectorstore(self):
        """벡터스토어 초기화"""
        print("🔗 벡터스토어 연결 중...")
        try:
            from database import engine as shared_engine
            self.vectorstore = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=shared_engine,
                pre_delete_collection=False,
            )
            print("✅ 벡터스토어 연결 성공")
            return True
        except Exception as e:
            print(f"❌ 벡터스토어 연결 실패: {e}")
            return False

    def initialize_all(self) -> TravelContext:
        """모든 컴포넌트 초기화"""
        print("🚀 여행 추천 시스템 초기화 시작...")

        # 단계별 초기화
        if not self.initialize_aws_session():
            sys.exit(1)

        if not self.initialize_llm():
            sys.exit(1)

        if not self.initialize_embeddings():
            sys.exit(1)

        if not self.initialize_vectorstore():
            sys.exit(1)

        print("✅ 모든 컴포넌트 초기화 완료")

        # TravelContext 초기화 (일단 기본 설정만)
        context = initialize_travel_context(
            llm=self.llm,
            retriever=None,  # initialize_retriever에서 설정됨
            db_catalogs=None,  # initialize_retriever에서 로드됨
            vectorstore=self.vectorstore,  # vectorstore 추가
            aws_region=self.aws_region,
            model_name=self.model_id
        )

        return context


# 전역 설정 인스턴스
_config_instance = None


def get_config() -> TravelSystemConfig:
    """전역 설정 인스턴스 반환"""
    global _config_instance
    if _config_instance is None:
        _config_instance = TravelSystemConfig()
    return _config_instance


def initialize_system() -> TravelContext:
    """시스템 전체 초기화"""
    config = get_config()
    return config.initialize_all()