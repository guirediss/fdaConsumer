from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DrugExtractRequest(BaseModel):
    generic_name: str = Field(min_length=2, max_length=120, examples=["sertraline"])
    limit: int = Field(default=5, ge=1, le=25)


class DrugLabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    set_id: str
    generic_name: str
    brand_name: str | None
    manufacturer_name: str | None
    route: str | None
    indications_and_usage: str | None
    extracted_at: datetime


class DrugExtractResponse(BaseModel):
    extracted_count: int
    items: list[DrugLabelResponse]


class DrugListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[DrugLabelResponse]
