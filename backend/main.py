from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import redis
import logging
import os
from database import engine, Base
from routers import auth, users, posts, attractions, recommendations, profile, saved_locations, trips, chat
from cache_utils import get_redis_status, cache_invalidate_attractions, cache_invalidate_user_recommendations
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Redis 클라이언트 초기화 (연결 실패 시 None으로 설정)
redis_client = None
try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client.ping()  # 연결 테스트
    logger.info("Redis 연결 성공")
except Exception as e:
    logger.warning(f"Redis 연결 실패: {e}")
    logger.info("Redis 없이 애플리케이션을 계속 실행합니다.")
    redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 데이터베이스 테이블 생성 (OAuth 테이블 추가를 위해 임시 활성화)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/updated")
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
app.include_router(recommendations.router, prefix="/api/v1", tags=["recommendations"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["profile"])
app.include_router(saved_locations.router, prefix="/api/v1/saved-locations", tags=["saved-locations"])
app.include_router(trips.router, prefix="/api/v1/trips", tags=["trips"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])


@app.get("/")
async def root():
    return {"message": "Witple API is running!"}


@app.get("/health")
async def health_check():
    redis_status_info = get_redis_status()
    
    return {
        "status": "healthy", 
        "redis": redis_status_info
    }

@app.post("/admin/cache/invalidate/attractions")
async def invalidate_attractions_cache():
    """관광지 관련 캐시 무효화 (관리자용)"""
    try:
        deleted_count = cache_invalidate_attractions()
        return {
            "message": f"관광지 캐시가 무효화되었습니다.",
            "deleted_keys": deleted_count
        }
    except Exception as e:
        logger.error(f"Error invalidating attractions cache: {e}")
        raise HTTPException(status_code=500, detail="캐시 무효화 중 오류가 발생했습니다.")

@app.post("/admin/cache/invalidate/user/{user_id}")
async def invalidate_user_cache(user_id: str):
    """특정 사용자의 추천 캐시 무효화 (관리자용)"""
    try:
        deleted_count = cache_invalidate_user_recommendations(user_id)
        return {
            "message": f"사용자 {user_id}의 추천 캐시가 무효화되었습니다.",
            "deleted_keys": deleted_count
        }
    except Exception as e:
        logger.error(f"Error invalidating user cache: {e}")
        raise HTTPException(status_code=500, detail="캐시 무효화 중 오류가 발생했습니다.")
