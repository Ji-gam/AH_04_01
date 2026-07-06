// src/features/schedule/useSchedules.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { scheduleApi } from "../../api/endpoints/schedule";
import type { ScheduleCreate } from "../../types";

export function useSchedules() {
  return useQuery({
    queryKey: ["schedules"],
    queryFn: scheduleApi.list,
  });
}

export function useCreateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ScheduleCreate) => scheduleApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}
