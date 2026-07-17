import { useEffect, useState } from "react";

import { familyApi, type FamilyLinkItem } from "../../api/familyApi";
import { pinkTheme as t } from "../../theme/pinkTheme";

/** 화면 제목 옆에 붙는 화살표 - 누르면 "나 + 연결된 가족" 목록이 펼쳐지고, 고르면 그 사람으로
 * 전환된다(참가자 목록 펼침 UI 참고, 2026-07-16). 연결된 가족이 없으면 화살표 자체를 안
 * 보여준다(본인만 쓰는 사람 화면엔 불필요). */
export default function FamilySwitcher({
  selectedProfileId,
  onSelect,
}: {
  selectedProfileId: number | null; // null = "나"
  onSelect: (target: { profileId: number; name: string } | null) => void;
}) {
  const [members, setMembers] = useState<FamilyLinkItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    familyApi
      .list()
      .then((data) => setMembers(data.as_guardian_accepted))
      .catch(() => setMembers([]));
  }, []);

  if (members.length === 0) return null;

  const selectedMember = members.find((m) => m.profile_id === selectedProfileId);
  const currentLabel = selectedMember ? selectedMember.name : "나";

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 12px",
          borderRadius: 999,
          border: `1px solid ${t.border}`,
          background: t.cardBg,
          color: t.text,
          fontSize: 13,
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        👤 {currentLabel} <span style={{ fontSize: 10 }}>{isOpen ? "▲" : "▼"}</span>
      </button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "110%",
            right: 0,
            zIndex: 20,
            minWidth: 200,
            background: t.cardBg,
            border: `1px solid ${t.border}`,
            borderRadius: 12,
            boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
            overflow: "hidden",
          }}
        >
          <button
            type="button"
            onClick={() => {
              onSelect(null);
              setIsOpen(false);
            }}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              border: "none",
              background: selectedProfileId === null ? t.primarySoft : "transparent",
              color: t.text,
              fontSize: 14,
              textAlign: "left",
              cursor: "pointer",
            }}
          >
            🙋 나
          </button>
          {members.map((m) => (
            <button
              key={m.link_id}
              type="button"
              onClick={() => {
                onSelect({ profileId: m.profile_id, name: m.name });
                setIsOpen(false);
              }}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 14px",
                border: "none",
                borderTop: `1px solid ${t.border}`,
                background: selectedProfileId === m.profile_id ? t.primarySoft : "transparent",
                color: t.text,
                fontSize: 14,
                textAlign: "left",
                cursor: "pointer",
              }}
            >
              👨‍👩‍👧 {m.name} ({m.relation_label})
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
