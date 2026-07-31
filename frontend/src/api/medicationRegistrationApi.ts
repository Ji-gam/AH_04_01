import { apiFetch } from "./client";
import type { MedicationSchedule } from "../hooks/useMedication";

/** (2026-07-30) 백엔드는 이미 통합되어 있다 - `/medications`, `/medications/quick-register`가
 * `target_profile_id`를 선택 필드로 받아서, 그 값이 있으면 가족 몫으로, 없으면 본인 몫으로
 * 등록한다(`app/apis/v1/medication.py`). 근데 프론트는 지금까지 이 두 경로를
 * `useMedication.ts`(본인용)와 `familyMedicationApi.ts`(가족용)가 각자 따로 감싸고 있어서,
 * 요청 모양이 스스로 갈라질 위험이 있었다(실제로 화면 스타일이 미묘하게 계속 어긋났던
 * 원인 중 하나). 여기에 그 "요청을 만드는 부분"만 공용으로 뽑아둔다 - 두 훅/API 파일이
 * 전부 이 함수들을 갖다 쓰면, 요청 모양은 앞으로 하나로만 유지된다.
 *
 * 상태 관리(로딩/에러 state, fetchSchedules 재호출 등)는 각 화면의 성격이 달라 여기 안
 * 넣었다 - 그건 여전히 useMedication.ts/familyMedicationApi.ts 쪽에서 각자 감싸서 쓴다.
 * OCR 업로드(FormData)·confirm 단계는 이번엔 포함하지 않았다 - family 쪽만 별도로
 * `/confirm-for-family`를 쓰는 등 분기가 더 있어서, 검색 기반 등록보다 리스크가 크다.
 * 필요하면 다음 단계로 넘긴다. */

export interface QuickRegisterResult {
  status: string;
  auto_created: boolean;
  schedule: MedicationSchedule | null;
  candidates: Array<{ drug_code: string; medication_name: string; form_type: string | null }>;
}

export interface RegisterByCodeResult {
  id: number;
  drug_name: string;
  times: string[];
}

/** 약품명을 그대로(또는 검색 없이) 등록 - 완전 일치/신규 자동생성이면 즉시 등록되고,
 * 여러 후보와 부분일치하면 candidates만 채워서 돌아온다(자동 등록 안 함).
 * targetProfileId를 넘기면 가족 몫으로, 안 넘기면(undefined) 본인 몫으로 등록된다. */
export function quickRegisterMedication(
  drugName: string,
  times: string[],
  hospitalName?: string | null,
  targetProfileId?: number,
): Promise<QuickRegisterResult> {
  return apiFetch<QuickRegisterResult>("/medications/quick-register", {
    method: "POST",
    body: JSON.stringify({
      drug_name: drugName,
      times,
      hospital_name: hospitalName ?? null,
      ...(targetProfileId !== undefined ? { target_profile_id: targetProfileId } : {}),
    }),
  });
}

/** 검색 결과에서 고른 약품코드로 확정 등록. targetProfileId 규칙은 quickRegisterMedication과 동일. */
export function registerMedicationByCode(
  drugCode: string,
  times: string[],
  hospitalName?: string | null,
  targetProfileId?: number,
): Promise<RegisterByCodeResult> {
  return apiFetch<RegisterByCodeResult>("/medications", {
    method: "POST",
    body: JSON.stringify({
      drug_code: drugCode,
      times,
      hospital_name: hospitalName ?? null,
      ...(targetProfileId !== undefined ? { target_profile_id: targetProfileId } : {}),
    }),
  });
}
