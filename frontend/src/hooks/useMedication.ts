import { useState } from "react";
import { apiFetch, apiFetchRaw } from "../api/client";

export interface MedicationSchedule {
  id: number;
  medication_id: number;
  drug_name: string;
  times: string[];
  source_job_id?: string | null;
  // 약 카드 표시용 부가 정보 — 마스터 데이터에 값이 없으면 null (T-NTFY-2)
  form_type?: string | null;
  dosage_guideline?: string | null;
}

export interface RecognitionCandidate {
  drug_name: string;
  match_rate: number;
  drug_code: string;
}

export interface RecognitionJobResult {
  job_id: string;
  status: string;
  source_type: string;
  candidates: RecognitionCandidate[];
  extracted_fields?: {
    dosage?: string;
    times?: string[];
    duration?: string;
    instruction?: string;
    ocr_raw_text?: string;
  } | null;
}

export function useMedication() {
  const [schedules, setSchedules] = useState<MedicationSchedule[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSchedules = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiFetch<MedicationSchedule[]>("/medications");
      setSchedules(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "복약 일정을 가져오는데 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const deleteSchedule = async (scheduleId: number) => {
    setIsLoading(true);
    setError(null);
    try {
      // DELETE는 204 No Content라 apiFetch(항상 res.json() 호출)를 쓰면 파싱 에러가 난다.
      await apiFetchRaw(`/medications/${scheduleId}`, { method: "DELETE" });
      await fetchSchedules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "복약 일정을 삭제하는데 실패했습니다.");
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const createManualSchedule = async (drugCode: string, times: string[]) => {
    setIsLoading(true);
    setError(null);
    try {
      await apiFetch("/medications", {
        method: "POST",
        body: JSON.stringify({ drug_code: drugCode, times }),
      });
      await fetchSchedules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "복약 일정을 등록하는데 실패했습니다.");
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const quickRegister = async (drugName: string, times: string[]) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{
        status: string;
        auto_created: boolean;
        schedule: MedicationSchedule | null;
        candidates: Array<{ drug_code: string; medication_name: string; form_type: string | null }>;
      }>("/medications/quick-register", {
        method: "POST",
        body: JSON.stringify({ drug_name: drugName, times }),
      });
      if (res.status === "registered") {
        await fetchSchedules();
      }
      return res;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "약품 등록에 실패했습니다.");
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const searchMedications = async (query: string) => {
    try {
      return await apiFetch<
        Array<{ id: number; standard_code: string; medication_name: string; form_type: string }>
      >(`/medications/search?query=${encodeURIComponent(query)}`);
    } catch (err) {
      console.error(err);
      return [];
    }
  };

  // FormData 업로드는 client.ts(공유 구역, 수정 금지)의 apiFetch/apiFetchRaw를 거치면
  // Content-Type: application/json이 강제되어 multipart boundary가 빠지는 문제가 있다.
  // client.ts를 고치지 않고 이 훅 안에서만 순수 fetch로 우회 처리한다.
  const uploadJob = async (file: File, sourceType: string): Promise<string> => {
    setIsLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_type", sourceType);

      const getToken = () =>
        (window as unknown as { __getToken?: () => string | null }).__getToken?.() || null;

      const doUpload = () => {
        const token = getToken();
        return fetch("/api/v1/recognition/jobs", {
          method: "POST",
          body: formData,
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      };

      let res = await doUpload();
      if (res.status === 401) {
        const refreshRes = await fetch("/api/v1/auth/token/refresh", { credentials: "include" });
        if (refreshRes.ok) {
          const body = (await refreshRes.json()) as { access_token?: string };
          if (body.access_token) {
            (window as unknown as { __setToken?: (t: string) => void }).__setToken?.(
              body.access_token,
            );
            res = await doUpload();
          }
        }
      }

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "파일 업로드에 실패했습니다.");
      }

      const data = await res.json();
      return data.job_id;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "파일 업로드에 실패했습니다.");
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const getJobStatus = async (jobId: string): Promise<RecognitionJobResult> => {
    return await apiFetch<RecognitionJobResult>(`/recognition/jobs/${jobId}`);
  };

  const confirmJob = async (
    jobId: string,
    selectedDrugCode: string | null,
    confirmedFields: unknown,
  ) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{
        status: string;
        guide_cards: Array<{ title: string; content: string; severity: string }>;
      }>(`/recognition/jobs/${jobId}/confirm`, {
        method: "POST",
        body: JSON.stringify({
          selected_candidate_drug_code: selectedDrugCode,
          confirmed_fields: confirmedFields,
        }),
      });
      await fetchSchedules();
      return res;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "확정 등록에 실패했습니다.");
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  return {
    schedules,
    isLoading,
    error,
    fetchSchedules,
    createManualSchedule,
    quickRegister,
    deleteSchedule,
    searchMedications,
    uploadJob,
    getJobStatus,
    confirmJob,
  };
}
