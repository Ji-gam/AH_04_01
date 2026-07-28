"""최초 관리자 지정용 CLI 스크립트 (서버에서 직접 실행 전용, 공개 API 경로 없음).

관리자 권한은 새로운 공개 가입 경로(초대코드 등)를 만들지 않고, "기존 관리자가
화면(더보기 > 관리자)에서 다른 사용자를 승격"하는 방식으로만 늘어난다 - 근데
맨 처음 관리자가 0명인 시점엔 그 화면 자체를 아무도 못 연다("닭이 먼저냐
달걀이 먼저냐" 문제). 이 스크립트가 그 첫 문을 여는 역할 - 서버(SSH/docker exec)
접근 권한이 있는 사람만 실행 가능하므로, 이미 신뢰된 인프라 접근 권한을 그대로
활용하는 것뿐이지 새로운 취약점이 아니다.

실행 (이미 가입된 계정만 대상 - 이메일로 지정):
    uv run python -m app.scripts.promote_admin --email jangnim@example.com

실행해도 이미 관리자면 조용히 넘어간다(여러 번 실행해도 안전).
"""

import argparse
import asyncio

from app.core.db.databases import AsyncSessionLocal
from app.repositories.user_repository import UserRepository


async def _promote(email: str) -> None:
    async with AsyncSessionLocal() as session:
        repo = UserRepository()
        user = await repo.get_user_by_email(session, email)
        if user is None:
            print(f"[실패] 해당 이메일로 가입된 계정이 없습니다: {email}")
            print("먼저 일반 회원가입을 완료한 뒤 이 스크립트를 실행해주세요.")
            return
        if user.is_admin:
            print(f"[안내] 이미 관리자입니다: {email}")
            return
        user.is_admin = True
        await session.commit()
        print(f"[완료] 관리자로 지정했습니다: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="이미 가입된 계정을 관리자로 지정한다.")
    parser.add_argument("--email", required=True, help="관리자로 지정할 계정의 이메일")
    args = parser.parse_args()
    asyncio.run(_promote(args.email))


if __name__ == "__main__":
    main()
