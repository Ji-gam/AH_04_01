import { apiFetch, apiFetchRaw } from "./client";

export interface FamilyLinkItem {
  link_id: number;
  profile_id: number;
  name: string;
  relation_label: string;
  status: "PENDING" | "ACCEPTED";
  created_at: string;
}

export interface FamilyMembersResult {
  as_guardian_accepted: FamilyLinkItem[]; // 내가 관리하는(수락된) 가족
  as_guardian_pending: FamilyLinkItem[]; // 내가 보냈지만 아직 대기중인 요청
  as_member_accepted: FamilyLinkItem[]; // 나를 관리하고 있는 보호자
  as_member_pending: FamilyLinkItem[]; // 내가 받은, 아직 응답 안 한 요청 - 수락/거절 대상
}

export interface FamilyInviteCode {
  code: string;
  relation_label: string;
  expires_at: string;
}

export const familyApi = {
  list: () => apiFetch<FamilyMembersResult>("/family/members"),
  requestLink: (email: string, relationLabel: string) =>
    apiFetch<FamilyLinkItem>("/family/link", {
      method: "POST",
      body: JSON.stringify({ email, relation_label: relationLabel }),
    }),
  accept: (linkId: number) =>
    apiFetch<FamilyLinkItem>(`/family/link/${linkId}/accept`, { method: "POST" }),
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  reject: async (linkId: number) => {
    await apiFetchRaw(`/family/link/${linkId}/reject`, { method: "POST" });
  },
  unlink: async (linkId: number) => {
    await apiFetchRaw(`/family/link/${linkId}`, { method: "DELETE" });
  },
  // 이메일을 모르거나(카카오 임시 가입 등) 이메일 방식이 번거로울 때 쓰는 대안 경로.
  createInviteCode: (relationLabel: string) =>
    apiFetch<FamilyInviteCode>("/family/invite-code", {
      method: "POST",
      body: JSON.stringify({ relation_label: relationLabel }),
    }),
  redeemInviteCode: (code: string) =>
    apiFetch<FamilyLinkItem>("/family/invite-code/redeem", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
};
