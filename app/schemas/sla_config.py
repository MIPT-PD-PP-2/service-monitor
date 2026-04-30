from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_SLA_CONFIG_VALUE = 100
MIN_SLA_CONFIG_VALUE = 0
DEFAULT_SLA_TARGET = 99.0


class SlaConfigRequest(BaseModel):
    target_percent: float = Field(
        default=DEFAULT_SLA_TARGET,
        ge=MIN_SLA_CONFIG_VALUE,
        le=MAX_SLA_CONFIG_VALUE,
        description=f"Target percent must be between {MIN_SLA_CONFIG_VALUE} and {MAX_SLA_CONFIG_VALUE}"
    )


class SlaConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    service_id: int
    target_percent: float
