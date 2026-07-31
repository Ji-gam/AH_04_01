import { Moon } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import PageTitle from "../../components/common/PageTitle";
import { pinkTheme as t } from "../../theme/pinkTheme";

import TimeSelectSection from "./TimeSelectSection";

/** 각 항목의 값: null(미선택) | "NONE"(해당없음) | "HH:MM". localStorage에 이 형태 그대로 저장한다. */
interface LifestyleInfo {
  wakeUp: string | null;
  breakfast: string | null;
  lunch: string | null;
  dinner: string | null;
  bedtime: string | null;
}

const STORAGE_KEY = "lifestyleInfo";

const SECTIONS = [
  {
    key: "wakeUp",
    label: "기상 시간",
    help: "약을 먹기 좋은 아침 시간대를 알려주세요",
    options: ["05:00", "06:00", "07:00"],
    customDefault: "06:30",
  },
  {
    key: "breakfast",
    label: "아침 식사",
    help: "약 복용과 식사 타이밍을 맞춰주세요 (식후/식전)",
    options: ["07:00", "08:00", "09:00"],
    customDefault: "08:30",
  },
  {
    key: "lunch",
    label: "점심 식사",
    help: "약 복용과 식사 타이밍을 맞춰주세요 (식후/식전)",
    options: ["12:00", "13:00", "14:00"],
    customDefault: "12:30",
  },
  {
    key: "dinner",
    label: "저녁 식사",
    help: "약 복용과 식사 타이밍을 맞춰주세요 (식후/식전)",
    options: ["18:00", "19:00", "20:00"],
    customDefault: "19:30",
  },
  {
    key: "bedtime",
    label: "취침 시간",
    help: "숙면과 복약 리듬을 위한 취침 시간을 알려주세요",
    options: ["22:00", "23:00", "24:00"],
    customDefault: "23:30",
  },
] as const satisfies readonly {
  key: keyof LifestyleInfo;
  label: string;
  help: string;
  options: string[];
  customDefault: string;
}[];

function loadInfo(): LifestyleInfo {
  const empty: LifestyleInfo = {
    wakeUp: null,
    breakfast: null,
    lunch: null,
    dinner: null,
    bedtime: null,
  };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...empty, ...(JSON.parse(raw) as Partial<LifestyleInfo>) } : empty;
  } catch {
    return empty;
  }
}

export default function LifestyleInfoPage() {
  const navigate = useNavigate();
  const [info, setInfo] = useState<LifestyleInfo>(() => loadInfo());
  const [saved, setSaved] = useState(false);

  const update = (key: keyof LifestyleInfo, value: string | null) => {
    setInfo((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(info));
    setSaved(true);
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
        <PageTitle icon={Moon} style={{ marginBottom: 6 }}>
          생활습관 정보
        </PageTitle>

        <p style={{ margin: "0 0 20px", fontSize: 13, color: t.textMuted, lineHeight: 1.5 }}>
          복약 효과를 높이기 위한 생활습관을 설정해주세요.
        </p>

        {SECTIONS.map((section) => (
          <TimeSelectSection
            key={section.key}
            label={section.label}
            help={section.help}
            options={section.options}
            customDefault={section.customDefault}
            value={info[section.key]}
            onChange={(v) => update(section.key, v)}
          />
        ))}

        <button
          type="button"
          onClick={handleSave}
          style={{
            width: "100%",
            padding: "14px 0",
            marginTop: 8,
            borderRadius: 10,
            border: "none",
            background: t.primary,
            color: "#fff",
            fontSize: 15,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          저장
        </button>

        {saved && (
          <p style={{ margin: "10px 0 0", fontSize: 13, color: t.success, textAlign: "center" }}>
            ✓ 저장되었습니다.
          </p>
        )}
      </div>
    </div>
  );
}
