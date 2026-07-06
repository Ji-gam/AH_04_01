// src/api/endpoints/supportGroup.ts
import { apiClient } from "../client";
import type { GroupCreateResponse, GroupMemberResponse } from "../../types";

export const supportGroupApi = {
  create: async (group_name: string): Promise<GroupCreateResponse> => {
    const res = await apiClient.post("/support-groups", { group_name });
    return res.data;
  },
  join: (invite_code: string) => apiClient.post("/support-groups/join", { invite_code }),
  getMembers: async (groupId: number): Promise<GroupMemberResponse[]> => {
    const res = await apiClient.get(`/support-groups/${groupId}/members`);
    return res.data;
  },
};
