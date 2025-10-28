"""
Authentication API Schemas
Pydantic models for authentication endpoints
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.database.models import UserRole


# Token Schemas
class Token(BaseModel):
    """Token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data"""

    username: str | None = None
    user_id: int | None = None


# User Schemas
class UserBase(BaseModel):
    """Base user schema"""

    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: str | None = Field(None, max_length=255)


class UserCreate(UserBase):
    """Schema for user registration"""

    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Schema for user update"""

    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=255)
    password: str | None = Field(None, min_length=8, max_length=100)


class UserResponse(UserBase):
    """Schema for user response"""

    id: int
    role: UserRole
    is_active: bool
    is_superuser: bool
    last_login: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Login Schema
class LoginRequest(BaseModel):
    """Schema for login request"""

    username: str
    password: str


# Password Change Schema
class PasswordChange(BaseModel):
    """Schema for password change"""

    old_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
