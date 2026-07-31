import { apiFetch } from "./client";
import type { NoticeCreateRequest, NoticeResult } from "./types";

export const noticeApi = {
  list: () => apiFetch<NoticeResult[]>("/notices"),
  create: (data: NoticeCreateRequest) =>
    apiFetch<NoticeResult>("/notices", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
