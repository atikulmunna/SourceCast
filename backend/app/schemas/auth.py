from pydantic import BaseModel, EmailStr, Field, field_validator
import uuid
from datetime import datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        if v.isdigit() or v.isalpha():
            raise ValueError("Password must contain letters and numbers")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(TokenResponse):
    user: UserOut
