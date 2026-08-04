"""시연/개발용 주간 리포트 즉시 생성 스크립트.

주간 리포트는 원래 매주 일요일 9시에 push_scheduler가 자동 생성한다
(`app/services/push_scheduler.py`의 `_generate_weekly_reports`). 시연 영상을 찍거나
화면을 확인할 때 일요일까지 기다릴 수는 없어서, 같은 서비스 메서드를 그대로 호출해
지금 시점(오늘 기준 최근 7일)의 리포트를 만들어 주는 스크립트다.

주의: `WeeklyReportService.generate_and_save()`는 그 주(week_start 기준) 리포트가 이미
있으면 새로 만들지 않고 기존 것을 그대로 돌려준다. 그래서 식단/운동 기록을 쌓기 전에
한 번 실행해버리면 "기록된 활동이 없어요" 리포트가 고정된다 - 이때는 `--force`로
그 주 리포트를 지우고 다시 생성하면 된다.

실행 (이미 가입된 계정의 이메일로 지정):
    uv run python -m app.scripts.make_demo_weekly_report --email demo@example.com
    uv run python -m app.scripts.make_demo_weekly_report --email demo@example.com --force --notify

`--notify`를 주면 스케줄러가 보내는 것과 같은 "리포트 도착" 알림을 알림함에도 넣는다
(알림 클릭 → 주간 리포트로 이동하는 딥링크 시연용).

ai_worker가 떠 있으면 AI 요약으로, 없으면 규칙 기반 폴백 요약으로 생성된다(둘 다 정상 동작).
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import delete

from app.core.db.databases import AsyncSessionLocal
from app.models.weekly_reports import WeeklyReport
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.push_service import PushService
from app.services.weekly_report_service import WeeklyReportService


async def _make_report(email: str, force: bool, notify: bool) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository().get_user_by_email(session, email)
        if user is None:
            print(f"[실패] 해당 이메일로 가입된 계정이 없습니다: {email}")
            return

        profile = await ProfileRepository().get_default_profile_for_user(session, user.id)
        if profile is None:
            print(f"[실패] 이 계정에 프로필이 없습니다: {email}")
            return

        if force:
            week_start = date.today() - timedelta(days=6)
            await session.execute(
                delete(WeeklyReport).where(
                    WeeklyReport.profile_id == profile.id, WeeklyReport.week_start_date == week_start
                )
            )
            await session.commit()
            print(f"[안내] 이번 주 기존 리포트를 삭제했습니다 (week_start={week_start}).")

        report = await WeeklyReportService().generate_and_save(session, profile.id)
        print(f"[완료] 주간 리포트 생성됨 (profile_id={profile.id}, id={report.id})")
        print(f"       기간: {report.week_start_date} ~ {report.week_end_date}")
        print("--- 본문 ---")
        print(report.content)

        if notify:
            # push_scheduler._send_weekly_ai_report_if_due()가 보내는 것과 같은 문구/링크를 쓴다
            # - 알림함(notification_logs)에 남아야 "알림 클릭 → 주간 리포트 딥링크" 시연이 된다.
            # 웹푸시 구독이 없어도 PushService의 훅이 알림함에는 항상 저장한다.
            await PushService().send_to_profile(
                session,
                profile.id,
                title="📊 이번 주 리포트가 도착했어요",
                body="더보기 > 주간 리포트에서 확인해보세요.",
                link_url="/weekly-reports",
            )
            print("[완료] 알림함에 '리포트 도착' 알림을 넣었습니다 (딥링크: /weekly-reports)")


def main() -> None:
    # 리포트 본문엔 이모지(💪, 🌟 등)가 들어간다 - Windows 기본 콘솔 인코딩(cp949)에서는
    # print가 UnicodeEncodeError로 죽으므로 stdout을 UTF-8로 다시 연다.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="시연용으로 주간 리포트를 지금 즉시 생성한다.")
    parser.add_argument("--email", required=True, help="리포트를 만들 계정의 이메일")
    parser.add_argument(
        "--force",
        action="store_true",
        help="이번 주 리포트가 이미 있으면 지우고 다시 생성한다(기록을 더 쌓은 뒤 갱신할 때 사용)",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="알림함에 '리포트 도착' 알림도 넣는다(알림 클릭 → 주간 리포트 딥링크 시연용)",
    )
    args = parser.parse_args()
    asyncio.run(_make_report(args.email, args.force, args.notify))


if __name__ == "__main__":
    main()
