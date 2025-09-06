from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import TokenData
from config import settings

# bcrypt 오류 방지를 위한 안정적인 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password, hashed_password):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def get_password_hash(password):
    try:
        return pwd_context.hash(password)
    except Exception as e:
        print(f"Password hashing error: {e}")
        # fallback to simple hash if bcrypt fails
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    import logging
    logger = logging.getLogger(__name__)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        logger.info(f"토큰 검증 시작 - 토큰 길이: {len(token) if token else 0}")
        logger.info(f"SECRET_KEY 길이: {len(settings.SECRET_KEY)}")
        logger.info(f"ALGORITHM: {settings.ALGORITHM}")
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        logger.info(f"JWT 디코딩 성공 - payload: {payload}")
        
        email: str = payload.get("sub")
        if email is None:
            logger.error("JWT payload에서 email(sub) 찾을 수 없음")
            raise credentials_exception
            
        logger.info(f"토큰에서 추출된 이메일: {email}")
        token_data = TokenData(email=email)
        
    except JWTError as e:
        logger.error(f"JWT 에러 발생: {str(e)}")
        logger.error(f"토큰 내용 (처음 50자): {token[:50] if token else 'None'}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"예상치 못한 에러: {str(e)}")
        raise credentials_exception
    
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        logger.error(f"사용자 찾을 수 없음: {token_data.email}")
        raise credentials_exception
        
    logger.info(f"사용자 인증 성공: {user.email}")
    return user
