import { apiFetch } from "./client";

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
  content_count_by_category: Record<string, number>;
  chat_message_trend: { date: string; count: number }[];
  active_chat_sessions_7d: number;
  notification_count_trend: { date: string; count: number }[];
  family_link_count: number;
  withdrawal_trend: { date: string; count: number }[];
  ai_worker_status: "ok" | "down";
}

export const adminApi = {
  listUsers: (search?: string) =>
    apiFetch<AdminUserResult[]>(`/admin/users${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  setAdmin: (userId: number, isAdmin: boolean) =>
    apiFetch<AdminUserResult>(`/admin/users/${userId}/admin`, {
      method: "PATCH",
      body: JSON.stringify({ is_admin: isAdmin }),
    }),
  listActions: () => apiFetch<AdminActionResult[]>("/admin/actions"),
  getStats: (days = 7) => apiFetch<AdminStatsResult>(`/admin/stats?days=${days}`),
  getErrorLogs: () => apiFetch<AdminErrorLogResult[]>("/admin/error-logs"),
  getOpsStats: () => apiFetch<AdminOpsStatsResult>("/admin/ops-stats"),
};
