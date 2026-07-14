import { apiFetch } from "./client";
import type {
  DurBasicScreeningResponse,
  DurIngredientScreeningResponse,
  DurInteractionScreeningResponse,
} from "./types";

/** T-MED-14 DUR 스크리닝. 3개 엔드포인트 모두 같은 형태의 바디({ drug_names: string[] })를 받는다. */
export const durApi = {
  screenBasic: (drugNames: string[]) =>
    apiFetch<DurBasicScreeningResponse>("/dur/screening/basic", {
      method: "POST",
      body: JSON.stringify({ drug_names: drugNames }),
    }),
  screenInteraction: (drugNames: string[]) =>
    apiFetch<DurInteractionScreeningResponse>("/dur/screening/interaction", {
      method: "POST",
      body: JSON.stringify({ drug_names: drugNames }),
    }),
  screenIngredient: (drugNames: string[]) =>
    apiFetch<DurIngredientScreeningResponse>("/dur/screening/ingredient", {
      method: "POST",
      body: JSON.stringify({ drug_names: drugNames }),
    }),
};
