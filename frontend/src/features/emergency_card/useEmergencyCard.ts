// src/features/emergency_card/useEmergencyCard.ts
// schedule/useSchedules.ts 를 그대로 복사해서 이름만 바꾼 겁니다.
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { emergencyCardApi } from "../../api/endpoints/emergencyCard";
import type { EmergencyCard } from "../../types";

export function useEmergencyCard() {
  return useQuery({
    queryKey: ["emergencyCard"],
    queryFn: emergencyCardApi.get,
    retry: false, // 카드가 아직 없으면 404가 정상이라, 재시도 안 하도록
  });
}

export function useUpsertEmergencyCard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<EmergencyCard>) => emergencyCardApi.upsert(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["emergencyCard"] });
    },
  });
}
