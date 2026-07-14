import { useEffect, useRef, useState } from "react";

import { diseaseApi } from "../../api/diseaseApi";
import type { Disease, DiseaseSubtypeSearchResult } from "../../api/types";
import { pinkTheme } from "../../theme/pinkTheme";

interface Props {
  category: Disease;
  value: string | null;
  onChange: (value: string | null) => void;
}

/** "구체적 질환명" 입력칸. 타이핑하는 대로 서버에 검색해서 기존에 등록된 이름을 보여준다(디바운스 300ms).
 * 목록에서 고르면 그 이름 그대로 선택되고, 목록에 없는 이름을 그냥 입력해도 그대로 값으로 쓸 수 있다
 * (그 값은 저장 시점에 서버가 자동으로 새 항목으로 등록한다 - get_or_create). */
export default function DiseaseSubtypeSearchInput({ category, value, onChange }: Props) {
  const [query, setQuery] = useState(value ?? "");
  const [results, setResults] = useState<DiseaseSubtypeSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setQuery(value ?? "");
  }, [value]);

  function handleInputChange(text: string) {
    setQuery(text);
    onChange(text || null);
    setIsOpen(true);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const found = await diseaseApi.searchSubtypes(category, text);
        setResults(found);
      } catch {
        setResults([]);
      }
    }, 300);
  }

  function handleSelect(name: string) {
    setQuery(name);
    onChange(name);
    setIsOpen(false);
  }

  return (
    <div style={{ position: "relative" }}>
      <input
        type="text"
        placeholder="구체적 질환명 검색 (선택, 예: 폐암)"
        value={query}
        onChange={(e) => handleInputChange(e.target.value)}
        onFocus={() => handleInputChange(query)}
        onBlur={() => setTimeout(() => setIsOpen(false), 150)}
        maxLength={50}
        style={{
          width: "100%",
          padding: "6px 10px",
          border: `1px solid ${pinkTheme.border}`,
          borderRadius: "6px",
          fontSize: 13,
          boxSizing: "border-box",
        }}
      />
      {isOpen && results.length > 0 && (
        <ul
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 10,
            margin: "2px 0 0",
            padding: "4px 0",
            listStyle: "none",
            background: "#fff",
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: "6px",
            maxHeight: 160,
            overflowY: "auto",
            boxShadow: "0 4px 10px rgba(0,0,0,0.08)",
          }}
        >
          {results.map((r) => (
            <li key={r.name}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(r.name)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "6px 10px",
                  border: "none",
                  background: "none",
                  fontSize: 13,
                  color: pinkTheme.text,
                  cursor: "pointer",
                }}
              >
                {r.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
