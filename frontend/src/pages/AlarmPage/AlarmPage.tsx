import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { apiFetch, apiFetchRaw } from "../../api/client";
import { notificationApi } from "../../api/notificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import FamilyNotificationView from "../../components/family/FamilyNotificationView";
import FamilySwitcher from "../../components/family/FamilySwitcher";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { pinkTheme as t } from "../../theme/pinkTheme";
import SchedulePage from "../SchedulePage/SchedulePage";

import AlarmCalendar from "./components/AlarmCalendar";
import AlarmForm, { type AlarmFormSubmit } from "./components/AlarmForm";
import MedTimeForm from "./components/MedTimeForm";
import Modal from "./components/Modal";
import ToggleSwitch from "./components/ToggleSwitch";
import { isScheduleDueOnDate, toDateString } from "./dateUtils";

function getCurrentHHMM(): string {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

function isDueToday(schedule: NotificationScheduleResult): boolean {
  return isScheduleDueOnDate(schedule, new Date());
}

function dayLabel(schedule: NotificationScheduleResult): string {
  return schedule.frequency_type === "DAILY" ? "매일" : `매주 ${schedule.target_day_of_week}요일`;
}

/** 하루 복용 횟수의 임상 표기. 4회 이상은 표기 없이 횟수만 보여준다. */
const DOSE_NOTATION: Record<number, string> = { 1: "qd", 2: "bid", 3: "tid", 4: "qid" };

function doseLabel(count: number): string {
  const notation = DOSE_NOTATION[count];
  return notation ? `하루 ${count}회 (${notation})` : `하루 ${count}회`;
}

/** 같은 약을 하루 몇 번 먹는지 — 약 이름+반복 조건이 같은 알림 개수를 센다. */
function buildDoseCounts(schedules: NotificationScheduleResult[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const s of schedules) {
    const key = `${s.medication_name}|${s.frequency_type}|${s.target_day_of_week ?? ""}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

function doseCountOf(counts: Map<string, number>, s: NotificationScheduleResult): number {
  return counts.get(`${s.medication_name}|${s.frequency_type}|${s.target_day_of_week ?? ""}`) ?? 1;
}

// 복약 관리(medications)에는 알림 on/off 개념이 백엔드에 없어, 브라우저 알림 여부만
// localStorage에 보관한다 — 기본값은 켜짐(ON), 여기 저장된 키만 꺼짐 상태다.
const MED_ALARM_DISABLED_KEY = "medAlarmDisabled";

function loadMedAlarmDisabled(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(MED_ALARM_DISABLED_KEY) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

function saveMedAlarmDisabled(disabled: Set<string>) {
  localStorage.setItem(MED_ALARM_DISABLED_KEY, JSON.stringify([...disabled]));
}

export default function AlarmPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // (가족관리) 가족 선택 시 아래 이 화면 전체를 FamilyNotificationView로 전환한다.
  // 기존 본인 몫 로직(달력/약 시간 병합 등)은 전혀 안 건드리고, 완전히 별도 분기로 처리한다.
  const [selectedFamily, setSelectedFamily] = useState<{ profileId: number; name: string } | null>(
    null,
  );

  const [schedules, setSchedules] = useState<NotificationScheduleResult[]>([]);
  const [medSchedules, setMedSchedules] = useState<MedicationSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  // 약품검색(더보기)에서 "복약알림 등록"으로 넘어온 약 이름 — 추가 폼을 자동으로 열고 미리 채운다.
  const [prefillMedName, setPrefillMedName] = useState<string | undefined>(undefined);
  const [editingSchedule, setEditingSchedule] = useState<NotificationScheduleResult | null>(null);
  // 복약 관리에서 등록한 약의 시간 수정 (알림 추가 폼과 같은 UI, 시간만 변경)
  const [editingMed, setEditingMed] = useState<{ med: MedicationSchedule; time: string } | null>(
    null,
  );
  const [formError, setFormError] = useState<string | undefined>(undefined);
  const [isSaving, setIsSaving] = useState(false);
  const [medAlarmDisabled, setMedAlarmDisabled] = useState<Set<string>>(() =>
    loadMedAlarmDisabled(),
  );
  // 달력 날짜 클릭 시 복약 스케줄 화면을 페이지 이동 없이 모달로 띄운다.
  const [scheduleModalDate, setScheduleModalDate] = useState<string | null>(null);

  const today = new Date();
  // 달력 선택 표시는 항상 오늘 — 날짜 클릭 시 이 페이지에서 필터하는 대신 복약스케줄 화면으로 이동한다.
  const [selectedDateStr] = useState(toDateString(today));
  const [visibleYear, setVisibleYear] = useState(today.getFullYear());
  const [visibleMonth, setVisibleMonth] = useState(today.getMonth());

  const handlePrevMonth = () => {
    if (visibleMonth === 0) {
      setVisibleYear((y) => y - 1);
      setVisibleMonth(11);
    } else {
      setVisibleMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (visibleMonth === 11) {
      setVisibleYear((y) => y + 1);
      setVisibleMonth(0);
    } else {
      setVisibleMonth((m) => m + 1);
    }
  };

  const loadSchedules = () => {
    setLoading(true);
    setError(null);
    // 직접 등록한 알림 + 복약 관리에서 등록한 약 스케줄을 함께 불러와 목록에 같이 보여준다.
    Promise.all([notificationApi.list(), apiFetch<MedicationSchedule[]>("/medications")])
      .then(([alarms, meds]) => {
        setSchedules(alarms);
        setMedSchedules(meds);
      })
      .catch(() => setError("알림 목록을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadSchedules();
  }, []);

  // 약품검색에서 navigate(..., { state: { prefillMedicationName } })로 넘어온 경우 —
  // 추가 폼을 자동으로 열고 약 이름을 미리 채운 뒤, 뒤로가기 시 다시 열리지 않도록 state를 비운다.
  useEffect(() => {
    const state = location.state as { prefillMedicationName?: string } | null;
    if (!state?.prefillMedicationName) return;
    setPrefillMedName(state.prefillMedicationName);
    setShowAddForm(true);
    setEditingSchedule(null);
    navigate(location.pathname, { replace: true, state: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  // 탭이 열려 있는 동안, 오늘 예약 시각이 되면 브라우저 알림을 자동으로 띄운다.
  // 같은 시각의 약(직접 등록 알림 + 복약 관리 약)은 하나로 묶어 한 번만 울린다.
  // 진짜 백그라운드 푸시(서비스워커)가 아니라 포그라운드 폴링이라 탭을 닫으면 울리지 않는다.
  const firedTodayRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    const checkAndFire = () => {
      if (!("Notification" in window) || Notification.permission !== "granted") return;
      const nowHHMM = getCurrentHHMM();
      const names: string[] = [];
      for (const s of schedules) {
        if (s.is_active && isDueToday(s) && s.alarm_time.slice(0, 5) === nowHHMM) {
          names.push(s.medication_name);
        }
      }
      for (const m of medSchedules) {
        const matchTime = m.times.find((time) => time.slice(0, 5) === nowHHMM);
        if (matchTime && !medAlarmDisabled.has(`med-${m.id}-${matchTime}`)) {
          names.push(m.drug_name);
        }
      }
      if (names.length === 0) return;
      const key = `${new Date().toDateString()}:${nowHHMM}`;
      if (firedTodayRef.current.has(key)) return;
      firedTodayRef.current.add(key);
      new Notification("💊 복약 시간이에요!", { body: [...new Set(names)].join(", ") });
    };
    checkAndFire();
    const timer = setInterval(checkAndFire, 15000);
    return () => clearInterval(timer);
  }, [schedules, medSchedules, medAlarmDisabled]);

  const handleToggleMedAlarm = (key: string) => {
    setMedAlarmDisabled((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      saveMedAlarmDisabled(next);
      return next;
    });
  };

  const requestNotificationPermission = () => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  };

  // 하루 2회(bid)/3회(tid)면 시각별로 알림을 한 건씩 등록한다 (백엔드는 알림 1건 = 시각 1개).
  const handleCreate = (data: AlarmFormSubmit) => {
    setIsSaving(true);
    setFormError(undefined);
    Promise.all(
      data.alarm_times.map((time) =>
        notificationApi.create({
          medication_name: data.medication_name,
          frequency_type: data.frequency_type,
          target_day_of_week: data.target_day_of_week,
          alarm_time: time,
        }),
      ),
    )
      .then(() => {
        setShowAddForm(false);
        loadSchedules();
      })
      .catch((e: Error) => {
        setFormError(`저장에 실패했습니다. (${e.message})`);
        // 여러 건 중 일부만 저장됐을 수 있으니 목록은 새로 불러온다.
        loadSchedules();
      })
      .finally(() => setIsSaving(false));
  };

  const handleUpdate = (data: AlarmFormSubmit) => {
    if (!editingSchedule) return;
    setIsSaving(true);
    setFormError(undefined);
    notificationApi
      .update(editingSchedule.id, {
        medication_name: data.medication_name,
        frequency_type: data.frequency_type,
        target_day_of_week: data.target_day_of_week,
        alarm_time: data.alarm_times[0],
      })
      .then(() => {
        setEditingSchedule(null);
        loadSchedules();
      })
      .catch((e: Error) => setFormError(`수정에 실패했습니다. (${e.message})`))
      .finally(() => setIsSaving(false));
  };

  const handleToggleActive = (schedule: NotificationScheduleResult) => {
    notificationApi
      .update(schedule.id, { is_active: !schedule.is_active })
      .then(loadSchedules)
      .catch((e: Error) => setError(`알림 상태 변경에 실패했습니다. (${e.message})`));
  };

  // 수정 폼은 모달로 뜨므로 스크롤 이동이 필요 없다.
  const startEdit = (schedule: NotificationScheduleResult) => {
    setEditingSchedule(schedule);
    setEditingMed(null);
    setShowAddForm(false);
    setFormError(undefined);
  };

  const startEditMed = (med: MedicationSchedule, time: string) => {
    setEditingMed({ med, time });
    setEditingSchedule(null);
    setShowAddForm(false);
    setFormError(undefined);
  };

  // 해당 시각 하나만 새 시각으로 바꾸고, 나머지 시각은 그대로 유지한다.
  const handleUpdateMedTime = (newTime: string) => {
    if (!editingMed) return;
    setIsSaving(true);
    setFormError(undefined);
    const oldHHMM = editingMed.time.slice(0, 5);
    const newTimes = [
      ...new Set(
        editingMed.med.times.map((time) => (time.slice(0, 5) === oldHHMM ? newTime : time)),
      ),
    ].sort();
    apiFetch(`/medications/${editingMed.med.id}`, {
      method: "PATCH",
      body: JSON.stringify({ times: newTimes }),
    })
      .then(() => {
        setEditingMed(null);
        loadSchedules();
      })
      .catch((e: Error) => setFormError(`수정에 실패했습니다. (${e.message})`))
      .finally(() => setIsSaving(false));
  };

  const handleDelete = (schedule: NotificationScheduleResult) => {
    if (!window.confirm(`"${schedule.medication_name}" 알림을 삭제할까요?`)) return;
    notificationApi
      .remove(schedule.id)
      .then(loadSchedules)
      .catch((e: Error) => setError(`알림 삭제에 실패했습니다. (${e.message})`));
  };

  // 트랙커(복약 관리)에서 등록한 약은 원래 여기서 지울 방법이 없었다(토글/시간수정만 있고
  // 삭제가 아예 빠져있었음 - 본인이 직접 등록했든 가족이 등록해줬든 동일). 알림(row.alarm)에
  // 이미 있는 것과 같은 패턴으로 추가한다.
  const handleDeleteMed = (med: MedicationSchedule) => {
    if (!window.confirm(`"${med.drug_name}" 등록을 삭제할까요?`)) return;
    apiFetchRaw(`/medications/${med.id}`, { method: "DELETE" })
      .then(loadSchedules)
      .catch((e: Error) => setError(`약 삭제에 실패했습니다. (${e.message})`));
  };

  const doseCounts = buildDoseCounts(schedules);

  // 달력 밑에는 직접 등록한 알림 + 복약 관리에서 등록한 약을 같은 시각끼리 묶어 보여준다
  // (날짜별 시간표는 /schedule 화면 담당). alarm이 있으면 토글/수정/삭제가 가능한 직접 등록 알림.
  interface RegisteredRow {
    key: string;
    time: string;
    name: string;
    subLabel: string;
    alarm?: NotificationScheduleResult;
    med?: MedicationSchedule;
  }
  const rows: RegisteredRow[] = [
    ...schedules.map((s) => ({
      key: `alarm-${s.id}`,
      time: s.alarm_time.slice(0, 5),
      name: s.medication_name,
      subLabel:
        dayLabel(s) +
        (doseCountOf(doseCounts, s) > 1 ? ` · ${doseLabel(doseCountOf(doseCounts, s))}` : ""),
      alarm: s,
    })),
    ...medSchedules.flatMap((m) =>
      m.times.map((time) => ({
        key: `med-${m.id}-${time}`,
        time: time.slice(0, 5),
        name: m.drug_name,
        subLabel: `매일${m.times.length > 1 ? ` · ${doseLabel(m.times.length)}` : ""}`,
        med: m,
      })),
    ),
  ].sort((a, b) => a.time.localeCompare(b.time));

  // 같은 시각끼리 하나의 카드로 묶는다 — 알림도 시각당 한 번만 울리는 것과 짝을 이룬다.
  const timeGroups: { time: string; items: RegisteredRow[] }[] = [];
  for (const row of rows) {
    const last = timeGroups[timeGroups.length - 1];
    if (last && last.time === row.time) last.items.push(row);
    else timeGroups.push({ time: row.time, items: [row] });
  }

  // (가족관리) 가족 구성원을 선택한 상태면, 본인 몫의 복잡한 달력/병합 로직은 그대로 두고
  // 화면 자체를 완전히 별도의 단순 화면(FamilyNotificationView)으로 바꿔치기한다.
  if (selectedFamily) {
    return (
      <div style={{ background: t.pageBg, minHeight: "100vh", padding: "24px 16px" }}>
        <div style={{ maxWidth: 480, margin: "0 auto" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
            }}
          >
            <button
              type="button"
              onClick={() => setSelectedFamily(null)}
              style={{
                border: "none",
                background: "none",
                color: t.primary,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                padding: 0,
              }}
            >
              ← 내 복약알림으로
            </button>
            <FamilySwitcher
              selectedProfileId={selectedFamily.profileId}
              onSelect={(target) => setSelectedFamily(target)}
            />
          </div>
          <FamilyNotificationView
            targetProfileId={selectedFamily.profileId}
            targetName={selectedFamily.name}
          />
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: t.pageBg, minHeight: "100vh", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/")}
          style={{
            background: "none",
            border: "none",
            color: t.textMuted,
            padding: 0,
            marginBottom: 12,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 20,
          }}
        >
          <h1 style={{ fontSize: 22, fontWeight: 700, color: t.primary, margin: 0 }}>
            💗 복약 알림
          </h1>
          <div style={{ display: "flex", gap: 8 }}>
            <FamilySwitcher
              selectedProfileId={null}
              onSelect={(target) => setSelectedFamily(target)}
            />
            <button
              type="button"
              onClick={() => {
                requestNotificationPermission();
                setShowAddForm((v) => !v);
                setEditingSchedule(null);
                setFormError(undefined);
              }}
              style={{
                padding: "8px 16px",
                borderRadius: 999,
                border: "none",
                background: t.primary,
                color: "white",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              + 알림 추가
            </button>
          </div>
        </div>

        {showAddForm && (
          <Modal
            onClose={() => {
              setShowAddForm(false);
              setPrefillMedName(undefined);
            }}
          >
            <AlarmForm
              key={prefillMedName ?? "blank"}
              initialMedicationName={prefillMedName}
              isSaving={isSaving}
              errorMessage={formError}
              onCancel={() => {
                setShowAddForm(false);
                setPrefillMedName(undefined);
              }}
              onSubmit={(data) => {
                handleCreate(data);
                setPrefillMedName(undefined);
              }}
            />
          </Modal>
        )}

        {editingSchedule && (
          <Modal onClose={() => setEditingSchedule(null)}>
            <AlarmForm
              key={editingSchedule.id}
              initial={editingSchedule}
              isSaving={isSaving}
              errorMessage={formError}
              onCancel={() => setEditingSchedule(null)}
              onSubmit={handleUpdate}
            />
          </Modal>
        )}

        {editingMed && (
          <Modal onClose={() => setEditingMed(null)}>
            <MedTimeForm
              key={`${editingMed.med.id}-${editingMed.time}`}
              medName={editingMed.med.drug_name}
              initialTime={editingMed.time}
              isSaving={isSaving}
              errorMessage={formError}
              onCancel={() => setEditingMed(null)}
              onSubmit={handleUpdateMedTime}
            />
          </Modal>
        )}

        {/* 날짜를 누르면 그 날짜의 복약 스케줄 화면(타임라인+복용체크)을 모달로 띄운다. */}
        {scheduleModalDate && (
          <Modal onClose={() => setScheduleModalDate(null)}>
            <SchedulePage dateStr={scheduleModalDate} embedded />
          </Modal>
        )}

        <AlarmCalendar
          year={visibleYear}
          month={visibleMonth}
          selectedDateStr={selectedDateStr}
          schedules={schedules}
          onSelectDate={(dateStr) => setScheduleModalDate(dateStr)}
          onPrevMonth={handlePrevMonth}
          onNextMonth={handleNextMonth}
        />

        <h2 style={{ fontSize: 15, color: t.text, marginBottom: 10 }}>🔔 등록된 알림</h2>

        {loading && <p style={{ color: t.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: t.danger, fontSize: 14 }}>{error}</p>}

        {!loading && !error && rows.length === 0 && (
          <div
            style={{
              background: t.cardBg,
              border: `1px dashed ${t.border}`,
              borderRadius: 16,
              padding: 28,
              textAlign: "center",
              color: t.textMuted,
              marginBottom: 20,
            }}
          >
            <p style={{ fontSize: 28, margin: 0 }}>🌸</p>
            <p style={{ fontSize: 14, margin: "8px 0 0" }}>등록된 알림이 없어요.</p>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 24 }}>
          {timeGroups.map((group) => (
            <div
              key={group.time}
              style={{
                background: t.cardBg,
                border: `1px solid ${t.border}`,
                borderRadius: 14,
                padding: "14px 16px",
                boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                <span style={{ fontSize: 16, fontWeight: 700, color: t.primary }}>
                  {group.time}
                </span>
                {group.items.length > 1 && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: t.primary,
                      background: t.primarySoft,
                      borderRadius: 999,
                      padding: "1px 8px",
                    }}
                  >
                    {group.items.length}개
                  </span>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {group.items.map((row, i) => (
                  <div
                    key={row.key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: i === 0 ? "0 0 8px" : "8px 0",
                      borderTop: i > 0 ? `1px solid ${t.border}` : undefined,
                      opacity:
                        (row.alarm && !row.alarm.is_active) ||
                        (row.med && medAlarmDisabled.has(row.key))
                          ? 0.5
                          : 1,
                    }}
                  >
                    <div>
                      <span style={{ fontSize: 14, color: t.text }}>{row.name}</span>
                      <p style={{ fontSize: 12, color: t.textMuted, margin: "2px 0 0" }}>
                        {row.subLabel}
                      </p>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      {row.alarm ? (
                        <>
                          <ToggleSwitch
                            checked={row.alarm.is_active}
                            onChange={() => handleToggleActive(row.alarm!)}
                            ariaLabel={`${row.name} 알림 ${row.alarm.is_active ? "끄기" : "켜기"}`}
                          />
                          <button
                            type="button"
                            aria-label="알림 수정"
                            onClick={() => startEdit(row.alarm!)}
                            style={{
                              border: "none",
                              background: "none",
                              color: t.textMuted,
                              cursor: "pointer",
                              fontSize: 14,
                            }}
                          >
                            ✏️
                          </button>
                          <button
                            type="button"
                            aria-label="알림 삭제"
                            onClick={() => handleDelete(row.alarm!)}
                            style={{
                              border: "none",
                              background: "none",
                              color: t.textMuted,
                              cursor: "pointer",
                              fontSize: 14,
                            }}
                          >
                            🗑️
                          </button>
                        </>
                      ) : (
                        <>
                          <ToggleSwitch
                            checked={!medAlarmDisabled.has(row.key)}
                            onChange={() => handleToggleMedAlarm(row.key)}
                            ariaLabel={`${row.name} 알림 ${medAlarmDisabled.has(row.key) ? "켜기" : "끄기"}`}
                          />
                          <button
                            type="button"
                            aria-label={`${row.name} 복용 시각 수정`}
                            onClick={() => startEditMed(row.med!, row.time)}
                            style={{
                              border: "none",
                              background: "none",
                              color: t.textMuted,
                              cursor: "pointer",
                              fontSize: 14,
                            }}
                          >
                            ✏️
                          </button>
                          <button
                            type="button"
                            aria-label={`${row.name} 등록 삭제`}
                            onClick={() => handleDeleteMed(row.med!)}
                            style={{
                              border: "none",
                              background: "none",
                              color: t.textMuted,
                              cursor: "pointer",
                              fontSize: 14,
                            }}
                          >
                            🗑️
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
