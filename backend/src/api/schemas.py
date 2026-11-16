from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Turn(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=8000)


class Filters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    crop: str | None = Field(default=None, max_length=100)
    topic: str | None = Field(default=None, max_length=100)
    source_organization: str | None = Field(default=None, max_length=200)
    publication_date: str | None = Field(default=None, max_length=40)
    district: str | None = Field(default=None, max_length=100)
    organic_standard: str | None = Field(default=None, max_length=100)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[Turn] = Field(default_factory=list, max_length=12)
    filters: Filters = Field(default_factory=Filters)

    @field_validator('question')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Question cannot be blank.')
        return value.strip()


class ChatResponse(BaseModel):
    answer: str
    detected_language: str
    citations: list[dict] = Field(default_factory=list)
    evidence_status: Literal['supported', 'insufficient', 'out_of_scope']
    metadata: dict = Field(default_factory=dict)
