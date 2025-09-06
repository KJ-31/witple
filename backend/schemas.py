from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    profile_image: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Post schemas
class PostBase(BaseModel):
    caption: str
    location: Optional[str] = None


class PostCreate(PostBase):
    image_data: str  # Base64 encoded image data


class PostResponse(PostBase):
    id: int
    user_id: str
    image_url: str
    likes_count: int
    comments_count: int
    created_at: datetime
    user: UserResponse
    
    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    posts: List[PostResponse]
    total: int


# Recommendation schemas
class PersonaType(str, Enum):
    luxury = "luxury"
    modern = "modern"
    nature_activity = "nature_activity"
    foodie = "foodie"


class PriorityType(str, Enum):
    accommodation = "accommodation"
    restaurants = "restaurants"
    experience = "experience"
    shopping = "shopping"


class AccommodationType(str, Enum):
    comfort = "comfort"
    healing = "healing"
    traditional = "traditional"
    community = "community"


class ExplorationType(str, Enum):
    hot = "hot"
    local = "local"
    balance = "balance"
    authentic_experience = "authentic_experience"


# Profile update schemas (moved after Enum definitions)
class ProfileImageUpdate(BaseModel):
    image_data: str  # Base64 encoded image data


class ProfileInfoUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None


class ProfilePreferencesUpdate(BaseModel):
    persona: Optional[PersonaType] = None
    priority: Optional[PriorityType] = None
    accommodation: Optional[AccommodationType] = None
    exploration: Optional[ExplorationType] = None


class ActionType(str, Enum):
    click = "click"
    dwell_time = "dwell_time"
    scroll_depth = "scroll_depth"
    like = "like"
    bookmark = "bookmark"
    search = "search"


class UserPreferencesBasic(BaseModel):
    persona: PersonaType
    priority: PriorityType
    accommodation: AccommodationType
    exploration: ExplorationType


class UserPreferencesTag(BaseModel):
    tag: str
    weight: float = 1.0


class PlaceRecommendation(BaseModel):
    id: str
    place_id: int
    table_name: str
    name: str
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    similarity_score: Optional[float] = None
    popularity_score: Optional[float] = None
    recommendation_type: Optional[str] = None


class RecommendationRequest(BaseModel):
    region: Optional[str] = None
    category: Optional[str] = None
    limit: int = 20


class UserActionLog(BaseModel):
    place_category: str
    place_id: int
    action_type: ActionType
    action_value: Optional[float] = None
    action_detail: Optional[str] = None
