from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import redis
import logging
import os
from database import engine, Base
# ✅ v2 추천 시스템 사용 (v1 완전 제거)
from routers import auth, users, posts, attractions, recommendations2, profile, saved_locations, trips, batch_processing, chat
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Redis 클라이언트 초기화
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 데이터베이스 테이블 생성 (OAuth 테이블 추가를 위해 임시 활성화)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/updated")

    # Redis + FAISS 하이브리드 캐시 사전 초기화 (첫 요청 지연 방지)
    try:
        logger.info("🚀 Redis + FAISS 하이브리드 캐시 사전 초기화 시작...")
        from LLM_RAG import initialize_redis_faiss_cache
        initialize_redis_faiss_cache()
        logger.info("✅ Redis + FAISS 하이브리드 캐시 사전 초기화 완료")
    except Exception as e:
        logger.warning(f"⚠️ Redis + FAISS 하이브리드 캐시 사전 초기화 실패: {e}")

    yield
    # 앱 종료 시 정리 작업 (필요시)


app = FastAPI(
    title="Witple API",
    description="Witple 백엔드 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://frontend:3000",
        "https://witple.kro.kr",
        "https://k8s-witple-witplefr-01ff6c628a-1226095041.ap-northeast-2.elb.amazonaws.com",
        "http://k8s-witple-witplefr-01ff6c628a-1226095041.ap-northeast-2.elb.amazonaws.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    # 요청 본문 로깅 (POST 요청의 경우) - 본문을 읽지 않고 헤더만 확인
    if request.method == "POST":
        content_length = request.headers.get('content-length')
        logger.info(f"Content-Length: {content_length}")
    
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

# 업로드된 파일을 위한 정적 파일 서빙 설정
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 등록
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(posts.router, prefix="/api/v1", tags=["posts"])
app.include_router(attractions.router, prefix="/api/v1/attractions", tags=["attractions"])
# ❌ v1 추천 라우터 비활성화 (v2로 완전 대체)
# app.include_router(recommendations.router, prefix="/api/v1", tags=["recommendations"])

# ✅ v2 추천 라우터 (새로운 시스템)
app.include_router(recommendations2.router, prefix="/api/v2", tags=["recommendations-v2"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["profile"])
app.include_router(saved_locations.router, prefix="/api/v1/saved-locations", tags=["saved-locations"])
app.include_router(trips.router, prefix="/api/v1/trips", tags=["trips"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(batch_processing.router, prefix="/api/v1", tags=["batch-processing"])


@app.get("/")
async def root():
    return {"message": "Witple API is running!"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "redis": redis_client.ping()}


@app.get("/redis/test")
async def test_redis():
    """Redis 연결 및 기본 기능 테스트"""
    try:
        # 기본 Redis 작업 테스트
        test_key = "test:redis:connection"
        test_value = {"message": "Redis 연결 성공!", "timestamp": "2024-01-01T00:00:00Z"}
        
        # 데이터 저장
        redis_client.set(test_key, str(test_value), ex=60)  # 60초 후 만료
        
        # 데이터 조회
        retrieved_value = redis_client.get(test_key)
        
        # 카운터 증가 테스트
        counter_key = "test:counter"
        redis_client.incr(counter_key)
        counter_value = redis_client.get(counter_key)
        
        return {
            "status": "success",
            "redis_connection": redis_client.ping(),
            "test_data": {
                "stored": test_value,
                "retrieved": retrieved_value,
                "counter": int(counter_value) if counter_value else 0
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Redis 테스트 실패: {str(e)}"
        }
