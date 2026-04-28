from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 10_000


class ServiceRequest(BaseModel):
    name: str = Field(..., examples=["Payment Gateway"])
    description: Optional[str] = Field(None, examples=["Main payment service"])

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Service name cannot be empty")
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"Service name cannot exceed {MAX_NAME_LENGTH} characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description cannot exceed {MAX_DESCRIPTION_LENGTH} characters")
        return v


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
