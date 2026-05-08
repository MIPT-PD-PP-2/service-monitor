from pydantic import BaseModel


class StatusResponse(BaseModel):
    is_running: bool
    interval: int
    endpoints_count: int


class TriggerResponse(BaseModel):
    detail: str
