from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel


class AdminUserResponse(BaseSerializerModel):
    id: Annotated[int, Field(description="User(계정)의 PK.")]
    email: Annotated[str, Field(description="로그인 이메일.")]
    is_admin: Annotated[bool, Field(description="관리자 여부.")]
    is_active: Annotated[bool, Field(description="계정 활성 상태.")]
    created_at: Annotated[datetime, Field(description="가입 시각.")]
    last_login: Annotated[datetime | None, Field(description="마지막 로그인 시각. 미로그인 시 null.")]
    # (2026-07-28) 관리자 화면에서 동의 현황도 같이 볼 수 있도록 추가.
    health_info_consented_at: Annotated[datetime | None, Field(description="개인건강정보 동의 시각.")]
    ai_chat_consented_at: Annotated[datetime | None, Field(description="AI 챗봇 데이터 활용 동의 시각.")]
    terms_of_service_consented_at: Annotated[datetime | None, Field(description="이용약관 동의 시각.")]
    marketing_consented_at: Annotated[datetime | None, Field(description="마케팅 정보 수신 동의 시각.")]


class SetAdminRequest(BaseModel):
    is_admin: Annotated[bool, Field(description="true면 관리자로 승격, false면 관리자 권한 해제.")]


class AdminActionResponse(BaseSerializerModel):
    id: Annotated[int, Field(description="감사로그 PK.")]
    actor_user_id: Annotated[int, Field(description="행위를 수행한 관리자의 User PK.")]
    actor_email: Annotated[str, Field(description="행위를 수행한 관리자의 이메일.")]
    action: Annotated[str, Field(description="행위 종류 (예: grant_admin, revoke_admin, create_notice).")]
    target: Annotated[str | None, Field(description="행위 대상 (user_id, notice_id 등).")]
    detail: Annotated[str | None, Field(description="사람이 읽을 수 있는 요약.")]
    created_at: Annotated[datetime, Field(description="행위 시각.")]


class SignupTrendPoint(BaseModel):
    date: Annotated[str, Field(description="YYYY-MM-DD 형식 날짜.")]
    count: Annotated[int, Field(description="그 날짜의 신규 가입자 수.")]


class ConsentSummary(BaseModel):
    terms_of_service: Annotated[int, Field(description="이용약관 동의자 수.")]
    health_info: Annotated[int, Field(description="개인건강정보 동의자 수.")]
    ai_chat: Annotated[int, Field(description="AI 챗봇 데이터 활용 동의자 수.")]
    marketing: Annotated[int, Field(description="마케팅 정보 수신 동의자 수.")]


class AdminStatsResponse(BaseModel):
    total_users: Annotated[int, Field(description="전체 가입자 수.")]
    total_admins: Annotated[int, Field(description="관리자 수.")]
    signup_trend: Annotated[list[SignupTrendPoint], Field(description="최근 7일 가입자 추이(날짜 오름차순).")]
    consent_summary: Annotated[ConsentSummary, Field(description="항목별 동의자 수.")]
    error_count_24h: Annotated[int, Field(description="최근 24시간 서버 오류 건수.")]


class ErrorLogResponse(BaseSerializerModel):
    id: Annotated[int, Field(description="오류로그 PK.")]
    created_at: Annotated[datetime, Field(description="발생 시각.")]
    method: Annotated[str, Field(description="HTTP 메서드.")]
    path: Annotated[str, Field(description="요청 경로.")]
    exception_type: Annotated[str, Field(description="예외 클래스명.")]
    message: Annotated[
        str | None,
        Field(description="잘라낸 예외 메시지(최대 200자). 민감정보 방지 위해 전체 트레이스백은 저장 안 함."),
    ]
    status_code: Annotated[int, Field(description="응답 상태 코드.")]


class TrendPoint(BaseModel):
    date: Annotated[str, Field(description="YYYY-MM-DD 형식 날짜.")]
    count: Annotated[int, Field(description="그 날짜의 건수.")]


class TopDrugItem(BaseModel):
    name: Annotated[str, Field(description="약품명.")]
    count: Annotated[int, Field(description="등록 건수.")]


class OpsStatsResponse(BaseModel):
    dau: Annotated[int, Field(description="일간 활성 사용자 수(24시간 내 로그인).")]
    wau: Annotated[int, Field(description="주간 활성 사용자 수(7일 내 로그인).")]
    adherence_rate: Annotated[
        float | None,
        Field(description="최근 7일 근사 복약 순응도(0~1). 등록약이 하나도 없으면 null."),
    ]
    top_drugs: Annotated[
        list[TopDrugItem],
        Field(description="등록 건수 상위 약품(등록자 3명 미만인 약은 재식별 위험 방지를 위해 제외)."),
    ]
    content_count_by_category: Annotated[
        dict[str, int], Field(description="카테고리별 생성된 건강 콘텐츠 수(조회수 추적은 없어서 인기순 아님).")
    ]
    chat_message_trend: Annotated[list[TrendPoint], Field(description="최근 7일 챗봇 메시지 수 추이.")]
    active_chat_sessions_7d: Annotated[int, Field(description="최근 7일 내 갱신된 챗봇 세션 수.")]
    notification_count_trend: Annotated[
        list[TrendPoint], Field(description="최근 7일 알림 발송 시도 건수 추이(전달 성공/실패 여부는 미추적).")
    ]
    family_link_count: Annotated[int, Field(description="수락 완료된 가족 연결 건수.")]
    withdrawal_trend: Annotated[list[TrendPoint], Field(description="최근 30일 탈퇴 관련 익명 통계 기록 분포(근사치).")]
    ai_worker_status: Annotated[str, Field(description='AI-worker 연결 상태. "ok" 또는 "down".')]
