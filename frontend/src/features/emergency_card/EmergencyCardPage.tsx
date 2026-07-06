// src/features/emergency_card/EmergencyCardPage.tsx
import { useState, useEffect } from "react";
import { useEmergencyCard, useUpsertEmergencyCard } from "./useEmergencyCard";

const FIELDS: { key: string; label: string; placeholder: string }[] = [
  { key: "blood_type", label: "혈액형", placeholder: "예: A+" },
  { key: "food_allergies", label: "음식 알레르기", placeholder: "예: 복숭아, 밀가루" },
  { key: "medication_allergies", label: "약물 알레르기", placeholder: "예: 페니실린 계열" },
  { key: "past_history", label: "과거 병력", placeholder: "예: 2018년 위암 수술" },
  { key: "present_history", label: "현재 병력", placeholder: "예: 만성 고혈압 복약 중" },
  { key: "emergency_contacts", label: "비상 연락처", placeholder: "예: 아들 김철수 010-1234-5678" },
];

export default function EmergencyCardPage() {
  const { data: card, isLoading } = useEmergencyCard();
  const upsert = useUpsertEmergencyCard();
  const [form, setForm] = useState<Record<string, string>>({});

  // 서버에서 카드를 불러오면 폼 초기값을 채워줍니다.
  useEffect(() => {
    if (card) {
      setForm({
        blood_type: card.blood_type ?? "",
        food_allergies: card.food_allergies ?? "",
        medication_allergies: card.medication_allergies ?? "",
        past_history: card.past_history ?? "",
        present_history: card.present_history ?? "",
        emergency_contacts: card.emergency_contacts ?? "",
      });
    }
  }, [card]);

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-2 text-2xl font-bold">응급 의료 카드</h1>
      <p className="mb-6 text-sm" style={{ color: "var(--text-secondary)" }}>
        응급 상황 시 참고할 수 있는 정보를 미리 등록해두세요.
      </p>

      {isLoading && <p style={{ color: "var(--text-secondary)" }}>불러오는 중...</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          upsert.mutate(form);
        }}
        className="flex flex-col gap-4 rounded-xl border p-5"
        style={{ borderColor: "var(--panel-border)", background: "var(--panel-bg)" }}
      >
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>
              {f.label}
            </label>
            <input
              value={form[f.key] ?? ""}
              placeholder={f.placeholder}
              onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
              className="w-full rounded-lg border bg-transparent px-3 py-2 outline-none"
              style={{ borderColor: "var(--panel-border)" }}
            />
          </div>
        ))}

        {upsert.isSuccess && (
          <p className="text-sm" style={{ color: "var(--accent-green)" }}>저장되었습니다.</p>
        )}

        <button
          type="submit"
          disabled={upsert.isPending}
          className="mt-2 rounded-lg py-2 font-semibold text-black"
          style={{ background: "var(--accent-cyan)" }}
        >
          {upsert.isPending ? "저장 중..." : "저장하기"}
        </button>
      </form>
    </div>
  );
}
