from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated
import logging
import uuid
from datetime import datetime
from database import get_db
from models import User, OAuthAccount
from schemas import UserCreate, UserResponse, Token
from auth_utils import verify_password, get_password_hash, create_access_token, get_current_user

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Register request received: email={user.email}, username={user.username}, full_name={user.full_name}")
    
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
            username=user.username,
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


# 기존 Google OAuth 엔드포인트 제거됨 (NextAuth.js 사용)


# NextAuth 콜백 엔드포인트
@router.post("/oauth/callback")
async def nextauth_callback(request: Request, db: Session = Depends(get_db)):
    """NextAuth에서 호출하는 OAuth 콜백 처리"""
    try:
        body = await request.json()
        provider = body.get("provider")
        provider_user_id = body.get("provider_user_id")
        email = body.get("email")
        name = body.get("name")
        image = body.get("image")
        
        logger.info(f"NextAuth callback: {provider}, {email}, {name}")
        
        if not provider or not provider_user_id or not email:
            raise HTTPException(status_code=400, detail="Invalid OAuth data")
        
        # 1. 기존 OAuth 계정이 있는지 확인
        existing_oauth = db.query(OAuthAccount).filter(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id
        ).first()
        
        if existing_oauth:
            # 기존 OAuth 계정이 있으면 해당 사용자로 로그인
            user = existing_oauth.user
            access_token = create_access_token(data={"sub": user.email})
            logger.info(f"Existing OAuth user login: {user.email}")
            return {"access_token": access_token, "token_type": "bearer", "user": user}
        
        # 2. OAuth 계정은 없지만 같은 이메일의 사용자가 있는지 확인
        existing_user = db.query(User).filter(User.email == email).first()
        
        if existing_user:
            # 기존 사용자에 OAuth 계정 연결
            oauth_account = OAuthAccount(
                user_id=existing_user.user_id,
                provider=provider,
                provider_user_id=provider_user_id,
                email=email,
                name=name,
                profile_picture=image,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(oauth_account)
            db.commit()
            
            access_token = create_access_token(data={"sub": existing_user.email})
            logger.info(f"OAuth account linked to existing user: {existing_user.email}")
            return {"access_token": access_token, "token_type": "bearer", "user": existing_user}
        
        # 3. 완전히 새로운 사용자 생성
        user_id = str(uuid.uuid4())
        new_user = User(
            user_id=user_id,
            email=email,
            name=name,
            pw=None,  # OAuth 사용자는 비밀번호 없음
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 새 사용자와 OAuth 계정을 함께 저장
        db.add(new_user)
        db.flush()  # user_id를 얻기 위해 flush
        
        oauth_account = OAuthAccount(
            user_id=new_user.user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            profile_picture=image,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(oauth_account)
        db.commit()
        db.refresh(new_user)
        
        access_token = create_access_token(data={"sub": new_user.email})
        logger.info(f"New OAuth user created: {new_user.email}")
        return {"access_token": access_token, "token_type": "bearer", "user": new_user}
        
    except Exception as e:
        logger.error(f"NextAuth callback error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="OAuth processing failed")
