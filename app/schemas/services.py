from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ServiceRequest(BaseModel):
    name: str
    description: Optional[str] = None


class ServiceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
