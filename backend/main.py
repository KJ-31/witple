from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import redis
import logging
import os
from database import engine, Base
from routers import auth, users, posts, attractions, recommendations, profile
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
        "http://localhost:3001",  # Next.js 개발서버 포트 추가
        "http://frontend:3000",
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
app.include_router(posts.router, prefix="/api/v1/posts", tags=["posts"])
app.include_router(attractions.router, prefix="/api/v1/attractions", tags=["attractions"])
app.include_router(recommendations.router, prefix="/api/v1", tags=["recommendations"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["profile"])


@app.get("/")
async def root():
    return {"message": "Witple API is running!"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "redis": redis_client.ping()}
