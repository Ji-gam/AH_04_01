import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { notificationSettingsApi } from "../../api/notificationSettingsApi";
import type { NotificationSettingsResult } from "../../api/types";
import TimeInputField from "../../components/ui/TimeInputField";
import { pinkTheme as t } from "../../theme/pinkTheme";
import ToggleSwitch from "../AlarmPage/components/ToggleSwitch";

/** 스피커 없이 짧게 "삐" 소리를 내는 테스트용 비프음 (오디오 파일 없이 Web Audio로 생성). */
function playTestBeep() {
  const AudioContextClass =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextClass) return;
  const ctx = new AudioContextClass();
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = "sine";
  oscillator.frequency.value = 880;
  gain.gain.value = 0.15;
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start();
  oscillator.stop(ctx.currentTime + 0.2);
  oscillator.onended = () => ctx.close();
}

const rowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 12,
  padding: "14px 0",
  borderBottom: `1px solid ${t.border}`,
};

const rowLabelStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 700,
  color: t.text,
  margin: 0,
};

const rowDescStyle: React.CSSProperties = {
  fontSize: 12,
  color: t.textMuted,
  margin: "3px 0 0",
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: t.textMuted,
  margin: "24px 0 4px",
};

interface ToggleRowProps {
  label: string;
  desc: string;
  checked: boolean;
  onChange: () => void;
}

function ToggleRow({ label, desc, checked, onChange }: ToggleRowProps) {
  return (
    <div style={rowStyle}>
      <span>
        <p style={rowLabelStyle}>{label}</p>
        <p style={rowDescStyle}>{desc}</p>
      </span>
      <ToggleSwitch checked={checked} onChange={onChange} ariaLabel={label} />
    </div>
  );
}

export default function NotificationSettingsPage() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<NotificationSettingsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<string | null>(null);

  useEffect(() => {
    notificationSettingsApi
      .get()
      .then(setSettings)
      .catch(() => setError("알림설정을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  // 서버 응답은 그대로, 화면엔 낙관적으로 먼저 반영한다 — 실패하면 이전 값으로 되돌린다.
  const update = <K extends keyof NotificationSettingsResult>(
    key: K,
    value: NotificationSettingsResult[K],
  ) => {
    if (!settings) return;
    const prev = settings;
    const next = { ...settings, [key]: value };
    setSettings(next);
    setTestStatus(null);
    notificationSettingsApi.update({ [key]: value }).catch(() => {
      setSettings(prev);
      setError("설정 저장에 실패했습니다.");
    });
  };

  const toggle = (key: keyof NotificationSettingsResult) => update(key, !settings?.[key] as never);

  const handleSendTest = async () => {
    if (!settings) return;
    if (!("Notification" in window)) {
      setTestStatus("이 브라우저는 알림 기능을 지원하지 않아요.");
      return;
    }
    let permission = Notification.permission;
    if (permission === "default") {
      permission = await Notification.requestPermission();
    }
    if (permission !== "granted") {
      setTestStatus("알림 권한이 꺼져 있어요. 브라우저 설정에서 알림을 허용해주세요.");
      return;
    }
    if (settings.popup_enabled) {
      new Notification("🔔 테스트 알림", { body: "설정하신 알림이 이렇게 도착해요." });
    }
    if (settings.sound_enabled) {
      playTestBeep();
    }
    if (settings.vibration_enabled && navigator.vibrate) {
      navigator.vibrate(200);
    }
    setTestStatus("✓ 테스트 알림을 보냈어요.");
  };

  return (
    <div style={{ background: t.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: t.textMuted,
            padding: 0,
            marginBottom: 12,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: t.text, margin: "0 0 6px" }}>
          🔔 알림설정
        </h1>

        <p style={{ margin: "0 0 12px", fontSize: 13, color: t.textMuted, lineHeight: 1.5 }}>
          받고 싶은 알림과 무음 시간대를 설정해주세요.
        </p>

        {loading && <p style={{ color: t.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>}

        {settings && (
          <>
            <ToggleRow
              label="복약알림 푸시"
              desc="복약 시간에 맞춰 푸시 알림을 받습니다"
              checked={settings.push_enabled}
              onChange={() => toggle("push_enabled")}
            />
            <ToggleRow
              label="AI챗봇 답변 알림"
              desc="AI챗봇 상담 답변이 도착하면 알려드려요"
              checked={settings.chatbot_reply_enabled}
              onChange={() => toggle("chatbot_reply_enabled")}
            />
            <ToggleRow
              label="공지사항 알림"
              desc="서비스 공지사항 및 업데이트 소식을 알려드려요"
              checked={settings.notice_enabled}
              onChange={() => toggle("notice_enabled")}
            />
            <ToggleRow
              label="마케팅 알림"
              desc="이벤트 및 혜택 정보를 알려드려요"
              checked={settings.marketing_enabled}
              onChange={() => toggle("marketing_enabled")}
            />
            <ToggleRow
              label="라이프스타일 팁 알림"
              desc="맞춤 건강 콘텐츠가 새로 올라오면 알려드려요"
              checked={settings.lifestyle_tip_enabled}
              onChange={() => toggle("lifestyle_tip_enabled")}
            />

            <p style={sectionTitleStyle}>무음 시간대</p>
            <ToggleRow
              label="무음 모드"
              desc="설정한 시간대에는 알림 소리 없이 무음으로 받아요"
              checked={settings.quiet_mode_enabled}
              onChange={() => toggle("quiet_mode_enabled")}
            />
            {settings.quiet_mode_enabled && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "14px 0",
                  borderBottom: `1px solid ${t.border}`,
                }}
              >
                <TimeInputField
                  value={settings.quiet_start.slice(0, 5)}
                  onChange={(v) => update("quiet_start", `${v}:00`)}
                />
                <span style={{ color: t.textMuted, fontSize: 13 }}>~</span>
                <TimeInputField
                  value={settings.quiet_end.slice(0, 5)}
                  onChange={(v) => update("quiet_end", `${v}:00`)}
                />
              </div>
            )}

            <p style={sectionTitleStyle}>알림 강도</p>
            <ToggleRow
              label="소리"
              desc="알림이 올 때 소리를 재생해요"
              checked={settings.sound_enabled}
              onChange={() => toggle("sound_enabled")}
            />
            <ToggleRow
              label="진동"
              desc="알림이 올 때 진동으로 알려드려요 (진동 지원 기기)"
              checked={settings.vibration_enabled}
              onChange={() => toggle("vibration_enabled")}
            />
            <ToggleRow
              label="팝업"
              desc="알림이 올 때 화면에 팝업으로 보여드려요"
              checked={settings.popup_enabled}
              onChange={() => toggle("popup_enabled")}
            />

            <button
              type="button"
              onClick={handleSendTest}
              style={{
                width: "100%",
                padding: "14px 0",
                marginTop: 24,
                borderRadius: 12,
                border: `1px solid ${t.primary}`,
                background: t.cardBg,
                color: t.primary,
                fontSize: 15,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              🔔 테스트 알림 보내기
            </button>

            {testStatus && (
              <p
                style={{
                  margin: "10px 0 0",
                  fontSize: 13,
                  color: t.textMuted,
                  textAlign: "center",
                }}
              >
                {testStatus}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
