import { useEffect, useState } from "react";

import { familyApi, type FamilyLinkItem } from "../../api/familyApi";
import { familyMedicationApi, type MedicationSearchResult } from "../../api/familyMedicationApi";
import { pinkTheme } from "../../theme/pinkTheme";

const inputStyle: React.CSSProperties = {
  padding: "8px 10px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "8px",
  fontSize: "13px",
  outline: "none",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "8px 14px",
  border: "none",
  borderRadius: "8px",
  background: pinkTheme.primary,
  color: "#fff",
  fontWeight: 600,
  fontSize: 13,
  cursor: "pointer",
};

/** 트랙커(복약 관리) 화면에 얹는 "가족 몫으로 등록" 섹션. 기존 등록 화면(본인 몫,
 * quick-register/OCR)은 전혀 안 건드리고, 완전히 독립된 섹션으로 최상단에 하나만 추가한다
 * - MedicationPage.tsx 쪽 변경은 이 컴포넌트를 import해서 렌더링하는 한 줄뿐이다
 * (2026-07-16, 가족관리 화면에 있던 등록 기능을 여기로 옮김 - 결정 배경은
 * docs/decision_log/2026-07-16-family-medication-registration-duplication.md 참고).
 *
 * 연결된 가족이 없으면 아예 아무것도 안 보여준다(본인만 쓰는 사람 화면엔 불필요한 UI). */
