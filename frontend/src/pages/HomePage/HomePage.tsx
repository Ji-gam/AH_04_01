import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { notificationApi } from "../../api/notificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { toDateString } from "../AlarmPage/dateUtils";
import { alarmTheme as t } from "../AlarmPage/theme";
import { buildGroups, loadChecked } from "../SchedulePage/scheduleData";

export default function HomePage() {
  const { user } = useAuth();
  const [meds, setMeds] = useState<MedicationSchedule[]>([]);
  const [alarms, setAlarms] = useState<NotificationScheduleResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([apiFetch<MedicationSchedule[]>("/medications"), notificationApi.list()])
      .then(([m, a]) => {
        setMeds(m);
        setAlarms(a);
      })
      .catch(() => {
        // 홈의 건강 카드는 참고용 요약이라, 실패해도 화면 전체를 막지 않고 카드만 조용히 숨긴다.
      })
      .finally(() => setLoading(false));
  }, []);

  const today = new Date();
  const groups = buildGroups(meds, alarms, today);
  const totalCount = groups.reduce((n, g) => n + g.items.length, 0);
  const checked = loadChecked(toDateString(today));
  const doneCount = groups.reduce(
    (n, g) => n + g.items.filter((i) => checked.has(i.key)).length,
    0,
  );

  return (
    <div style={{ background: t.pageBg, minHeight: "100vh", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: t.text, margin: "0 0 20px" }}>
          👋 안녕하세요, {user?.name ?? ""}님!
        </h1>

        {!loading && totalCount > 0 && (
          <Link to="/schedule" style={{ textDecoration: "none" }}>
            <div
              style={{
                background: t.cardBg,
                border: `1px solid ${t.border}`,
                borderRadius: 16,
                padding: 18,
                boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
              }}
            >
              <p style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700, color: t.primary }}>
                💗 오늘의 건강 카드
              </p>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: t.primarySoft,
                  borderRadius: 12,
                  padding: "12px 14px",
                }}
              >
                <span style={{ fontSize: 14, color: t.text }}>⏰ 금일 약 복용</span>
                <span style={{ fontSize: 15, fontWeight: 700, color: t.primary }}>
                  {doneCount} / {totalCount} 완료
                </span>
              </div>
            </div>
          </Link>
        )}

        {!loading && totalCount === 0 && (
          <div
            style={{
              background: t.cardBg,
              border: `1px dashed ${t.border}`,
              borderRadius: 16,
              padding: 24,
              textAlign: "center",
              color: t.textMuted,
            }}
          >
            <p style={{ fontSize: 26, margin: 0 }}>🌸</p>
            <p style={{ fontSize: 13, margin: "8px 0 0" }}>
              오늘 등록된 약이 없어요.{" "}
              <Link to="/alarms" style={{ color: t.primary }}>
                복약알림 등록하러 가기
              </Link>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
