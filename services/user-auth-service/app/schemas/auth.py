import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SendCodeRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MessageResponse(BaseModel):
    message: str


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile
