from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated
import logging
from database import get_db
from models import User
from schemas import UserCreate, UserResponse, Token
from auth_utils import verify_password, get_password_hash, create_access_token, get_current_user

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Register request received: email={user.email}, full_name={user.full_name}")
    
    try:
        # 이메일 중복 확인
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            logger.warning(f"Email already registered: {user.email}")
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # 새 사용자 생성
        logger.info("Creating new user...")
        hashed_password = get_password_hash(user.password)
        logger.info("Password hashed successfully")
        
        db_user = User(
            email=user.email,
            hashed_password=hashed_password,
            full_name=user.full_name
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User created successfully: id={db_user.id}")
        return db_user
        
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    logger.info("Login endpoint called - Step 1")
    
    try:
        logger.info("Step 2: Getting request body")
        # 요청 본문을 직접 파싱
        body = await request.body()
        logger.info(f"Step 3: Raw request body: {body}")
        
        logger.info("Step 4: Decoding body")
        # URL 디코딩
        import urllib.parse
        decoded_body = urllib.parse.unquote(body.decode())
        logger.info(f"Step 5: Decoded body: {decoded_body}")
        
        logger.info("Step 6: Parsing parameters")
        # 파라미터 파싱
        params = {}
        for param in decoded_body.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
        
        logger.info(f"Step 7: Parsed params: {params}")
        
        username = params.get('username')
        password = params.get('password')
        
        logger.info(f"Step 8: Username: {username}, Password: {password}")
        
        if not username or not password:
            logger.error("Missing username or password")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing username or password"
            )
        
        logger.info(f"Step 9: Login attempt for username: {username}")
        
        # 사용자 조회
        logger.info("Step 10: Querying database")
        user = db.query(User).filter(User.email == username).first()
        logger.info(f"Step 11: User found: {user is not None}")
        
        if not user:
            logger.warning(f"User not found: {username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 비밀번호 검증
        logger.info("Step 12: Verifying password...")
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Password verification failed for user: {username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 토큰 생성
        logger.info("Step 13: Creating access token...")
        access_token = create_access_token(data={"sub": user.email})
        logger.info(f"Step 14: Login successful for user: {user.email}")
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException:
        logger.info("Step X: HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"Step X: Unexpected error during login: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
