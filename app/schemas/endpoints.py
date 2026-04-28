from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EndpointRequest(BaseModel):
    url: str
    is_active: Optional[bool] = True


class EndpointUpdateRequest(BaseModel):
    url: Optional[str] = None
    is_active: Optional[bool] = None


class EndpointResponse(BaseModel):
    id: int
    service_id: int
    url: str
    is_active: bool
    created_at: datetime
