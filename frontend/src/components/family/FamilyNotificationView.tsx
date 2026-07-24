import { useEffect, useState } from "react";

import {
  familyMedicationApi,
  type FamilyMedicationScheduleItem,
} from "../../api/familyMedicationApi";
import { familyNotificationApi } from "../../api/familyNotificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import AlarmCalendar from "../../pages/AlarmPage/components/AlarmCalendar";
import AlarmForm, { type AlarmFormSubmit } from "../../pages/AlarmPage/components/AlarmForm";
import MedTimeForm from "../../pages/AlarmPage/components/MedTimeForm";
import Modal from "../../pages/AlarmPage/components/Modal";
import ToggleSwitch from "../../pages/AlarmPage/components/ToggleSwitch";
import { toDateString } from "../../pages/AlarmPage/dateUtils";
import { pinkTheme as t } from "../../theme/pinkTheme";
import TimeInputField from "../ui/TimeInputField";

interface RegisteredRow {
  key: string;
  time: string;
  name: string;
  subLabel: string;
  alarm?: NotificationScheduleResult;
  med?: FamilyMedicationScheduleItem;
}

export default function FamilyNotificationView({
  targetProfileId,
  targetName,
}: {
  targetProfileId: number;
  targetName: string;
}) {
  const [schedules, setSchedules] = useState<NotificationScheduleResult[]>([]);
  const [medSchedules, setMedSchedules] = useState<FamilyMedicationScheduleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDateStr, setSelectedDateStr] = useState(toDateString(today));

  const [showAddForm, setShowAddForm] = useState(false);
  const [medicationName, setMedicationName] = useState("");
  const [alarmTime, setAlarmTime] = useState("08:00");
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // [2026-07-21 변경] 인라인(칸 하나짜리) 수정 대신, 본인 몫 복약알림 화면과 같은 모달 폼
  // (AlarmForm/MedTimeForm)을 그대로 재사용한다 - 두 컴포넌트 다 이 파일에서 고치지 않고
  // 그대로 가져다 쓰기만 한다(이미 AlarmCalendar/ToggleSwitch를 이 방식으로 쓰고 있던 것과
  // 같은 패턴).
  const [editingAlarm, setEditingAlarm] = useState<NotificationScheduleResult | null>(null);
  const [editingMedRow, setEditingMedRow] = useState<{
    med: FamilyMedicationScheduleItem;
    time: string;
  } | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [alarms, meds] = await Promise.all([
        familyNotificationApi.list(targetProfileId),
        familyMedicationApi.listForFamily(targetProfileId),
      ]);
      setSchedules(alarms);
      setMedSchedules(meds);
    } catch (err) {
      setError(err instanceof Error ? err.message : "불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetProfileId]);

  async function handleAdd() {
    if (!medicationName.trim()) return;
    setFormError(null);
    setIsSaving(true);
    try {
      await familyNotificationApi.create(targetProfileId, {
        medication_name: medicationName.trim(),
        frequency_type: "DAILY",
        alarm_time: `${alarmTime}:00`,
      });
      setMedicationName("");
      setAlarmTime("08:00");
      setShowAddForm(false);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "알림 등록에 실패했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggle(schedule: NotificationScheduleResult) {
    try {
      await familyNotificationApi.update(schedule.id, { is_active: !schedule.is_active });
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "변경에 실패했습니다.");
    }
  }

  async function handleDelete(schedule: NotificationScheduleResult) {
    if (!window.confirm(`"${schedule.medication_name}" 알림을 삭제할까요?`)) return;
    try {
      await familyNotificationApi.remove(schedule.id);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "삭제에 실패했습니다.");
    }
  }

  async function handleDeleteMed(med: FamilyMedicationScheduleItem) {
    if (!window.confirm(`"${med.drug_name}" 등록을 삭제할까요?`)) return;
    try {
      await familyMedicationApi.deleteForFamily(med.id);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "삭제에 실패했습니다.");
    }
  }

  // AlarmForm은 하루 여러 번(alarm_times 배열)까지 지원하지만, 여기서는 "기존 알림 하나를
  // 고치는 것"이라 본인 몫 화면의 수정 모드와 동일하게 alarm_times[0]만 사용한다.
  async function handleSaveAlarmEdit(data: AlarmFormSubmit) {
    if (!editingAlarm) return;
    setFormError(null);
    setIsSaving(true);
    try {
      await familyNotificationApi.update(editingAlarm.id, {
        medication_name: data.medication_name,
        frequency_type: data.frequency_type,
        target_day_of_week: data.target_day_of_week,
        alarm_time: data.alarm_times[0],
      });
      setEditingAlarm(null);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "수정에 실패했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  // 이 med는 여러 시각 중 하나(editingMedRow.time)를 대표하는 행이다 - 그 시각만 새 시각으로
  // 바꾸고 나머지 시각은 그대로 둔다 (본인 몫 AlarmForm.handleUpdateMedTime과 같은 패턴).
  async function handleSaveMedEdit(newTime: string) {
    if (!editingMedRow) return;
    setFormError(null);
    setIsSaving(true);
    try {
      const oldHHMM = editingMedRow.time;
      const newTimes = [
        ...new Set(
          editingMedRow.med.times.map((tm) => (tm.slice(0, 5) === oldHHMM ? newTime : tm)),
        ),
      ].sort();
      await familyMedicationApi.updateForFamily(editingMedRow.med.id, newTimes);
      setEditingMedRow(null);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "수정에 실패했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  const rows: RegisteredRow[] = [
    ...schedules.map((s) => ({
      key: `alarm-${s.id}`,
      time: s.alarm_time.slice(0, 5),
      name: s.medication_name,
      subLabel: s.frequency_type === "DAILY" ? "매일" : (s.target_day_of_week ?? ""),
      alarm: s,
    })),
    ...medSchedules.flatMap((m) =>
      m.times.map((time) => ({
        key: `med-${m.id}-${time}`,
        time: time.slice(0, 5),
        name: m.drug_name,
        subLabel: "매일",
        med: m,
      })),
    ),
  ].sort((a, b) => a.time.localeCompare(b.time));

  const timeGroups: { time: string; items: RegisteredRow[] }[] = [];
  for (const row of rows) {
    const last = timeGroups[timeGroups.length - 1];
    if (last && last.time === row.time) last.items.push(row);
    else timeGroups.push({ time: row.time, items: [row] });
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h1 style={{ fontSize: 20, fontWeight: 700, color: t.primary, margin: 0 }}>
          💗 {targetName}님의 복약알림
        </h1>
        <button
          type="button"
          onClick={() => setShowAddForm((v) => !v)}
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
          {showAddForm ? "닫기" : "+ 알림 추가"}
        </button>
      </div>

      {showAddForm && (
        <div
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 10,
            padding: 14,
            marginBottom: 16,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            background: t.primarySoft,
          }}
        >
          <input
            type="text"
            placeholder="약 이름 (예: 타이레놀)"
            value={medicationName}
            onChange={(e) => setMedicationName(e.target.value)}
            style={{
              padding: "10px 12px",
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              fontSize: 14,
            }}
          />
          <TimeInputField value={alarmTime} onChange={setAlarmTime} />
          {formError && <p style={{ margin: 0, fontSize: 12, color: t.danger }}>{formError}</p>}
          <button
            type="button"
            onClick={handleAdd}
            disabled={isSaving}
            style={{
              padding: "10px",
              border: "none",
              borderRadius: 8,
              background: t.primary,
              color: "#fff",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {isSaving ? "등록 중..." : "등록"}
          </button>
        </div>
      )}

      {editingAlarm && (
        <Modal onClose={() => setEditingAlarm(null)}>
          <AlarmForm
            key={editingAlarm.id}
            initial={editingAlarm}
            isSaving={isSaving}
            errorMessage={formError ?? undefined}
            onCancel={() => setEditingAlarm(null)}
            onSubmit={handleSaveAlarmEdit}
          />
        </Modal>
      )}

      {editingMedRow && (
        <Modal onClose={() => setEditingMedRow(null)}>
          <MedTimeForm
            key={`${editingMedRow.med.id}-${editingMedRow.time}`}
            medName={editingMedRow.med.drug_name}
            initialTime={editingMedRow.time}
            isSaving={isSaving}
            errorMessage={formError ?? undefined}
            onCancel={() => setEditingMedRow(null)}
            onSubmit={handleSaveMedEdit}
          />
        </Modal>
      )}

      {loading && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}
      {error && <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>}

      {!loading && !error && (
        <>
          <AlarmCalendar
            year={year}
            month={month}
            selectedDateStr={selectedDateStr}
            schedules={schedules}
            onSelectDate={setSelectedDateStr}
            onPrevMonth={() => {
              const d = new Date(year, month - 1, 1);
              setYear(d.getFullYear());
              setMonth(d.getMonth());
            }}
            onNextMonth={() => {
              const d = new Date(year, month + 1, 1);
              setYear(d.getFullYear());
              setMonth(d.getMonth());
            }}
          />

          <p style={{ margin: "20px 0 10px", fontWeight: 700, color: t.text }}>🔔 등록된 알림</p>

          {timeGroups.length === 0 ? (
            <div
              style={{
                border: `1px dashed ${t.border}`,
                borderRadius: 12,
                padding: "24px",
                textAlign: "center",
                color: t.textMuted,
                fontSize: 13,
              }}
            >
              등록된 알림이 없어요.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {timeGroups.map((group) => (
                <div
                  key={group.time}
                  style={{
                    border: `1px solid ${t.border}`,
                    borderRadius: 12,
                    padding: "12px 16px",
                    background: t.cardBg,
                  }}
                >
                  <p style={{ margin: "0 0 8px", fontWeight: 700, color: t.primary, fontSize: 15 }}>
                    {group.time}
                  </p>
                  {group.items.map((row) => (
                    <div
                      key={row.key}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "6px 0",
                      }}
                    >
                      <div>
                        <p style={{ margin: 0, fontSize: 14, color: t.text }}>💊 {row.name}</p>
                        <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
                          {row.subLabel}
                        </p>
                      </div>
                      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                        {row.alarm && (
                          <>
                            <ToggleSwitch
                              checked={row.alarm.is_active}
                              onChange={() => handleToggle(row.alarm!)}
                              ariaLabel={`${row.name} 알림 ${row.alarm.is_active ? "끄기" : "켜기"}`}
                            />
                            <button
                              type="button"
                              onClick={() => {
                                setFormError(null);
                                setEditingAlarm(row.alarm!);
                              }}
                              style={{
                                border: "none",
                                background: "none",
                                cursor: "pointer",
                                fontSize: 14,
                              }}
                              aria-label="알림 수정"
                            >
                              ✏️
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDelete(row.alarm!)}
                              style={{
                                border: "none",
                                background: "none",
                                color: t.textMuted,
                                cursor: "pointer",
                                fontSize: 14,
                              }}
                              aria-label="알림 삭제"
                            >
                              🗑️
                            </button>
                          </>
                        )}
                        {row.med && (
                          <>
                            <button
                              type="button"
                              onClick={() => {
                                setFormError(null);
                                setEditingMedRow({ med: row.med!, time: row.time });
                              }}
                              style={{
                                border: "none",
                                background: "none",
                                cursor: "pointer",
                                fontSize: 14,
                              }}
                              aria-label={`${row.name} 복용 시각 수정`}
                            >
                              ✏️
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteMed(row.med!)}
                              style={{
                                border: "none",
                                background: "none",
                                color: t.textMuted,
                                cursor: "pointer",
                                fontSize: 14,
                              }}
                              aria-label={`${row.name} 등록 삭제`}
                            >
                              🗑️
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
