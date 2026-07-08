from datetime import date

from pydantic import BaseModel, Field


class HealthContentResponse(BaseModel):
    disease_code: str = Field(description="질환 코드(질환명)", examples=["당뇨"])
    category: str = Field(description="콘텐츠 카테고리", examples=["LIFESTYLE"])
    content_date: date = Field(description="콘텐츠 기준 날짜")
    title: str = Field(description="카드 제목")
    summary: str = Field(description="카드 요약(카드뉴스용)")
    body: str = Field(description="카드 본문")
    image_prompt: str | None = Field(default=None, description="카드뉴스 이미지 생성용 프롬프트(T-LLM-4에서 사용)")
    disclaimer: str = Field(description="면책 문구(응답 시점에 항상 동적으로 부착됨)")


class ContentsFeedResponse(BaseModel):
    personalized: bool = Field(
        description="true면 로그인한 프로필의 등록 질환 기준 결과, false면 비로그인/질환 미등록으로 전체 콘텐츠를 폴백한 결과"
    )
    items: list[HealthContentResponse] = Field(description="누적 피드 카드 목록(최신 날짜순)")
