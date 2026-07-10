from typing import Any

from pydantic import BaseModel, Field


class GenerateStructuredRequest(BaseModel):
    system_prompt: str = Field(description="시스템 프롬프트")
    user_input: str = Field(description="사용자 입력")
    json_schema: dict[str, Any] = Field(description="응답이 따라야 할 JSON 스키마")


class GenerateStructuredResponse(BaseModel):
    data: dict[str, Any] = Field(description="요청받은 json_schema를 만족하는 생성 결과")
