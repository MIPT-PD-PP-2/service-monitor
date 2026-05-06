from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CheckResultsCreate(BaseModel):
    endpoint_id: int
    checked_at: datetime
    is_available: bool
    status_code: Optional[int] = Field(None, ge=100, le=599)
    response_time_ms: Optional[int] = Field(None, ge=0)
    error_message: Optional[str]


class CheckResultsResponse(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: int
  endpoint_id: int
  checked_at: datetime
  is_available: bool
  status_code: Optional[int]
  response_time_ms: Optional[int]
  error_message: Optional[str]
