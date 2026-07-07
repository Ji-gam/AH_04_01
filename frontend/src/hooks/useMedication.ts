import { useState } from "react";
import { apiFetch, apiFetchRaw } from "../api/client";

export interface MedicationSchedule {
  id: number;
  medication_id: number;
  drug_name: string;
  times: string[];
  source_job_id?: string | null;
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

  const searchMedications = async (query: string) => {
    try {
      return await apiFetch<Array<{ id: number; standard_code: string; medication_name: string; form_type: string }>>(
        `/medications/search?query=${encodeURIComponent(query)}`
      );
    } catch (err) {
      console.error(err);
      return [];
    }
  };

  const uploadJob = async (file: File, sourceType: string): Promise<string> => {
    setIsLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_type", sourceType);

      // apiFetchRaw를 사용하여 multipart/form-data 헤더 적용 (Content-Type 자동 설정되도록 헤더 비움)
      const res = await apiFetchRaw("/recognition/jobs", {
        method: "POST",
        body: formData,
        headers: {}, // Content-Type을 null로 덮어쓰기하여 브라우저가 바운더리 포함 자동지정하도록 유도
      });
      
      // Content-Type 비우기 위해 아래처럼 raw 헤더 오버라이드
      // apiFetchRaw 내부에서 Content-Type이 "application/json"으로 강제 지정될 수 있으므로 직접 fetch 사용
      const token = (window as unknown as { __getToken?: () => string | null }).__getToken?.() || "";
      const rawRes = await fetch("/api/v1/recognition/jobs", {
        method: "POST",
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      
      if (!rawRes.ok) {
        const body = await rawRes.json().catch(() => ({}));
        throw new Error(body.detail || "작업 업로드 실패");
      }
      
      const data = await rawRes.json();
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

  const confirmJob = async (jobId: string, selectedDrugCode: string | null, confirmedFields: unknown) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ status: string; guide_cards: Array<{ title: string; content: string; severity: string }> }>(
        `/recognition/jobs/${jobId}/confirm`,
        {
          method: "POST",
          body: JSON.stringify({
            selected_candidate_drug_code: selectedDrugCode,
            confirmed_fields: confirmedFields,
          }),
        }
      );
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
    searchMedications,
    uploadJob,
    getJobStatus,
    confirmJob,
  };
}
