import { useState } from "react";

import { apiFetch, apiFetchRaw, getAccessToken, tryRefreshAccessToken } from "../api/client";

export interface MedicationSchedule {
  id: number;
  medication_id: number;
  drug_name: string;
  times: string[];
  source_job_id?: string | null;
  // 약 카드 표시용 부가 정보 — 마스터 데이터에 값이 없으면 null (T-NTFY-2)
  form_type?: string | null;
  dosage_guideline?: string | null;
  hospital_name?: string | null;
}

export interface InteractionWarning {
  drug_a_name: string;
  drug_b_name: string;
  description: string;
  disclaimer: string;
}

export interface InteractionCheckResult {
  warnings: InteractionWarning[];
  checked_count: number;
}

export interface FoodItem {
  name: string;
  detail: string;
}

export interface GuideCard {
  title: string;
  content: string;
  severity: string;
  disclaimer: string;
  // (T-DOC-4) 규칙 기반 추출로 음식명이 식별되면 채워진다. 없으면 undefined — 이 경우
  // 프론트는 기존처럼 content 전체 텍스트를 그대로 보여준다.
  food_items?: FoodItem[] | null;
}

export interface FoodInteractionCheckResult {
  guide_cards: GuideCard[];
  checked_count: number;
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

  const createManualSchedule = async (
    drugCode: string,
    times: string[],
    hospitalName?: string | null,
  ) => {
    setIsLoading(true);
    setError(null);
    try {
      await apiFetch("/medications", {
        method: "POST",
        body: JSON.stringify({ drug_code: drugCode, times, hospital_name: hospitalName ?? null }),
      });
      await fetchSchedules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "복약 일정을 등록하는데 실패했습니다.");
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const quickRegister = async (drugName: string, times: string[], hospitalName?: string | null) => {
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
        body: JSON.stringify({ drug_name: drugName, times, hospital_name: hospitalName ?? null }),
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

  const checkInteractions = async (): Promise<InteractionCheckResult> => {
    return await apiFetch<InteractionCheckResult>("/medications/interactions");
  };

  const checkFoodInteractions = async (): Promise<FoodInteractionCheckResult> => {
    return await apiFetch<FoodInteractionCheckResult>("/medications/food-interactions");
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

  // FormData 업로드는 client.ts의 apiFetch/apiFetchRaw를 거치면
  // Content-Type: application/json이 강제되어 multipart boundary가 빠지는 문제가 있다.
  // 그래서 이 훅 안에서 순수 fetch로 처리하되, 토큰은 client.ts가 export하는
  // getAccessToken/tryRefreshAccessToken을 공유해서 프로덕션에서도 인증이 붙게 한다.
  const uploadJob = async (file: File, sourceType: string): Promise<string> => {
    setIsLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_type", sourceType);

      const doUpload = () => {
        const token = getAccessToken();
        return fetch("/api/v1/recognition/jobs", {
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
    checkInteractions,
    checkFoodInteractions,
    uploadJob,
    getJobStatus,
    confirmJob,
  };
}
