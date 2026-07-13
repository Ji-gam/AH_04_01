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

/** 복용 체크는 날짜별 localStorage에 보관한다(백엔드 복용 기록 도메인 합류 전까지의 임시 저장소). */
export function loadChecked(dateStr: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(`intake-${dateStr}`) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

export function saveChecked(dateStr: string, checked: Set<string>) {
  localStorage.setItem(`intake-${dateStr}`, JSON.stringify([...checked]));
}
