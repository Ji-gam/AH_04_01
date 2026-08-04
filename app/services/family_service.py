from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.family import (
    FamilyInviteCodeCreateRequest,
    FamilyInviteCodeResult,
    FamilyLinkCreateRequest,
    FamilyLinkResult,
    FamilyMembersResult,
)
from app.models.family_link import FamilyLink, FamilyLinkStatus
from app.models.profiles import Profile
from app.repositories.family_invite_code_repository import FamilyInviteCodeRepository
from app.repositories.family_repository import FamilyRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository


class FamilyService:
    def __init__(self) -> None:
        self._family_repo = FamilyRepository()
        self._invite_repo = FamilyInviteCodeRepository()
        self._profile_repo = ProfileRepository()
        self._user_repo = UserRepository()

    async def request_link(
        self, session: AsyncSession, guardian_profile_id: int, req: FamilyLinkCreateRequest
    ) -> FamilyLinkResult:
        """이메일로 가족 구성원을 찾아 연결 "요청"을 보낸다 (PENDING). 상대방이 수락해야
        실제 보호자 권한(약 등록 등)이 생긴다 - 요청만으로는 아무 권한도 생기지 않는다."""
        target_user = await self._user_repo.get_user_by_email(session, req.email)
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 이메일로 가입된 계정을 찾을 수 없습니다. 가족분이 먼저 회원가입을 해주셔야 해요.",
            )

        target_profile = await self._profile_repo.get_default_profile_for_user(session, target_user.id)
        if target_profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 계정의 프로필을 찾을 수 없습니다.")

        if target_profile.id == guardian_profile_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="본인 자신은 가족으로 등록할 수 없습니다."
            )

        existing = await self._family_repo.get_link(session, guardian_profile_id, target_profile.id)
        if existing is not None:
            detail = (
                "이미 연결된 가족 구성원입니다."
                if existing.status.value == "ACCEPTED"
                else "이미 응답 대기중인 요청이 있습니다."
            )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

        link = await self._family_repo.create_link(session, guardian_profile_id, target_profile.id, req.relation_label)
        return await self._to_result(session, link, other_profile=target_profile)

    async def accept_request(self, session: AsyncSession, member_profile_id: int, link_id: int) -> FamilyLinkResult:
        """받은 요청을 수락한다 - 요청받은 사람(member) 본인만 할 수 있다."""
        link = await self._family_repo.get_link_by_id(session, link_id)
        if link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="연결 요청을 찾을 수 없습니다.")
        if link.member_profile_id != member_profile_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인에게 온 요청만 수락할 수 있습니다.")
        link = await self._family_repo.accept(session, link)
        guardian_profile = await self._profile_repo.get_profile(session, link.guardian_profile_id)
        return await self._to_result(session, link, other_profile=guardian_profile)

    async def reject_request(self, session: AsyncSession, member_profile_id: int, link_id: int) -> None:
        """받은 요청을 거절한다 - 요청받은 사람(member) 본인만 할 수 있다. row 자체를 지워서
        나중에 다시 요청받을 수 있게 한다(uq_family_links_pair 제약 때문에 남겨두면 재요청 불가)."""
        link = await self._family_repo.get_link_by_id(session, link_id)
        if link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="연결 요청을 찾을 수 없습니다.")
        if link.member_profile_id != member_profile_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인에게 온 요청만 거절할 수 있습니다.")
        await self._family_repo.delete_link(session, link)

    async def list_members(self, session: AsyncSession, profile_id: int) -> FamilyMembersResult:
        guardian_links = await self._family_repo.list_as_guardian(session, profile_id)
        member_links = await self._family_repo.list_as_member(session, profile_id)

        as_guardian_accepted: list[FamilyLinkResult] = []
        as_guardian_pending: list[FamilyLinkResult] = []
        for link in guardian_links:
            other = await self._profile_repo.get_profile(session, link.member_profile_id)
            if other is None:
                continue
            item = await self._to_result(session, link, other_profile=other)
            (as_guardian_accepted if link.status == FamilyLinkStatus.ACCEPTED else as_guardian_pending).append(item)

        as_member_accepted: list[FamilyLinkResult] = []
        as_member_pending: list[FamilyLinkResult] = []
        for link in member_links:
            other = await self._profile_repo.get_profile(session, link.guardian_profile_id)
            if other is None:
                continue
            item = await self._to_result(session, link, other_profile=other)
            (as_member_accepted if link.status == FamilyLinkStatus.ACCEPTED else as_member_pending).append(item)

        return FamilyMembersResult(
            as_guardian_accepted=as_guardian_accepted,
            as_guardian_pending=as_guardian_pending,
            as_member_accepted=as_member_accepted,
            as_member_pending=as_member_pending,
        )

    async def delete_link(self, session: AsyncSession, requester_profile_id: int, link_id: int) -> None:
        """연결 해제.

        [2026-08-03] 원래는 보호자만 해제할 수 있었다 - 한 번 수락된 관계는 피보호자
        본인이 스스로 끊을 방법이 없어, "본인 건강정보를 보는 보호자를 본인이 통제할
        수 없는" 상태였다(정보주체 자기결정권 문제). ACCEPTED 상태는 양쪽 다 해제
        가능하도록 변경.

        PENDING(보호자가 보낸 요청이 아직 대기 중)은 기존대로 보호자만 취소 가능 -
        피보호자 쪽은 이 시점엔 `reject_request`로 거절하는 것이 맞는 경로라 여기서는
        건드리지 않는다.
        """
        link = await self._family_repo.get_link_by_id(session, link_id)
        if link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="연결 정보를 찾을 수 없습니다.")

        is_guardian = link.guardian_profile_id == requester_profile_id
        is_member = link.member_profile_id == requester_profile_id

        if link.status == FamilyLinkStatus.PENDING:
            if not is_guardian:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="대기중인 요청은 보낸 사람만 취소할 수 있습니다.",
                )
        elif not (is_guardian or is_member):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인이 속한 연결만 해제할 수 있습니다.")

        await self._family_repo.delete_link(session, link)

    async def create_invite_code(
        self, session: AsyncSession, guardian_profile_id: int, req: FamilyInviteCodeCreateRequest
    ) -> FamilyInviteCodeResult:
        """이메일을 모르거나(예: 카카오 임시 이메일 계정) 이메일 방식이 번거로울 때 쓰는 대안
        경로. 코드를 발급하고, 그 코드를 아는 사람이 입력하는 즉시 연결된다(승인 절차 없음)."""
        invite = await self._invite_repo.create(session, guardian_profile_id, req.relation_label)
        return FamilyInviteCodeResult(
            code=invite.code, relation_label=invite.relation_label, expires_at=invite.expires_at
        )

    async def redeem_invite_code(self, session: AsyncSession, member_profile_id: int, code: str) -> FamilyLinkResult:
        """초대코드를 입력해 즉시 연결한다. 코드를 전달받았다는 것 자체가 이미 상대방의 동의로
        간주하므로, 이메일 요청 방식과 달리 PENDING 승인 절차 없이 바로 ACCEPTED가 된다."""
        invite = await self._invite_repo.get_by_code(session, code.strip().upper())
        now = datetime.now().astimezone()
        if invite is None or not invite.is_valid(now):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="유효하지 않거나 만료된 초대코드입니다.")

        if invite.guardian_profile_id == member_profile_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="본인이 발급한 코드는 본인이 사용할 수 없습니다."
            )

        existing = await self._family_repo.get_link(session, invite.guardian_profile_id, member_profile_id)
        if existing is not None and existing.status == FamilyLinkStatus.ACCEPTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 연결된 가족 구성원입니다.")

        if existing is not None:
            # 이메일 요청으로 이미 PENDING 상태였던 경우 - 새로 만들지 않고 그걸 바로 수락 처리한다
            # (guardian_profile_id + member_profile_id 조합에 유니크 제약이 있어서 중복 생성 불가).
            link = await self._family_repo.accept(session, existing)
        else:
            link = await self._family_repo.create_link(
                session, invite.guardian_profile_id, member_profile_id, invite.relation_label
            )
            link = await self._family_repo.accept(session, link)

        await self._invite_repo.mark_used(session, invite)
        guardian_profile = await self._profile_repo.get_profile(session, invite.guardian_profile_id)
        return await self._to_result(session, link, other_profile=guardian_profile)

    async def _to_result(
        self, session: AsyncSession, link: FamilyLink, other_profile: Profile | None
    ) -> FamilyLinkResult:
        if other_profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="상대방 프로필을 찾을 수 없습니다.")
        return FamilyLinkResult(
            link_id=link.id,
            profile_id=other_profile.id,
            name=other_profile.name,
            relation_label=link.relation_label,
            status=link.status.value,
            created_at=link.created_at,
        )
