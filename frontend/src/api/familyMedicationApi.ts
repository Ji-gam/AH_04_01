import { apiFetch, apiFetchRaw, getAccessToken, tryRefreshAccessToken } from "./client";

// 이 파일은 "가족관리 > 약 등록" 전용이다. 기존 useMedication.ts(본인 몫 등록)는 다른 조원이
// 계속 다듬고 있어서(OCR 마스터 DB 매칭 개선 등) 병합 충돌을 피하려고 완전히 새 파일로
// 분리했다 - 아래 함수들은 useMedication.ts의 동명 함수와 로직이 겹치는 부분이 있는데
// 의도적인 중복이다. 백엔드도 confirm-for-family는 별도 엔드포인트로 분리해뒀다.

export interface MedicationSearchResult {
  id: number;
  standard_code: string;
  medication_name: string;
  form_type: string | null;
}

export interface RecognitionCandidate {
  drug_name: string;
  match_rate: number;
  drug_code: string;
}

export interface RecognitionJobStatus {
  job_id: string;
  status: "pending" | "processing" | "done" | "failed";
  source_type: string;
  candidates: RecognitionCandidate[];
  extracted_fields: { times?: string[]; ocr_raw_text?: string } | null;
}

export interface FamilyMedicationScheduleItem {
  id: number;
  medication_id: number;
  drug_name: string;
  times: string[];
  source_job_id?: string | null;
  form_type?: string | null;
  dosage_guideline?: string | null;
  hospital_name?: string | null;
}

export interface FamilyInteractionWarning {
  drug_a_name: string;
  drug_b_name: string;
  description: string;
  disclaimer: string;
}

export interface FamilyInteractionCheckResult {
  warnings: FamilyInteractionWarning[];
  checked_count: number;
}

export interface FamilyFoodItem {
  name: string;
  detail: string;
  polarity: "avoid" | "recommend";
}

export interface FamilyGuideCard {
  title: string;
  content: string;
  severity: string;
  disclaimer: string;
  food_items: FamilyFoodItem[] | null;
}

export interface FamilyFoodInteractionCheckResult {
  guide_cards: FamilyGuideCard[];
  checked_count: number;
}

export const familyMedicationApi = {
  search: (query: string) =>
    apiFetch<MedicationSearchResult[]>(`/medications/search?query=${encodeURIComponent(query)}`),

  // 가족 몫 등록(검색 기반) - 이미 있는 /medications(POST)가 target_profile_id를 지원해서
  // 새 엔드포인트 없이 그대로 재사용한다.
  registerForFamily: (
    targetProfileId: number,
    drugCode: string,
    times: string[],
    hospitalName?: string | null,
  ) =>
    apiFetch<{ id: number; drug_name: string; times: string[] }>("/medications", {
      method: "POST",
      body: JSON.stringify({
        drug_code: drugCode,
        times,
        hospital_name: hospitalName ?? null,
        target_profile_id: targetProfileId,
      }),
    }),

  // 사진(처방전) 업로드 - FormData라 apiFetch(Content-Type: application/json 강제)를 못 쓰고
  // 순수 fetch로 처리한다(useMedication.ts의 uploadJob과 같은 이유의 같은 패턴).
  uploadJob: async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("source_type", "prescription");

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
  },

  // 인식 결과 조회는 읽기전용 기존 API를 그대로 재사용(누구 몫으로 등록할지와 무관한 단계라
  // 새로 안 만들어도 됨).
  getJobStatus: (jobId: string) => apiFetch<RecognitionJobStatus>(`/recognition/jobs/${jobId}`),

  // 가족 몫 확정등록 - 백엔드의 새 엔드포인트(confirm-for-family) 호출.
  confirmForFamily: (jobId: string, targetProfileId: number, drugCode: string, times: string[]) =>
    apiFetch<{ status: string }>(`/recognition/jobs/${jobId}/confirm-for-family`, {
      method: "POST",
      body: JSON.stringify({
        target_profile_id: targetProfileId,
        selected_candidate_drug_code: drugCode,
        confirmed_fields: { times },
      }),
    }),

  // 트랙커/복약알림 가족 화면에서 쓰는 조회용 함수들 - 전부 보호자 권한 검증을 거친다.
  listForFamily: (targetProfileId: number) =>
    apiFetch<FamilyMedicationScheduleItem[]>(`/medications/family/${targetProfileId}`),
  checkInteractionsForFamily: (targetProfileId: number) =>
    apiFetch<FamilyInteractionCheckResult>(`/medications/interactions/family/${targetProfileId}`),
  checkFoodInteractionsForFamily: (targetProfileId: number) =>
    apiFetch<FamilyFoodInteractionCheckResult>(
      `/medications/food-interactions/family/${targetProfileId}`,
    ),

  // 204 No Content라 apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  deleteForFamily: async (scheduleId: number) => {
    await apiFetchRaw(`/medications/${scheduleId}/for-family`, { method: "DELETE" });
  },
};
