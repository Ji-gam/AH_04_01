import { apiFetch, apiFetchRaw } from "./client";
import type { AdminHealthNewsResult, CollectNewsResult, HealthNewsUpdatePayload } from "./types";

export interface AdminUserResult {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
  health_info_consented_at: string | null;
  ai_chat_consented_at: string | null;
  terms_of_service_consented_at: string | null;
  marketing_consented_at: string | null;
}

export interface AdminActionResult {
  id: number;
  actor_user_id: number;
  actor_email: string;
  action: string;
  target: string | null;
  detail: string | null;
  created_at: string;
}

export interface AdminStatsResult {
  total_users: number;
  total_admins: number;
  signup_trend: { date: string; count: number }[];
  consent_summary: {
    terms_of_service: number;
    health_info: number;
    ai_chat: number;
    marketing: number;
  };
  error_count_24h: number;
}

export interface AdminErrorLogResult {
  id: number;
  created_at: string;
  method: string;
  path: string;
  exception_type: string;
  message: string | null;
  status_code: number;
}

export interface AdminOpsStatsResult {
  dau: number;
  wau: number;
  adherence_rate: number | null;
  top_drugs: { name: string; count: number }[];
  // T-LLM-6: 매체별 수집된 건강 뉴스 수. 조회수 추적이 없어서 인기순은 여전히 못 보여준다.
  news_count_by_source: Record<string, number>;
  chat_message_trend: { date: string; count: number }[];
  active_chat_sessions_7d: number;
  notification_count_trend: { date: string; count: number }[];
  family_link_count: number;
  withdrawal_trend: { date: string; count: number }[];
  ai_worker_status: "ok" | "down";
}

export interface AdminNoticeResult {
  id: number;
  kind: "NOTICE" | "MARKETING";
  title: string;
  body: string;
  created_at: string;
}

export interface AdminNoticeUpdatePayload {
  kind?: "NOTICE" | "MARKETING";
  title?: string;
  body?: string;
}

// T-LLM-6 관리자 뉴스 관리. 타입은 frontend/src/api/types.ts에 두고 여기서 재수출한다 —
// 사용자 화면(healthNewsApi)과 같은 백엔드 DTO를 보므로 한 곳에서 관리한다.
export type { AdminHealthNewsResult, CollectNewsResult, HealthNewsUpdatePayload } from "./types";

export const adminApi = {
  listUsers: (search?: string) =>
    apiFetch<AdminUserResult[]>(
      `/admin/users${search ? `?search=${encodeURIComponent(search)}` : ""}`,
    ),
  setAdmin: (userId: number, isAdmin: boolean) =>
    apiFetch<AdminUserResult>(`/admin/users/${userId}/admin`, {
      method: "PATCH",
      body: JSON.stringify({ is_admin: isAdmin }),
    }),
  listActions: () => apiFetch<AdminActionResult[]>("/admin/actions"),
  getStats: (days = 7) => apiFetch<AdminStatsResult>(`/admin/stats?days=${days}`),
  getErrorLogs: () => apiFetch<AdminErrorLogResult[]>("/admin/error-logs"),
  getOpsStats: () => apiFetch<AdminOpsStatsResult>("/admin/ops-stats"),
  listNotices: () => apiFetch<AdminNoticeResult[]>("/admin/notices"),
  updateNotice: (noticeId: number, data: AdminNoticeUpdatePayload) =>
    apiFetch<AdminNoticeResult>(`/admin/notices/${noticeId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteNotice: (noticeId: number) =>
    apiFetchRaw(`/admin/notices/${noticeId}`, { method: "DELETE" }),
  // T-LLM-6: 주기 자동 수집(Celery)이 붙기 전까지 이 버튼이 유일한 수집 트리거다.
  // 여러 번 눌러도 안전하다(이미 저장된 기사는 건너뛴다).
  collectNews: () => apiFetch<CollectNewsResult>("/admin/news/collect", { method: "POST" }),
  listNews: (limit = 100) => apiFetch<AdminHealthNewsResult[]>(`/admin/news?limit=${limit}`),
  updateNews: (newsId: number, data: HealthNewsUpdatePayload) =>
    apiFetch<AdminHealthNewsResult>(`/admin/news/${newsId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteNews: (newsId: number) => apiFetchRaw(`/admin/news/${newsId}`, { method: "DELETE" }),
};
