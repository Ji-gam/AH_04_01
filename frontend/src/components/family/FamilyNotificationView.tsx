import { useEffect, useState } from "react";

import {
  familyMedicationApi,
  type FamilyMedicationScheduleItem,
} from "../../api/familyMedicationApi";
import { familyNotificationApi } from "../../api/familyNotificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import AlarmCalendar from "../../pages/AlarmPage/components/AlarmCalendar";
import ToggleSwitch from "../../pages/AlarmPage/components/ToggleSwitch";
import { toDateString } from "../../pages/AlarmPage/dateUtils";
import { pinkTheme as t } from "../../theme/pinkTheme";

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

  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editTime, setEditTime] = useState("");

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

  async function handleSaveEdit(row: RegisteredRow) {
    try {
      if (row.alarm) {
        await familyNotificationApi.update(row.alarm.id, { alarm_time: `${editTime}:00` });
      }
      setEditingKey(null);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "수정에 실패했습니다.");
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
          <input
            type="time"
            value={alarmTime}
            onChange={(e) => setAlarmTime(e.target.value)}
            style={{
              padding: "10px 12px",
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              fontSize: 14,
            }}
          />
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
                      {editingKey === row.key ? (
                        <div style={{ display: "flex", gap: 6, alignItems: "center", flex: 1 }}>
                          <span style={{ fontSize: 14, color: t.text }}>{row.name}</span>
                          <input
                            type="time"
                            value={editTime}
                            onChange={(e) => setEditTime(e.target.value)}
                            style={{
                              padding: "4px 8px",
                              border: `1px solid ${t.border}`,
                              borderRadius: 6,
                              fontSize: 13,
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => handleSaveEdit(row)}
                            style={{
                              border: "none",
                              borderRadius: 6,
                              background: t.primary,
                              color: "#fff",
                              fontSize: 12,
                              padding: "4px 10px",
                              cursor: "pointer",
                            }}
                          >
                            저장
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingKey(null)}
                            style={{
                              border: `1px solid ${t.border}`,
                              borderRadius: 6,
                              background: t.cardBg,
                              color: t.textMuted,
                              fontSize: 12,
                              padding: "4px 10px",
                              cursor: "pointer",
                            }}
                          >
                            취소
                          </button>
                        </div>
                      ) : (
                        <>
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
                                    setEditingKey(row.key);
                                    setEditTime(row.time);
                                  }}
                                  style={{
                                    border: "none",
                                    background: "none",
                                    cursor: "pointer",
                                    fontSize: 14,
                                  }}
                                  aria-label="시간 수정"
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
                                    fontSize: 12,
                                    cursor: "pointer",
                                  }}
                                >
                                  삭제
                                </button>
                              </>
                            )}
                            {row.med && (
                              <button
                                type="button"
                                onClick={() => handleDeleteMed(row.med!)}
                                style={{
                                  border: "none",
                                  background: "none",
                                  color: t.textMuted,
                                  fontSize: 12,
                                  cursor: "pointer",
                                }}
                              >
                                삭제
                              </button>
                            )}
                          </div>
                        </>
                      )}
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
