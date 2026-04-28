from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ResponsibleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Ivan Ivanov"])
    email: EmailStr = Field(..., examples=["ivanov@company.ru"])


class ResponsibleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    name: str
    email: str