export default function FamilyRegisterSection() {
  const [members, setMembers] = useState<FamilyLinkItem[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);

  const [tab, setTab] = useState<"search" | "photo">("search");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MedicationSearchResult[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<MedicationSearchResult | null>(null);
  const [timesInput, setTimesInput] = useState("08:00");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<"uploading" | "processing" | "done" | "failed" | null>(
    null,
  );
  const [candidates, setCandidates] = useState<MedicationSearchResult[]>([]);

  useEffect(() => {
    familyApi
      .list()
      .then((data) => setMembers(data.as_guardian_accepted))
      .catch(() => setMembers([]));
  }, []);

  useEffect(() => {
    if (!jobId || jobStatus !== "processing") return;
    const timer = setInterval(async () => {
      try {
        const status = await familyMedicationApi.getJobStatus(jobId);
        if (status.status === "done" || status.status === "failed") {
          clearInterval(timer);
          setJobStatus(status.status);
          if (status.status === "done") {
            setCandidates(
              status.candidates.map((c) => ({
                id: 0,
                standard_code: c.drug_code,
                medication_name: c.drug_name,
                form_type: null,
              })),
            );
            if (status.extracted_fields?.times?.length) {
              setTimesInput(status.extracted_fields.times.join(","));
            }
          }
        }
      } catch {
        clearInterval(timer);
        setJobStatus("failed");
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [jobId, jobStatus]);

  if (members.length === 0) return null;

  function parseTimes(): string[] {
    return timesInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
  }

  async function handleSearch() {
    setError(null);
    setIsBusy(true);
    try {
      setResults(await familyMedicationApi.search(query.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "검색에 실패했습니다.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRegisterFromSearch() {
    if (!selectedDrug || !selectedProfileId) return;
    setError(null);
    setMessage(null);
    setIsBusy(true);
    try {
      await familyMedicationApi.registerForFamily(
        selectedProfileId,
        selectedDrug.standard_code,
        parseTimes(),
      );
      setMessage(`${selectedDrug.medication_name} 등록 완료`);
      setSelectedDrug(null);
      setQuery("");
      setResults([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "등록에 실패했습니다.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleUpload() {
    if (!file) return;
    setError(null);
    setJobStatus("uploading");
    try {
      const newJobId = await familyMedicationApi.uploadJob(file);
      setJobId(newJobId);
      setJobStatus("processing");
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드에 실패했습니다.");
      setJobStatus(null);
    }
  }

  async function handleRegisterFromPhoto(candidate: MedicationSearchResult) {
    if (!jobId || !selectedProfileId) return;
    setError(null);
    setMessage(null);
    setIsBusy(true);
    try {
      await familyMedicationApi.confirmForFamily(
        jobId,
        selectedProfileId,
        candidate.standard_code,
        parseTimes(),
      );
      setMessage(`${candidate.medication_name} 등록 완료`);
      setFile(null);
      setJobId(null);
      setJobStatus(null);
      setCandidates([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "등록에 실패했습니다.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div
      style={{
        border: `1.5px solid ${pinkTheme.primary}`,
        borderRadius: 10,
        padding: "12px 15px",
        marginBottom: "15px",
        background: pinkTheme.primarySoft,
      }}
    >
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          border: "none",
          background: "none",
          padding: 0,
          cursor: "pointer",
          fontWeight: 700,
          fontSize: 14,
          color: pinkTheme.primary,
        }}
      >
        <span>👨‍👩‍👧 가족 몫으로 등록</span>
        <span>{isExpanded ? "▲" : "▼"}</span>
      </button>

      {isExpanded && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {members.map((m) => (
              <button
                key={m.link_id}
                type="button"
                onClick={() => setSelectedProfileId(m.profile_id)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 999,
                  border: `1.5px solid ${selectedProfileId === m.profile_id ? pinkTheme.primary : pinkTheme.border}`,
                  background:
                    selectedProfileId === m.profile_id ? pinkTheme.primary : pinkTheme.cardBg,
                  color: selectedProfileId === m.profile_id ? "#fff" : pinkTheme.text,
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                {m.name} ({m.relation_label})
              </button>
            ))}
          </div>

          {selectedProfileId && (
            <>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="button"
                  onClick={() => setTab("search")}
                  style={{
                    flex: 1,
                    padding: "6px",
                    border: `1px solid ${tab === "search" ? pinkTheme.primary : pinkTheme.border}`,
                    borderRadius: 8,
                    background: tab === "search" ? pinkTheme.primary : pinkTheme.cardBg,
                    color: tab === "search" ? "#fff" : pinkTheme.textMuted,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  검색
                </button>
                <button
                  type="button"
                  onClick={() => setTab("photo")}
                  style={{
                    flex: 1,
                    padding: "6px",
                    border: `1px solid ${tab === "photo" ? pinkTheme.primary : pinkTheme.border}`,
                    borderRadius: 8,
                    background: tab === "photo" ? pinkTheme.primary : pinkTheme.cardBg,
                    color: tab === "photo" ? "#fff" : pinkTheme.textMuted,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  사진(처방전)
                </button>
              </div>

              {tab === "search" ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ display: "flex", gap: 6 }}>
                    <input
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="약품명 검색"
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    <button
                      type="button"
                      onClick={handleSearch}
                      disabled={isBusy || !query.trim()}
                      style={primaryButtonStyle}
                    >
                      검색
                    </button>
                  </div>
                  {results.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {results.map((r) => (
                        <button
                          key={r.standard_code}
                          type="button"
                          onClick={() => setSelectedDrug(r)}
                          style={{
                            padding: "6px 10px",
                            borderRadius: 999,
                            border: `1.5px solid ${selectedDrug?.standard_code === r.standard_code ? pinkTheme.primary : pinkTheme.border}`,
                            background:
                              selectedDrug?.standard_code === r.standard_code
                                ? pinkTheme.primary
                                : pinkTheme.cardBg,
                            color:
                              selectedDrug?.standard_code === r.standard_code
                                ? "#fff"
                                : pinkTheme.text,
                            fontSize: 12,
                            cursor: "pointer",
                          }}
                        >
                          {r.medication_name}
                        </button>
                      ))}
                    </div>
                  )}
                  {selectedDrug && (
                    <>
                      <input
                        type="text"
                        value={timesInput}
                        onChange={(e) => setTimesInput(e.target.value)}
                        placeholder="복용시간, 쉼표로 구분 (예: 08:00,19:00)"
                        style={inputStyle}
                      />
                      <button
                        type="button"
                        onClick={handleRegisterFromSearch}
                        disabled={isBusy}
                        style={primaryButtonStyle}
                      >
                        {selectedDrug.medication_name} 등록하기
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    style={{ fontSize: 12 }}
                  />
                  <button
                    type="button"
                    onClick={handleUpload}
                    disabled={!file || jobStatus === "uploading" || jobStatus === "processing"}
                    style={primaryButtonStyle}
                  >
                    {jobStatus === "uploading" || jobStatus === "processing"
                      ? "인식 중..."
                      : "업로드 및 인식"}
                  </button>
                  {jobStatus === "done" && candidates.length > 0 && (
                    <>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {candidates.map((c) => (
                          <button
                            key={c.standard_code}
                            type="button"
                            onClick={() => handleRegisterFromPhoto(c)}
                            disabled={isBusy}
                            style={{
                              padding: "6px 10px",
                              borderRadius: 999,
                              border: `1.5px solid ${pinkTheme.border}`,
                              background: pinkTheme.cardBg,
                              color: pinkTheme.text,
                              fontSize: 12,
                              cursor: "pointer",
                            }}
                          >
                            {c.medication_name}
                          </button>
                        ))}
                      </div>
                      <input
                        type="text"
                        value={timesInput}
                        onChange={(e) => setTimesInput(e.target.value)}
                        placeholder="복용시간, 쉼표로 구분 (예: 08:00,19:00)"
                        style={inputStyle}
                      />
                    </>
                  )}
                  {jobStatus === "done" && candidates.length === 0 && (
                    <p style={{ margin: 0, fontSize: 12, color: pinkTheme.textMuted }}>
                      인식된 약품이 없어요. 검색 탭을 이용해주세요.
                    </p>
                  )}
                </div>
              )}
            </>
          )}

          {message && (
            <p style={{ margin: 0, fontSize: 12, color: pinkTheme.success }}>{message}</p>
          )}
          {error && <p style={{ margin: 0, fontSize: 12, color: pinkTheme.danger }}>{error}</p>}
        </div>
      )}
    </div>
  );
}
