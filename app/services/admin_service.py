from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models.users import User
from app.repositories.error_log_repository import ErrorLogRepository
from app.repositories.health_news_repository import HealthNewsRepository
from app.repositories.notice_repository import NoticeRepository
from app.repositories.ops_stats_repository import OpsStatsRepository
from app.repositories.user_repository import AdminActionRepository, UserRepository
from app.services.health_news_service import CollectResult, HealthNewsService, SummaryResult
from app.services.health_news_source import ALL_SOURCES


class AdminService:
    """관리자 화면(사용자 목록/권한 승격, 감사로그 조회) 전용 서비스. 공지 발송 권한 검증
    자체는 라우터 단의 `get_current_admin_user` 의존성이 맡고, 여기는 그 이후의 실제
    비즈니스 로직 + 감사로그 기록을 담당한다."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        action_repo: AdminActionRepository | None = None,
        error_log_repo: ErrorLogRepository | None = None,
        ops_stats_repo: OpsStatsRepository | None = None,
        notice_repo: NoticeRepository | None = None,
        news_repo: HealthNewsRepository | None = None,
        news_service: HealthNewsService | None = None,
    ) -> None:
        self._user_repo = user_repo or UserRepository()
        self._action_repo = action_repo or AdminActionRepository()
        self._error_log_repo = error_log_repo or ErrorLogRepository()
        self._ops_stats_repo = ops_stats_repo or OpsStatsRepository()
        self._notice_repo = notice_repo or NoticeRepository()
        self._news_repo = news_repo or HealthNewsRepository()
        self._news_service = news_service or HealthNewsService(self._news_repo)

    async def list_users(self, session: AsyncSession, search: str | None) -> list[User]:
        return await self._user_repo.list_users(session, search=search)

    async def set_admin(self, session: AsyncSession, actor: User, target_user_id: int, is_admin: bool) -> User:
        target = await self._user_repo.set_admin(session, target_user_id, is_admin)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 사용자를 찾을 수 없습니다.")

        await self._action_repo.log(
            session,
            actor_user_id=actor.id,
            action="grant_admin" if is_admin else "revoke_admin",
            target=f"user:{target_user_id}",
            detail=f"{actor.email} -> {'grant' if is_admin else 'revoke'} admin for {target.email}",
        )
        await session.commit()
        await session.refresh(target)
        return target

    async def list_actions(self, session: AsyncSession) -> list[dict]:
        actions = await self._action_repo.list_recent(session)
        results = []
        for a in actions:
            actor = await self._user_repo.get_user(session, a.actor_user_id)
            results.append(
                {
                    "id": a.id,
                    "actor_user_id": a.actor_user_id,
                    "actor_email": actor.email if actor else "(삭제된 계정)",
                    "action": a.action,
                    "target": a.target,
                    "detail": a.detail,
                    "created_at": a.created_at,
                }
            )
        return results

    async def get_stats(self, session: AsyncSession, days: int = 7) -> dict:
        """(관리자 대시보드) 전체 가입자/관리자 수, 최근 N일 가입자 추이, 항목별
        동의자 수, 최근 24시간 오류 건수를 한 번에 모아서 돌려준다."""
        total_users = await self._user_repo.count_all(session)
        total_admins = await self._user_repo.count_admins(session)
        trend = await self._user_repo.signup_trend(session, days=days)
        consent_summary = {
            "terms_of_service": await self._user_repo.count_consented(session, User.terms_of_service_consented_at),
            "health_info": await self._user_repo.count_consented(session, User.health_info_consented_at),
            "ai_chat": await self._user_repo.count_consented(session, User.ai_chat_consented_at),
            "marketing": await self._user_repo.count_consented(session, User.marketing_consented_at),
        }
        since_24h = datetime.now(tz=config.TIMEZONE) - timedelta(hours=24)
        error_count_24h = await self._error_log_repo.count_since(session, since_24h)
        return {
            "total_users": total_users,
            "total_admins": total_admins,
            "signup_trend": [{"date": d, "count": c} for d, c in trend],
            "consent_summary": consent_summary,
            "error_count_24h": error_count_24h,
        }

    async def list_error_logs(self, session: AsyncSession) -> list:
        return await self._error_log_repo.list_recent(session)

    # ── 공지 관리 (목록/수정/삭제) ──
    async def list_notices_admin(self, session: AsyncSession):  # noqa: ANN201
        return await self._notice_repo.list_all(session)

    async def update_notice(self, session: AsyncSession, actor: User, notice_id: int, data):  # noqa: ANN001, ANN201
        from app.models.notice import NoticeKind

        notice = await self._notice_repo.get_by_id(session, notice_id)
        if notice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 공지를 찾을 수 없습니다.")
        updated = await self._notice_repo.update(
            session,
            notice,
            kind=NoticeKind(data.kind) if data.kind else None,
            title=data.title,
            body=data.body,
        )
        await self._action_repo.log(
            session,
            actor_user_id=actor.id,
            action="update_notice",
            target=f"notice:{notice_id}",
            detail=f"{actor.email} updated notice '{updated.title}'",
        )
        await session.commit()
        return updated

    async def delete_notice(self, session: AsyncSession, actor: User, notice_id: int) -> None:
        notice = await self._notice_repo.get_by_id(session, notice_id)
        if notice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 공지를 찾을 수 없습니다.")
        title = notice.title
        await self._notice_repo.delete(session, notice)
        await self._action_repo.log(
            session,
            actor_user_id=actor.id,
            action="delete_notice",
            target=f"notice:{notice_id}",
            detail=f"{actor.email} deleted notice '{title}'",
        )
        await session.commit()

    # ── 건강 뉴스 관리 (T-LLM-6: 수집 트리거 / 목록 / 수정 / 삭제) ──
    async def collect_health_news(self, session: AsyncSession, actor: User) -> tuple[CollectResult, SummaryResult]:
        """[뉴스 수집] 버튼. 주기 자동 수집(Celery)이 붙기 전까지 이게 유일한 트리거다.

        수집과 카드요약을 나눠 부르는 이유는 `HealthNewsService` 주석 참고 - OpenAI가 흔들려도
        기사 수집은 남아야 한다. LLM 비용이 드는 행위이므로 감사로그에 남긴다."""
        collected = await self._news_service.collect_all(session)
        summarized = await self._news_service.generate_missing_card_summaries(session)
        await self._action_repo.log(
            session,
            actor_user_id=actor.id,
            action="collect_health_news",
            target=f"health_news:{','.join(s.code for s in ALL_SOURCES)}",
            detail=(
                f"{actor.email} collected {collected.created} new articles "
                f"(fetched={collected.fetched}, excluded={collected.excluded}, skipped={collected.skipped}, "
                f"over_limit={collected.over_limit}, unreadable={collected.unreadable}), "
                f"generated {summarized.generated} card summaries (failed={summarized.failed})"
                # 실패 원인을 감사로그에도 남긴다 - 관리자 화면의 활동 로그만 보고도 원인을
                # 알 수 있어야 한다(그 순간의 응답 문구는 화면을 새로 고치면 사라진다).
                + (f" - 수집: {collected.first_error}" if collected.first_error else "")
                + (f" - 요약: {summarized.first_error}" if summarized.first_error else "")
            ),
        )
        await session.commit()
        return collected, summarized

    async def regenerate_card_summaries(self, session: AsyncSession, actor: User) -> SummaryResult:
        """[카드요약 다시 만들기] 버튼. 프롬프트나 글자 수 제한을 손질한 뒤 기존 기사에도
        새 기준을 적용할 때 쓴다. 기사 수만큼 LLM을 부르는 비싼 행위라 감사로그에 남긴다."""
        summarized = await self._news_service.regenerate_card_summaries(session)
        await self._action_repo.log(
            session,
            actor_user_id=actor.id,
            action="regenerate_card_summaries",
            target=f"health_news:{','.join(s.code for s in ALL_SOURCES)}",
            detail=(
                f"{actor.email} regenerated {summarized.generated} of {summarized.pending} card summaries "
                f"(failed={summarized.failed})" + (f" - {summarized.first_error}" if summarized.first_error else "")
            ),
        )
        await session.commit()
        return summarized

    async def list_health_news_admin(self, session: AsyncSession, limit: int = 100):  # noqa: ANN201
        return await self._news_repo.list_feed(session, limit=limit)

    async def update_health_news(self, session: AsyncSession, actor: User, news_id: int, data):  # noqa: ANN001, ANN201
        news = await self._news_repo.get_by_id(session, news_id)
        if news is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 기사를 찾을 수 없습니다.")
        updated = await self._news_repo.update_article(
            session,
            news,
            title=data.title if data.title is not None else news.title,
            body_text=data.body_text if data.body_text is not None else news.body_text,
        )
        await self._action_repo.log(
            session,
            actor_user_id=actor.id,
            action="update_health_news",
            target=f"health_news:{news_id}",
            detail=f"{actor.email} updated health news '{updated.title}'",
        )
        await session.commit()
        return updated

    async def delete_health_news(self, session: AsyncSession, actor: User, news_id: int) -> None:
        """AI 요약이 기사를 왜곡했거나 건강정보로 부적절한 기사를 내리는 경로.
        승인 게이트를 두지 않기로 했으므로(계획 문서 3-3절) 이게 유일한 교정 수단이다."""
        news = await self._news_repo.get_by_id(session, news_id)
        if news is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 기사를 찾을 수 없습니다.")
        title = news.title
        await self._news_repo.delete(session, news)
        await self._action_repo.log(
            session,
            actor_user_id=actor.id,
            action="delete_health_news",
            target=f"health_news:{news_id}",
            detail=f"{actor.email} deleted health news '{title}'",
        )
        await session.commit()

    async def get_ops_stats(self, session: AsyncSession) -> dict:
        """(관리자 대시보드 "운영 현황" 탭) DAU/WAU, 근사 복약 순응도, 상위 약품(소수
        인원 그룹 제외), 콘텐츠/챗봇/알림/가족연결/탈퇴 추이, AI-worker 상태를 모아서
        돌려준다. 전부 익명 집계이고, 상위 약품은 등록자 3명 미만이면 결과에서 뺀다."""
        repo = self._ops_stats_repo
        now = datetime.now(tz=config.TIMEZONE)
        dau = await repo.active_user_count(session, now - timedelta(hours=24))
        wau = await repo.active_user_count(session, now - timedelta(days=7))
        adherence = await repo.adherence_rate(session, days=7)
        top_drugs = await repo.top_drugs(session, min_count=3, limit=10)
        news_by_source = await repo.news_count_by_source(session)
        chat_trend = await repo.chat_usage_trend(session, days=7)
        active_chat_sessions = await repo.active_chat_session_count(session, now - timedelta(days=7))
        notification_trend = await repo.notification_count_trend(session, days=7)
        family_links = await repo.family_link_count(session)
        withdrawal_trend = await repo.withdrawal_trend(session, days=30)
        ai_worker_status = await repo.ai_worker_status()

        return {
            "dau": dau,
            "wau": wau,
            "adherence_rate": adherence,
            "top_drugs": [{"name": n, "count": c} for n, c in top_drugs],
            "news_count_by_source": news_by_source,
            "chat_message_trend": [{"date": d, "count": c} for d, c in chat_trend],
            "active_chat_sessions_7d": active_chat_sessions,
            "notification_count_trend": [{"date": d, "count": c} for d, c in notification_trend],
            "family_link_count": family_links,
            "withdrawal_trend": [{"date": d, "count": c} for d, c in withdrawal_trend],
            "ai_worker_status": ai_worker_status,
        }
