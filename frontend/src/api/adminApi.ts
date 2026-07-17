import { apiFetch, getAccessToken, tryRefreshAccessToken } from "./client";
import type {
  AdminChatSessionListItem,
  ChatMessageResponse,
  IngestCsvResult,
  IngestPapersResult,
  IngestStatusResult,
} from "./types";

// CSV 업로드는 FormData라 apiFetch를 거치면 Content-Type: application/json이 강제되어
// multipart boundary가 깨진다(useMedication.ts의 uploadJob과 같은 이유로 순수 fetch 사용).
// 재업로드가 곧 그 파일 소스의 upsert라 force 파라미터는 없다(전체 리셋은 resetDurCollection).
async function uploadCsv(file: File): Promise<IngestCsvResult> {
  const formData = new FormData();
  formData.append("file", file);

  const doUpload = () => {
    const token = getAccessToken();
    return fetch(`/api/v1/admin/rag/ingest/csv`, {
      method: "POST",
      body: formData,
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  };

  let res = await doUpload();
  if (res.status === 401 && (await tryRefreshAccessToken())) {
    res = await doUpload();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "CSV 업로드에 실패했습니다.");
  }
  return res.json();
}

export const adminApi = {
  listChatSessions: (limit = 50, offset = 0) =>
    apiFetch<AdminChatSessionListItem[]>(`/admin/chat/sessions?limit=${limit}&offset=${offset}`),

  getChatSessionMessages: (sessionId: number) =>
    apiFetch<ChatMessageResponse[]>(`/admin/chat/sessions/${sessionId}/messages`),

  uploadCsv,

  triggerPaperIngest: (categories?: string[], retmaxPerCategory?: number) =>
    apiFetch<IngestPapersResult>("/admin/rag/ingest/papers", {
      method: "POST",
      body: JSON.stringify({
        categories: categories ?? null,
        retmax_per_category: retmaxPerCategory ?? null,
      }),
    }),

  resetPaperCollection: () =>
    apiFetch<{ status: string }>("/admin/rag/ingest/papers/reset", { method: "POST" }),

  resetDurCollection: () =>
    apiFetch<{ status: string }>("/admin/rag/ingest/csv/reset", { method: "POST" }),

  getIngestStatus: () => apiFetch<IngestStatusResult>("/admin/rag/ingest/status"),
};
