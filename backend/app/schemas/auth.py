from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.rpartition("@")
        if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("请输入有效的邮箱地址")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=2048)


class AuthUserResponse(BaseModel):
    id: str
    email: str | None
    email_confirmed_at: datetime | None = None


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int | None = None
    expires_at: int | None = None


class AuthResponse(BaseModel):
    user: AuthUserResponse
    session: AuthSessionResponse | None
    message: str | None = None


class StatusResponse(BaseModel):
    status: str
