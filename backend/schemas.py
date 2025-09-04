from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
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
