from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import ARRAY
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
    profile_image = Column(String, nullable=True)  # 프로필 이미지 URL
    created_at = Column(DateTime(timezone=False))  # 기존 스키마에 맞춤
    updated_at = Column(DateTime(timezone=False))

    # Relationships
    posts = relationship("Post", back_populates="user")
    oauth_accounts = relationship("OAuthAccount", back_populates="user")
    preferences = relationship("UserPreference", back_populates="user")
    preference_tags = relationship("UserPreferenceTag", back_populates="user")
    saved_locations = relationship("SavedLocation", back_populates="user")
    trips = relationship("Trip", back_populates="user")
    
    # 새로운 데이터 수집 관련 관계들
    actions = relationship("UserAction", back_populates="user")
    behavior_vector = relationship("UserBehaviorVector", back_populates="user", uselist=False)


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


class PostLike(Base):
    __tablename__ = "post_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    persona = Column(String, nullable=True)  # luxury, modern, nature_activity, foodie
    priority = Column(String, nullable=True)  # accommodation, restaurants, experience, shopping
    accommodation = Column(String, nullable=True)  # comfort, healing, traditional, community
    exploration = Column(String, nullable=True)  # hot, local, balance, authentic_experience
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to user
    user = relationship("User", back_populates="preferences")


class UserPreferenceTag(Base):
    __tablename__ = "user_preference_tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    tag = Column(String, nullable=False)
    weight = Column(Integer, default=1)  # 태그의 가중치
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to user
    user = relationship("User", back_populates="preference_tags")

    
class SavedLocation(Base):
    __tablename__ = "saved_locations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    places = Column(Text, nullable=False)  # "table_name:table_id" 형식
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to user
    user = relationship("User", back_populates="saved_locations")

    
class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    title = Column(String, nullable=False)  # 여행 제목
    places = Column(Text, nullable=True)  # 장소들 (JSON 형태로 저장: [{"name": "장소명", "order": 1, "latitude": "37.5", "longitude": "127.0"}])
    start_date = Column(DateTime(timezone=False), nullable=False)  # 시작 날짜
    end_date = Column(DateTime(timezone=False), nullable=False)  # 종료 날짜
    status = Column(String, default='planned')  # planned, active, completed
    total_budget = Column(Integer, nullable=True)  # 총 예산
    cover_image = Column(String, nullable=True)  # 커버 이미지 URL
    description = Column(Text, nullable=True)  # 여행 설명
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to user
    user = relationship("User", back_populates="trips")


class UserAction(Base):
    """사용자 행동 데이터 - Collection Server에서 수집된 데이터 저장"""
    __tablename__ = "user_actions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    place_category = Column(String, nullable=False, index=True)  # actionTracker 호환
    place_id = Column(String, nullable=False, index=True)        # actionTracker 호환  
    action_type = Column(String, nullable=False, index=True)     # 'click', 'like', 'bookmark'
    action_value = Column(Integer, nullable=True)                # actionTracker 호환
    action_detail = Column(JSON, nullable=True)                  # actionTracker 호환
    session_id = Column(String, nullable=True, index=True)
    
    # 서버 메타데이터
    server_timestamp = Column(DateTime(timezone=True), nullable=True)
    client_ip = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String, nullable=True)
    
    # AWS Batch 처리 상태
    batch_processed = Column(Boolean, default=False, index=True)
    batch_processed_at = Column(DateTime(timezone=True), nullable=True)
    batch_id = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 인덱스 최적화를 위한 테이블 설정
    __table_args__ = (
        {'extend_existing': True}
    )
    
    # Relationship
    user = relationship("User")


class UserBehaviorVector(Base):
    """AWS Batch에서 생성하는 사용자 행동 벡터 (BERT 384차원)"""
    __tablename__ = "user_behavior_vectors"
    
    user_id = Column(String, ForeignKey("users.user_id"), primary_key=True)
    
    # BERT 벡터 (384차원) - PostgreSQL ARRAY 타입
    behavior_vector = Column(ARRAY(Float), nullable=True)
    
    # 행동 점수들 (0.0~100.0)
    like_score = Column(Float, default=0.0)              # 좋아요 선호도 점수
    bookmark_score = Column(Float, default=0.0)          # 북마크 선호도 점수
    click_score = Column(Float, default=0.0)             # 클릭 패턴 점수
    dwell_time_score = Column(Float, default=0.0)        # 체류시간 점수 (향후 확장)
    
    # 통계 메타데이터
    total_actions = Column(Integer, default=0)           # 총 액션 수
    total_likes = Column(Integer, default=0)             # 총 좋아요 수
    total_bookmarks = Column(Integer, default=0)         # 총 북마크 수
    total_clicks = Column(Integer, default=0)            # 총 클릭 수
    
    # 최신성 정보
    last_action_date = Column(DateTime(timezone=True), nullable=True)
    vector_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship  
    user = relationship("User")


class PlaceVector(Base):
    """장소별 벡터 데이터 (추천 성능 향상용)"""
    __tablename__ = "place_vectors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    place_id = Column(String, nullable=False, index=True)
    place_category = Column(String, nullable=False, index=True)
    
    # 장소 특성 벡터들
    content_vector = Column(ARRAY(Float), nullable=True)    # 내용 기반 벡터 (장소 설명, 태그 등)
    behavior_vector = Column(ARRAY(Float), nullable=True)   # 행동 기반 벡터 (사용자 액션 기반)
    combined_vector = Column(ARRAY(Float), nullable=True)   # 결합 벡터 (추천용)
    
    # 장소별 통계 정보
    total_likes = Column(Integer, default=0)
    total_bookmarks = Column(Integer, default=0) 
    total_clicks = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)               # 고유 사용자 수
    avg_dwell_time = Column(Float, default=0.0)             # 평균 체류시간
    
    # 인기도 점수 (0.0~100.0)
    popularity_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)           # 참여도 점수
    
    # 벡터 업데이트 정보
    vector_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    stats_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        {'extend_existing': True}
    )
