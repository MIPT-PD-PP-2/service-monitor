from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_URL_LENGTH = 2048
ALLOWED_URL_PREFIXES = ("http://", "https://")


class EndpointRequest(BaseModel):
    url: str = Field(..., examples=["https://payment.internal/health"])
    is_active: Optional[bool] = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        if len(v) > MAX_URL_LENGTH:
            raise ValueError(f"URL cannot exceed {MAX_URL_LENGTH} characters")
        if not v.startswith(ALLOWED_URL_PREFIXES):
            raise ValueError("URL must start with http:// or https://")
        return v


class EndpointUpdateRequest(BaseModel):
    url: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("URL cannot be empty")
        if len(v) > MAX_URL_LENGTH:
            raise ValueError(f"URL cannot exceed {MAX_URL_LENGTH} characters")
        if not v.startswith(ALLOWED_URL_PREFIXES):
            raise ValueError("URL must start with http:// or https://")
        return v


class EndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    url: str
    is_active: bool
    created_at: datetime
