import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { notificationApi } from "../../api/notificationApi";
import type { NotificationScheduleResult } from "../../api/types";

import AlarmCalendar from "./components/AlarmCalendar";
import AlarmForm, { type AlarmFormSubmit } from "./components/AlarmForm";
import { isScheduleDueOnDate, toDateString } from "./dateUtils";
import { alarmTheme as t } from "./theme";

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

export default function AlarmPage() {
  const navigate = useNavigate();
  const [schedules, setSchedules] = useState<NotificationScheduleResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<NotificationScheduleResult | null>(null);
  const [formError, setFormError] = useState<string | undefined>(undefined);
  const [isSaving, setIsSaving] = useState(false);

  const today = new Date();
  // 달력 선택 표시는 항상 오늘 — 날짜 클릭 시 이 페이지에서 필터하는 대신 복약스케줄 화면으로 이동한다.
  const [selectedDateStr] = useState(toDateString(today));
  const [visibleYear, setVisibleYear] = useState(today.getFullYear());
  const [visibleMonth, setVisibleMonth] = useState(today.getMonth());
  const selectedDate = new Date(`${selectedDateStr}T00:00:00`);
  const isSelectedToday = selectedDateStr === toDateString(today);

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
    notificationApi
      .list()
      .then(setSchedules)
      .catch(() => setError("알림 목록을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadSchedules();
  }, []);

  // 탭이 열려 있는 동안, 오늘 예약 시각이 되면 브라우저 알림을 자동으로 띄운다.
  // 진짜 백그라운드 푸시(서비스워커)가 아니라 포그라운드 폴링이라 탭을 닫으면 울리지 않는다.
  const firedTodayRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    const checkAndFire = () => {
      if (!("Notification" in window) || Notification.permission !== "granted") return;
      const todayStr = new Date().toDateString();
      const nowHHMM = getCurrentHHMM();
      for (const s of schedules) {
        if (!s.is_active || !isDueToday(s)) continue;
        if (s.alarm_time.slice(0, 5) !== nowHHMM) continue;
        const key = `${todayStr}:${s.id}`;
        if (firedTodayRef.current.has(key)) continue;
        firedTodayRef.current.add(key);
        new Notification("💊 복약 시간이에요!", { body: s.medication_name });
      }
    };
    checkAndFire();
    const timer = setInterval(checkAndFire, 15000);
    return () => clearInterval(timer);
  }, [schedules]);

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

  // 수정 폼은 페이지 상단에 열리므로, 스크롤을 내린 상태에서도 폼이 보이도록 위로 올린다.
  const startEdit = (schedule: NotificationScheduleResult) => {
    setEditingSchedule(schedule);
    setShowAddForm(false);
    setFormError(undefined);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = (schedule: NotificationScheduleResult) => {
    if (!window.confirm(`"${schedule.medication_name}" 알림을 삭제할까요?`)) return;
    notificationApi
      .remove(schedule.id)
      .then(loadSchedules)
      .catch((e: Error) => setError(`알림 삭제에 실패했습니다. (${e.message})`));
  };

  const selectedDaySchedules = schedules
    .filter((s) => isScheduleDueOnDate(s, selectedDate))
    .sort((a, b) => a.alarm_time.localeCompare(b.alarm_time));

  const doseCounts = buildDoseCounts(schedules);

  const sectionTitle = isSelectedToday
    ? "오늘의 복약 시간표"
    : `${selectedDate.getMonth() + 1}월 ${selectedDate.getDate()}일 복약 시간표`;

  return (
    <div style={{ background: t.pageBg, minHeight: "100vh", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
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

        {showAddForm && (
          <AlarmForm
            isSaving={isSaving}
            errorMessage={formError}
            onCancel={() => setShowAddForm(false)}
            onSubmit={handleCreate}
          />
        )}

        {editingSchedule && (
          <AlarmForm
            key={editingSchedule.id}
            initial={editingSchedule}
            isSaving={isSaving}
            errorMessage={formError}
            onCancel={() => setEditingSchedule(null)}
            onSubmit={handleUpdate}
          />
        )}

        {/* 날짜를 누르면 복약 시간표 화면으로 이동해 그 날짜의 통합 타임라인(약+알림)을 보여준다. */}
        <AlarmCalendar
          year={visibleYear}
          month={visibleMonth}
          selectedDateStr={selectedDateStr}
          schedules={schedules}
          onSelectDate={(dateStr) => navigate(`/schedule?date=${dateStr}`)}
          onPrevMonth={handlePrevMonth}
          onNextMonth={handleNextMonth}
        />

        <h2 style={{ fontSize: 15, color: t.text, marginBottom: 10 }}>{sectionTitle}</h2>

        {loading && <p style={{ color: t.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: t.danger, fontSize: 14 }}>{error}</p>}

        {!loading && !error && selectedDaySchedules.length === 0 && (
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
            <p style={{ fontSize: 14, margin: "8px 0 0" }}>
              {isSelectedToday ? "오늘 등록된 알림이 없어요." : "이 날짜에 등록된 알림이 없어요."}
            </p>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 24 }}>
          {selectedDaySchedules.map((s) => (
            <div
              key={s.id}
              style={{
                background: t.cardBg,
                border: `1px solid ${t.border}`,
                borderRadius: 14,
                padding: "14px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                opacity: s.is_active ? 1 : 0.5,
              }}
            >
              <div>
                <span style={{ fontSize: 16, fontWeight: 700, color: t.primary }}>
                  {s.alarm_time.slice(0, 5)}
                </span>{" "}
                <span style={{ fontSize: 14, color: t.text }}>{s.medication_name}</span>
                <p style={{ fontSize: 12, color: t.textMuted, margin: "2px 0 0" }}>
                  {dayLabel(s)}
                  {doseCountOf(doseCounts, s) > 1 && ` · ${doseLabel(doseCountOf(doseCounts, s))}`}
                </p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 12,
                    color: t.textMuted,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={s.is_active}
                    onChange={() => handleToggleActive(s)}
                  />
                  알림
                </label>
                <button
                  type="button"
                  aria-label="알림 수정"
                  onClick={() => startEdit(s)}
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
                  onClick={() => handleDelete(s)}
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
              </div>
            </div>
          ))}
        </div>

        <h2 style={{ fontSize: 15, color: t.text, marginBottom: 10 }}>등록된 전체 알림</h2>
        {!loading && schedules.length === 0 && (
          <p style={{ color: t.textMuted, fontSize: 14 }}>등록된 알림이 없습니다.</p>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...schedules]
            .sort((a, b) => a.alarm_time.localeCompare(b.alarm_time))
            .map((s) => (
              <div
                key={s.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 13,
                  color: t.text,
                  padding: "8px 4px",
                  borderBottom: `1px solid ${t.border}`,
                }}
              >
                <span>
                  {s.alarm_time.slice(0, 5)} · {s.medication_name} · {dayLabel(s)}
                  {doseCountOf(doseCounts, s) > 1 && ` · ${doseLabel(doseCountOf(doseCounts, s))}`}
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ color: s.is_active ? t.success : t.textMuted }}>
                    {s.is_active ? "켜짐" : "꺼짐"}
                  </span>
                  <button
                    type="button"
                    aria-label="알림 수정"
                    onClick={() => startEdit(s)}
                    style={{
                      border: "none",
                      background: "none",
                      color: t.textMuted,
                      cursor: "pointer",
                      fontSize: 13,
                    }}
                  >
                    ✏️
                  </button>
                  <button
                    type="button"
                    aria-label="알림 삭제"
                    onClick={() => handleDelete(s)}
                    style={{
                      border: "none",
                      background: "none",
                      color: t.textMuted,
                      cursor: "pointer",
                      fontSize: 13,
                    }}
                  >
                    🗑️
                  </button>
                </span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
