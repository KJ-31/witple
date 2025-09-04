from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True)  # 기존 스키마에 맞춤
    email = Column(String, unique=True, index=True, nullable=False)
    pw = Column(String, nullable=True)  # OAuth 사용자는 비밀번호 없음
    name = Column(String, nullable=True)  # 기존 스키마에 맞춤
    age = Column(Integer, nullable=True)
    nationality = Column(String, nullable=True)
    phone_e164 = Column(String, nullable=True)
    points_balance = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=False))  # 기존 스키마에 맞춤
    updated_at = Column(DateTime(timezone=False))

    # Relationships
    posts = relationship("Post", back_populates="user")
    oauth_accounts = relationship("OAuthAccount", back_populates="user")


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    provider = Column(String, nullable=False)  # 'google', 'facebook', 'github' 등
    provider_user_id = Column(String, nullable=False)  # OAuth 제공자에서의 사용자 ID
    email = Column(String, nullable=True)  # OAuth에서 받은 이메일
    name = Column(String, nullable=True)  # OAuth에서 받은 이름
    profile_picture = Column(String, nullable=True)  # 프로필 이미지 URL
    access_token = Column(Text, nullable=True)  # OAuth 액세스 토큰
    refresh_token = Column(Text, nullable=True)  # OAuth 리프레시 토큰
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), onupdate=func.now())

    # Unique constraint for provider + provider_user_id
    __table_args__ = (
        {'extend_existing': True}
    )

    # Relationship to user
    user = relationship("User", back_populates="oauth_accounts")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    caption = Column(Text, nullable=False)
    image_url = Column(String, nullable=False)  # 이미지 파일 경로 또는 URL
    location = Column(String, nullable=True)
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to user
    user = relationship("User", back_populates="posts")
