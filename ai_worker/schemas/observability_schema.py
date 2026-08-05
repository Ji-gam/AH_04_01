from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    trace_id: str = Field(description="점수를 붙일 Langfuse trace id")
    name: str = Field(description="점수 이름 (예: user_feedback)")
    value: float = Field(description="점수 값")
    comment: str | None = Field(default=None, description="자유 서술 코멘트")
