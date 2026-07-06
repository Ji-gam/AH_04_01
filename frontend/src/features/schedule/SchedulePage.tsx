// src/features/schedule/SchedulePage.tsx
// 이 페이지는 "도메인 하나를 A-Z로 어떻게 만드는지" 보여주는 예시입니다.
// 다른 도메인 화면을 만들 때 이 파일 + useSchedules.ts 구조를 그대로 참고하시면 됩니다.
import { useState } from "react";
import { useSchedules, useCreateSchedule } from "./useSchedules";

export default function SchedulePage() {
  const { data: schedules, isLoading } = useSchedules();
  const createSchedule = useCreateSchedule();

  const [medicationId, setMedicationId] = useState("1");
  const [alarmTime, setAlarmTime] = useState("08:30");
  const [frequencyType, setFrequencyType] = useState<"DAILY" | "WEEKLY">("DAILY");

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-6 text-2xl font-bold">복약 스케줄</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          createSchedule.mutate({
            medication_id: Number(medicationId),
            frequency_type: frequencyType,
            alarm_time: `${alarmTime}:00`,
          });
        }}
        className="mb-8 rounded-xl border p-4"
        style={{ borderColor: "var(--panel-border)", background: "var(--panel-bg)" }}
      >
        <h2 className="mb-3 font-semibold">새 스케줄 등록</h2>
        <div className="mb-3 flex gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>의약품 ID</label>
            <input
              value={medicationId}
              onChange={(e) => setMedicationId(e.target.value)}
              className="w-full rounded-lg border bg-transparent px-3 py-2"
              style={{ borderColor: "var(--panel-border)" }}
            />
            {/* TODO(조원 구현): 의약품 ID를 직접 입력하는 대신, medicationApi.get()으로
                자동완성/드롭다운 검색을 붙이면 사용성이 훨씬 좋아집니다. */}
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>복용 시각</label>
            <input
              type="time"
              value={alarmTime}
              onChange={(e) => setAlarmTime(e.target.value)}
              className="w-full rounded-lg border bg-transparent px-3 py-2"
              style={{ borderColor: "var(--panel-border)" }}
            />
          </div>
        </div>
        <div className="mb-4">
          <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>주기</label>
          <select
            value={frequencyType}
            onChange={(e) => setFrequencyType(e.target.value as "DAILY" | "WEEKLY")}
            className="w-full rounded-lg border bg-transparent px-3 py-2"
            style={{ borderColor: "var(--panel-border)" }}
          >
            <option value="DAILY" style={{ color: "black" }}>매일 (DAILY)</option>
            <option value="WEEKLY" style={{ color: "black" }}>매주 (WEEKLY)</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={createSchedule.isPending}
          className="rounded-lg px-4 py-2 font-semibold text-black"
          style={{ background: "var(--accent-cyan)" }}
        >
          {createSchedule.isPending ? "등록 중..." : "스케줄 등록"}
        </button>
      </form>

      <h2 className="mb-3 font-semibold">등록된 스케줄</h2>
      {isLoading && <p style={{ color: "var(--text-secondary)" }}>불러오는 중...</p>}
      {schedules?.length === 0 && <p style={{ color: "var(--text-muted)" }}>등록된 스케줄이 없습니다.</p>}
      <div className="flex flex-col gap-2">
        {schedules?.map((s) => (
          <div
            key={s.schedule_id}
            className="flex items-center justify-between rounded-xl border p-4"
            style={{ borderColor: "var(--panel-border)", background: "var(--panel-bg)" }}
          >
            <div>
              <p className="font-semibold">{s.card_alias || `의약품 #${s.medication_id}`}</p>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {s.frequency_type === "DAILY" ? "매일" : `매주 ${s.target_day_of_week ?? ""}`} · {s.alarm_time}
              </p>
            </div>
            <span
              className="rounded-full px-3 py-1 text-xs font-semibold"
              style={{ background: "rgba(0,242,254,0.12)", color: "var(--accent-cyan)" }}
            >
              {s.is_active ? "활성" : "비활성"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
