import { intakeApi } from "../../api/intakeApi";
import type { NotificationScheduleResult } from "../../api/types";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { isScheduleDueOnDate } from "../AlarmPage/dateUtils";

const FORM_TYPE_UNIT: Record<string, string> = {
  TABLET: "1정",
  CAPSULE: "1캡슐",
  INJECTION: "주사",
  SYRUP: "시럽",
};

export interface TimelineItem {
  key: string;
  name: string;
  /** 약 이름 아래 줄 — 병원명이 있으면 병원명, 없으면 제형 단위 */
  subLabel: string | null;
  hospitalName: string | null;
  /** 이 약을 하루에 몇 번 먹는지 — 약 이름 옆에 표시 */
  doseCount: number;
  tip: string | null;
}

export interface TimeGroup {
  time: string; // "HH:MM"
  items: TimelineItem[];
  isPrescription: boolean;
}

/** 등록된 약 스케줄(medications) + 직접 등록 알림 중 그 날짜에 복용할 것들을 시간별로 묶는다.
 * 복약 시간표(/schedule)와 홈 화면 건강 카드가 "오늘 몇 개 중 몇 개" 숫자를 똑같이 계산하려면
 * 이 함수 하나로 공유해야 두 화면 숫자가 어긋나지 않는다. */
export function buildGroups(
  meds: MedicationSchedule[],
  alarms: NotificationScheduleResult[],
  date: Date,
): TimeGroup[] {
  const byTime = new Map<string, TimelineItem[]>();
  const push = (time: string, item: TimelineItem) => {
    const arr = byTime.get(time) ?? [];
    arr.push(item);
    byTime.set(time, arr);
  };

  for (const m of meds) {
    for (const time of m.times) {
      push(time.slice(0, 5), {
        key: `med-${m.id}-${time}`,
        name: m.drug_name,
        subLabel:
          m.hospital_name ?? (m.form_type ? (FORM_TYPE_UNIT[m.form_type] ?? m.form_type) : null),
        hospitalName: m.hospital_name ?? null,
        doseCount: m.times.length,
        tip: m.dosage_guideline ?? null,
      });
    }
  }

  // 직접 등록 알림은 같은 약 이름의 알림 개수 = 하루 복용 횟수
  const dueAlarms = alarms.filter((a) => a.is_active && isScheduleDueOnDate(a, date));
  const alarmDoseCounts = new Map<string, number>();
  for (const a of dueAlarms) {
    alarmDoseCounts.set(a.medication_name, (alarmDoseCounts.get(a.medication_name) ?? 0) + 1);
  }
  for (const a of dueAlarms) {
    push(a.alarm_time.slice(0, 5), {
      key: `alarm-${a.id}`,
      name: a.medication_name,
      subLabel: "직접 등록 알림",
      hospitalName: null,
      doseCount: alarmDoseCounts.get(a.medication_name) ?? 1,
      tip: null,
    });
  }

  return [...byTime.entries()]
    .sort(([t1], [t2]) => t1.localeCompare(t2))
    .map(([time, items]) => ({
      time,
      items,
      isPrescription: items.some((i) => i.key.startsWith("med-")),
    }));
}

/** item.key("med-{id}-{HH:MM}" 또는 "alarm-{id}")를 서버 API가 쓰는 (source_type, source_id)로
 * 되돌린다(F-ADH-1). alarm 쪽은 키에 시각이 없으니(NotificationSchedule 행 자체가 이미 시각
 * 하나) scheduled_time은 호출부가 그 항목이 속한 TimeGroup.time을 그대로 넘겨준다. */
export function keyToSource(key: string): {
  source_type: "medication_schedule" | "notification_schedule";
  source_id: number;
} {
  if (key.startsWith("med-")) {
    const rest = key.slice(4); // "{id}-{HH:MM}"
    const lastDash = rest.lastIndexOf("-");
    return { source_type: "medication_schedule", source_id: Number(rest.slice(0, lastDash)) };
  }
  return { source_type: "notification_schedule", source_id: Number(key.slice(6)) }; // "alarm-{id}"
}

function sourceToKey(sourceType: string, sourceId: number, scheduledTime: string): string {
  return sourceType === "medication_schedule"
    ? `med-${sourceId}-${scheduledTime}`
    : `alarm-${sourceId}`;
}

/** 복용 체크는 서버(medication_intake_logs)에 저장한다(F-ADH-1) - 예전엔 localStorage에만
 * 저장해서 기기를 바꾸거나 캐시를 지우면 기록이 사라졌다. 실패하면(오프라인 등) 빈 Set을
 * 반환해 화면은 계속 쓸 수 있게 한다 - 순응도 요약은 참고용이라 조회 실패로 앱을 막지 않는다. */
export async function loadChecked(dateStr: string): Promise<Set<string>> {
  try {
    const records = await intakeApi.list(dateStr);
    return new Set(records.map((r) => sourceToKey(r.source_type, r.source_id, r.scheduled_time)));
  } catch {
    return new Set();
  }
}

/** 체크/체크해제 하나를 서버에 반영한다. item.key만으로는 alarm 항목의 시각을 알 수 없어
 * scheduledTime(그 항목이 속한 TimeGroup.time)을 호출부에서 같이 넘겨받는다. */
export async function toggleChecked(
  item: TimelineItem,
  scheduledTime: string,
  dateStr: string,
  checked: boolean,
) {
  const source = keyToSource(item.key);
  await intakeApi.toggle({ ...source, scheduled_time: scheduledTime }, dateStr, checked);
}
