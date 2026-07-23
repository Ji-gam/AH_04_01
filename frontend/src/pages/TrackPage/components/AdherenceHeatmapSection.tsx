import { useEffect, useState } from "react";

import { apiFetch } from "../../../api/client";
import { intakeApi, type IntakeDailyCount } from "../../../api/intakeApi";
import { notificationApi } from "../../../api/notificationApi";
import type { MedicationSchedule } from "../../../hooks/useMedication";
import { pinkTheme as t } from "../../../theme/pinkTheme";
import { buildGroups } from "../../SchedulePage/scheduleData";

const WEEKS = 13; // 최근 13주(91일) - 잔디심기 그래프와 비슷한 분량
const DAYS = WEEKS * 7;

/** 순응도(0~1)를 5단계 색으로 매핑한다 - 라이트니스가 단조감소하는 순차(sequential) 램프
 * 하나(핑크 계열)로만 구성해, "그날 예정된 게 없음"(회색, 채도 없음)과 뚜렷이 구분한다. */
const RATE_STEPS = ["#F3E3E8", "#FFD1DE", "#FF9FB6", "#FF6F91", "#D9436A"];
const NO_DOSE_COLOR = "#EDEBE8";

function colorForRate(rate: number | null): string {
  if (rate === null) return NO_DOSE_COLOR;
  const idx = Math.min(RATE_STEPS.length - 1, Math.floor(rate * RATE_STEPS.length));
  return RATE_STEPS[idx];
}

function toDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

interface DayCell {
  dateStr: string;
  day: number;
  rate: number | null; // null = 그날 예정된 복용이 없음
  done: number;
  total: number;
}

/** 복약 순응도 히트맵(F-ADH-1) - 최근 13주를 요일별 열로 묶어 GitHub 커밋 그래프 형태로
 * 보여준다. 분자(체크 개수)는 서버(medication_intake_logs)에서, 분모(그날 예정된 복용
 * 개수)는 프론트가 이미 갖고 있는 buildGroups(요일별 반복 규칙 포함)로 직접 계산해
 * 합친다 - 서버는 "언제 몇 번 예정돼 있었는지"의 반복 규칙을 모르기 때문이다. */
export default function AdherenceHeatmapSection() {
  const [cells, setCells] = useState<DayCell[] | null>(null);

  useEffect(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - (DAYS - 1));

    Promise.all([
      apiFetch<MedicationSchedule[]>("/medications"),
      notificationApi.list(),
      intakeApi.dailyCounts(toDateStr(start), toDateStr(end)),
    ])
      .then(([meds, alarms, counts]) => {
        const countByDate = new Map<string, IntakeDailyCount>(counts.map((c) => [c.date, c]));
        const result: DayCell[] = Array.from({ length: DAYS }, (_, i) => {
          const d = new Date(start);
          d.setDate(d.getDate() + i);
          const dateStr = toDateStr(d);
          const total = buildGroups(meds, alarms, d).reduce((n, g) => n + g.items.length, 0);
          const done = countByDate.get(dateStr)?.checked_count ?? 0;
          return {
            dateStr,
            day: d.getDay(),
            done,
            total,
            rate: total > 0 ? Math.min(1, done / total) : null,
          };
        });
        setCells(result);
      })
      .catch(() => setCells([]));
  }, []);

  // 로딩 중이거나, 구간 전체에 예정된 복용이 하나도 없으면(=콘텐츠 없음) 섹션 자체를 숨긴다
  // (기존 TODO 스텁의 "콘텐츠가 없으면 렌더링하지 않는다"는 의도를 그대로 유지).
  if (cells === null) return null;
  if (cells.every((c) => c.rate === null)) return null;

  const weeks: DayCell[][] = [];
  for (let w = 0; w < WEEKS; w++) weeks.push(cells.slice(w * 7, w * 7 + 7));

  return (
    <section
      style={{
        background: t.cardBg,
        border: `1px solid ${t.border}`,
        borderRadius: 16,
        padding: 18,
        marginBottom: 16,
        boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
      }}
    >
      <p style={{ margin: "0 0 2px", fontSize: 14, fontWeight: 700, color: t.primary }}>
        🗓️ 복약 순응도
      </p>
      <p style={{ margin: "0 0 14px", fontSize: 12, color: t.textMuted }}>
        최근 {WEEKS}주간 복용 체크 기록이에요. 색이 진할수록 그날 잘 챙겨 드신 거예요.
      </p>

      <div style={{ display: "flex", gap: 3, overflowX: "auto", paddingBottom: 4 }}>
        {weeks.map((week, wi) => (
          <div key={wi} style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {week.map((cell) => (
              <div
                key={cell.dateStr}
                title={
                  cell.rate === null
                    ? `${cell.dateStr}: 예정된 복용 없음`
                    : `${cell.dateStr}: ${cell.done}/${cell.total} 복용 (${Math.round(cell.rate * 100)}%)`
                }
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: 3,
                  background: colorForRate(cell.rate),
                  flexShrink: 0,
                }}
              />
            ))}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10 }}>
        <span style={{ fontSize: 11, color: t.textMuted }}>적음</span>
        {RATE_STEPS.map((color) => (
          <div key={color} style={{ width: 12, height: 12, borderRadius: 3, background: color }} />
        ))}
        <span style={{ fontSize: 11, color: t.textMuted }}>많음</span>
      </div>
    </section>
  );
}
