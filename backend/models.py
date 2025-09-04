from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True)  # 기존 스키마에 맞춤
    email = Column(String, unique=True, index=True, nullable=False)
    pw = Column(String, nullable=False)  # 기존 스키마에 맞춤
    name = Column(String, nullable=True)  # 기존 스키마에 맞춤
    age = Column(Integer, nullable=True)
    nationality = Column(String, nullable=True)
    phone_e164 = Column(String, nullable=True)
    points_balance = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=False))  # 기존 스키마에 맞춤
    updated_at = Column(DateTime(timezone=False))

    # Relationship to posts
    posts = relationship("Post", back_populates="user")


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
