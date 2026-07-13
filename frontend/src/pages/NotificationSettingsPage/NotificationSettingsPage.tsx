import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { pinkTheme as t } from "../../theme/pinkTheme";
import ToggleSwitch from "../AlarmPage/components/ToggleSwitch";

/** localStorage에 이 형태 그대로 저장한다 — 백엔드 알림설정 도메인이 생기면 연동 예정. */
interface NotificationSettings {
  pushEnabled: boolean;
  chatbotReplyEnabled: boolean;
  noticeEnabled: boolean;
  marketingEnabled: boolean;
  quietModeEnabled: boolean;
  quietStart: string;
  quietEnd: string;
  soundEnabled: boolean;
  vibrationEnabled: boolean;
  popupEnabled: boolean;
}

const STORAGE_KEY = "notificationSettings";

const DEFAULT_SETTINGS: NotificationSettings = {
  pushEnabled: true,
  chatbotReplyEnabled: true,
  noticeEnabled: false,
  marketingEnabled: false,
  quietModeEnabled: true,
  quietStart: "22:00",
  quietEnd: "07:00",
  soundEnabled: true,
  vibrationEnabled: true,
  popupEnabled: true,
};

function loadSettings(): NotificationSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<NotificationSettings>) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

/** 스피커 없이 짧게 "삐" 소리를 내는 테스트용 비프음 (오디오 파일 없이 Web Audio로 생성). */
function playTestBeep() {
  const AudioContextClass =
    window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
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

const timeInputStyle: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: 10,
  border: `1px solid ${t.border}`,
  outline: "none",
  fontSize: 14,
  color: t.text,
  background: "#fff",
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
  const [settings, setSettings] = useState<NotificationSettings>(() => loadSettings());
  const [testStatus, setTestStatus] = useState<string | null>(null);

  const update = <K extends keyof NotificationSettings>(key: K, value: NotificationSettings[K]) => {
    const next = { ...settings, [key]: value };
    setSettings(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setTestStatus(null);
  };

  const toggle = (key: keyof NotificationSettings) => update(key, !settings[key] as never);

  const handleSendTest = async () => {
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
    if (settings.popupEnabled) {
      new Notification("🔔 테스트 알림", { body: "설정하신 알림이 이렇게 도착해요." });
    }
    if (settings.soundEnabled) {
      playTestBeep();
    }
    if (settings.vibrationEnabled && navigator.vibrate) {
      navigator.vibrate(200);
    }
    setTestStatus("✓ 테스트 알림을 보냈어요.");
  };

  return (
    <div style={{ background: t.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <button
            type="button"
            aria-label="뒤로"
            onClick={() => navigate("/more")}
            style={{ border: "none", background: "none", color: t.text, fontSize: 20, cursor: "pointer", lineHeight: 1 }}
          >
            ←
          </button>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: t.text, margin: 0 }}>🔔 알림설정</h1>
        </div>

        <p style={{ margin: "0 0 12px", fontSize: 13, color: t.textMuted, lineHeight: 1.5 }}>
          받고 싶은 알림과 무음 시간대를 설정해주세요.
        </p>

        <ToggleRow
          label="복약알림 푸시"
          desc="복약 시간에 맞춰 푸시 알림을 받습니다"
          checked={settings.pushEnabled}
          onChange={() => toggle("pushEnabled")}
        />
        <ToggleRow
          label="AI챗봇 답변 알림"
          desc="AI챗봇 상담 답변이 도착하면 알려드려요"
          checked={settings.chatbotReplyEnabled}
          onChange={() => toggle("chatbotReplyEnabled")}
        />
        <ToggleRow
          label="공지사항 알림"
          desc="서비스 공지사항 및 업데이트 소식을 알려드려요"
          checked={settings.noticeEnabled}
          onChange={() => toggle("noticeEnabled")}
        />
        <ToggleRow
          label="마케팅 알림"
          desc="이벤트 및 혜택 정보를 알려드려요"
          checked={settings.marketingEnabled}
          onChange={() => toggle("marketingEnabled")}
        />

        <p style={sectionTitleStyle}>무음 시간대</p>
        <ToggleRow
          label="무음 모드"
          desc="설정한 시간대에는 알림 소리 없이 무음으로 받아요"
          checked={settings.quietModeEnabled}
          onChange={() => toggle("quietModeEnabled")}
        />
        {settings.quietModeEnabled && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 0", borderBottom: `1px solid ${t.border}` }}>
            <input
              type="time"
              aria-label="무음 시작 시간"
              value={settings.quietStart}
              onChange={(e) => update("quietStart", e.target.value)}
              style={timeInputStyle}
            />
            <span style={{ color: t.textMuted, fontSize: 13 }}>~</span>
            <input
              type="time"
              aria-label="무음 종료 시간"
              value={settings.quietEnd}
              onChange={(e) => update("quietEnd", e.target.value)}
              style={timeInputStyle}
            />
          </div>
        )}

        <p style={sectionTitleStyle}>알림 강도</p>
        <ToggleRow
          label="소리"
          desc="알림이 올 때 소리를 재생해요"
          checked={settings.soundEnabled}
          onChange={() => toggle("soundEnabled")}
        />
        <ToggleRow
          label="진동"
          desc="알림이 올 때 진동으로 알려드려요 (진동 지원 기기)"
          checked={settings.vibrationEnabled}
          onChange={() => toggle("vibrationEnabled")}
        />
        <ToggleRow
          label="팝업"
          desc="알림이 올 때 화면에 팝업으로 보여드려요"
          checked={settings.popupEnabled}
          onChange={() => toggle("popupEnabled")}
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
          <p style={{ margin: "10px 0 0", fontSize: 13, color: t.textMuted, textAlign: "center" }}>{testStatus}</p>
        )}
      </div>
    </div>
  );
}
