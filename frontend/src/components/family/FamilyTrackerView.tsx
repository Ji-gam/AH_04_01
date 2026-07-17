import { useEffect, useState } from "react";

import {
  familyMedicationApi,
  type FamilyFoodInteractionCheckResult,
  type FamilyInteractionCheckResult,
  type FamilyMedicationScheduleItem,
  type MedicationSearchResult,
} from "../../api/familyMedicationApi";
import { pinkTheme as t } from "../../theme/pinkTheme";

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: `1px solid ${t.border}`,
  borderRadius: "8px",
  fontSize: "14px",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "10px 16px",
  border: "none",
  borderRadius: "8px",
  background: t.primary,
  color: "#fff",
  fontWeight: 600,
  cursor: "pointer",
};

type Tab = "register" | "list" | "interactions" | "food";

// 기본 시간대 매핑 - "1일 N회"는 있는데 정확한 시각(아침/점심/저녁 중 어디인지)까지는
// OCR로 못 잡는 경우가 많아, 흔한 국내 처방 관행(아침/점심/저녁/자기전) 순으로 채운다.
// 사용자가 +/-로 언제든 수동 조정 가능하니, 여기서는 "횟수"만 정확히 맞추는 게 목표다.
const DEFAULT_TIMES_BY_COUNT: Record<number, string[]> = {
  1: ["08:00"],
  2: ["08:00", "19:00"],
  3: ["08:00", "13:00", "19:00"],
  4: ["08:00", "13:00", "19:00", "22:00"],
};

/** OCR 원문에 실제 "08:00" 같은 시:분 숫자가 박혀있는 처방전은 드물고, 대부분
 * "1일 2회"/"1일 3회" 식으로 횟수만 적혀있다(약봉투/조제명세서 관행). 백엔드
 * `_parse_dosage_fields`는 시:분 패턴만 찾으므로(공용 로직이라 여기서는 안 건드림),
 * 프론트에서 OCR 원문을 한 번 더 보고 "N회" 패턴을 찾아 슬롯 개수를 정한다.
 * "N회"도 못 찾으면 안전하게 1칸(사용자가 +로 늘리면 됨)으로 시작한다. */
function deriveTimeSlots(
  extractedFields: { times?: string[]; ocr_raw_text?: string } | null | undefined,
): string[] {
  if (extractedFields?.times && extractedFields.times.length > 0) {
    return extractedFields.times.map((tm) => tm.slice(0, 5));
  }
  const rawText = extractedFields?.ocr_raw_text ?? "";
  const match = rawText.match(/1\s*일\s*(\d+)\s*회/) ?? rawText.match(/(\d+)\s*회/);
  const count = match ? parseInt(match[1], 10) : 0;
  if (count >= 1 && count <= 4) return DEFAULT_TIMES_BY_COUNT[count];
  return ["08:00"];
}

export default function FamilyTrackerView({
  targetProfileId,
  targetName,
}: {
  targetProfileId: number;
  targetName: string;
}) {
  const [tab, setTab] = useState<Tab>("register");

  return (
    <div>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: t.text, margin: "0 0 16px" }}>
        💊 {targetName}님의 복약 관리
      </h2>

      <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
        {(
          [
            ["register", "시간표 / 분석"],
            ["list", "등록 목록"],
            ["interactions", "조합"],
            ["food", "음식"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            style={{
              padding: "8px 14px",
              borderRadius: 999,
              border: `1px solid ${tab === key ? t.primary : t.border}`,
              background: tab === key ? t.primary : t.cardBg,
              color: tab === key ? "#fff" : t.textMuted,
              fontWeight: 600,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "register" && <RegisterTab targetProfileId={targetProfileId} />}
      {tab === "list" && <ListTab targetProfileId={targetProfileId} />}
      {tab === "interactions" && <InteractionsTab targetProfileId={targetProfileId} />}
      {tab === "food" && <FoodTab targetProfileId={targetProfileId} />}
    </div>
  );
}

function RegisterTab({ targetProfileId }: { targetProfileId: number }) {
  const [subTab, setSubTab] = useState<"search" | "photo">("search");

  // 검색 탭 (단일 선택 - 검색은 보통 약 하나를 찾는 용도라 그대로 유지)
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MedicationSearchResult[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<MedicationSearchResult | null>(null);
  const [searchTimesInput, setSearchTimesInput] = useState("08:00");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  // 사진 탭 - 처방전 한 장에서 여러 약이 인식될 수 있으므로 다중 선택(체크박스, 기본 전체
  // 선택)으로 하고, 복용 시간은 "하루 N회" 감지된 슬롯 개수만큼 칸을 만들어서 입력받는다.
  // 약마다 실제 복용 횟수가 다를 수 있지만, 결국 봉지 단위로 같이 복용하는 경우가 많아
  // OCR에서 감지된 최대 슬롯 수 하나를 모든 선택 약품에 공통 적용한다(원본 수동등록 화면의
  // "여러 약 체크박스 + 공용 시간대" 방식과 같은 설계, 시간 입력만 슬롯형으로 바꿈).
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<"uploading" | "processing" | "done" | "failed" | null>(
    null,
  );
  const [candidates, setCandidates] = useState<MedicationSearchResult[]>([]);
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());
  const [timeSlots, setTimeSlots] = useState<string[]>(["08:00"]);

  useEffect(() => {
    if (!jobId || jobStatus !== "processing") return;
    const timer = setInterval(async () => {
      try {
        const status = await familyMedicationApi.getJobStatus(jobId);
        if (status.status === "done" || status.status === "failed") {
          clearInterval(timer);
          setJobStatus(status.status);
          if (status.status === "done") {
            const found = status.candidates.map((c) => ({
              id: 0,
              standard_code: c.drug_code,
              medication_name: c.drug_name,
              form_type: null,
            }));
            setCandidates(found);
            setSelectedCodes(new Set(found.map((c) => c.standard_code))); // 기본 전체 선택

            setTimeSlots(deriveTimeSlots(status.extracted_fields));
          }
        }
      } catch {
        clearInterval(timer);
        setJobStatus("failed");
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [jobId, jobStatus]);

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
    if (!selectedDrug) return;
    setError(null);
    setMessage(null);
    setIsBusy(true);
    try {
      const times = searchTimesInput
        .split(",")
        .map((tm) => tm.trim())
        .filter(Boolean);
      await familyMedicationApi.registerForFamily(
        targetProfileId,
        selectedDrug.standard_code,
        times,
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

  function toggleCandidate(code: string) {
    setSelectedCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function updateSlot(index: number, value: string) {
    setTimeSlots((prev) => prev.map((s, i) => (i === index ? value : s)));
  }

  function addSlot() {
    setTimeSlots((prev) => [...prev, "08:00"]);
  }

  function removeSlot(index: number) {
    setTimeSlots((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev));
  }

  async function handleRegisterSelectedFromPhoto() {
    if (!jobId || selectedCodes.size === 0) return;
    setError(null);
    setMessage(null);
    setIsBusy(true);
    const toRegister = candidates.filter((c) => selectedCodes.has(c.standard_code));
    try {
      for (const candidate of toRegister) {
        await familyMedicationApi.confirmForFamily(
          jobId,
          targetProfileId,
          candidate.standard_code,
          timeSlots,
        );
      }
      setMessage(`선택한 ${toRegister.length}개 약품 등록 완료`);
      setFile(null);
      setJobId(null);
      setJobStatus(null);
      setCandidates([]);
      setSelectedCodes(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "등록에 실패했습니다.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <button
          type="button"
          onClick={() => setSubTab("search")}
          style={{
            flex: 1,
            padding: "8px",
            border: `1px solid ${subTab === "search" ? t.primary : t.border}`,
            borderRadius: 8,
            background: subTab === "search" ? t.primary : t.cardBg,
            color: subTab === "search" ? "#fff" : t.textMuted,
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          검색
        </button>
        <button
          type="button"
          onClick={() => setSubTab("photo")}
          style={{
            flex: 1,
            padding: "8px",
            border: `1px solid ${subTab === "photo" ? t.primary : t.border}`,
            borderRadius: 8,
            background: subTab === "photo" ? t.primary : t.cardBg,
            color: subTab === "photo" ? "#fff" : t.textMuted,
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          사진(처방전)
        </button>
      </div>

      {subTab === "search" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
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
                    border: `1.5px solid ${selectedDrug?.standard_code === r.standard_code ? t.primary : t.border}`,
                    background:
                      selectedDrug?.standard_code === r.standard_code ? t.primary : t.cardBg,
                    color: selectedDrug?.standard_code === r.standard_code ? "#fff" : t.text,
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
                value={searchTimesInput}
                onChange={(e) => setSearchTimesInput(e.target.value)}
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
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
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
              <p style={{ margin: "4px 0 0", fontSize: 12, color: t.textMuted }}>
                의약품 후보 선택 (처방전에 여러 약이 있으면 전부 선택 가능):
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {candidates.map((c) => (
                  <label
                    key={c.standard_code}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 10px",
                      border: `1px solid ${t.border}`,
                      borderRadius: 8,
                      fontSize: 13,
                      color: t.text,
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedCodes.has(c.standard_code)}
                      onChange={() => toggleCandidate(c.standard_code)}
                    />
                    💊 {c.medication_name}
                  </label>
                ))}
              </div>

              <p style={{ margin: "8px 0 0", fontSize: 12, color: t.textMuted }}>
                복용 시간대 설정 (하루 {timeSlots.length}회 - 처방전에서 인식된 횟수 기준, 필요하면
                +/-로 조정):
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {timeSlots.map((slot, idx) => (
                  <div key={idx} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      type="time"
                      value={slot}
                      onChange={(e) => updateSlot(idx, e.target.value)}
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    <button
                      type="button"
                      onClick={() => removeSlot(idx)}
                      disabled={timeSlots.length <= 1}
                      style={{
                        border: `1px solid ${t.border}`,
                        borderRadius: 8,
                        background: t.cardBg,
                        color: t.textMuted,
                        padding: "8px 12px",
                        cursor: "pointer",
                      }}
                    >
                      −
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addSlot}
                  style={{
                    border: `1px dashed ${t.border}`,
                    borderRadius: 8,
                    background: "none",
                    color: t.textMuted,
                    padding: "8px",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  + 시간 추가
                </button>
              </div>

              <button
                type="button"
                onClick={handleRegisterSelectedFromPhoto}
                disabled={isBusy || selectedCodes.size === 0}
                style={{ ...primaryButtonStyle, background: "#22c55e" }}
              >
                선택한 {selectedCodes.size}개 약품 복약 스케줄 등록 확정
              </button>
            </>
          )}
          {jobStatus === "done" && candidates.length === 0 && (
            <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
              인식된 약품이 없어요. 검색 탭을 이용해주세요.
            </p>
          )}
        </div>
      )}

      {message && <p style={{ margin: 0, fontSize: 12, color: t.success }}>{message}</p>}
      {error && <p style={{ margin: 0, fontSize: 12, color: t.danger }}>{error}</p>}
    </div>
  );
}

function ListTab({ targetProfileId }: { targetProfileId: number }) {
  const [items, setItems] = useState<FamilyMedicationScheduleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    familyMedicationApi
      .listForFamily(targetProfileId)
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "목록을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetProfileId]);

  async function handleDelete(item: FamilyMedicationScheduleItem) {
    if (!window.confirm(`"${item.drug_name}" 등록을 삭제할까요?`)) return;
    try {
      await familyMedicationApi.deleteForFamily(item.id);
      load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "삭제에 실패했습니다.");
    }
  }

  if (loading) return <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>;
  if (error) return <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>;
  if (items.length === 0)
    return <p style={{ color: t.textMuted, fontSize: 13 }}>등록된 약이 없어요.</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {items.map((item) => (
        <div
          key={item.id}
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            border: `1px solid ${t.border}`,
            borderRadius: 10,
            padding: "10px 14px",
          }}
        >
          <div>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: t.text }}>
              💊 {item.drug_name}
            </p>
            <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
              {item.times.join(", ")}
              {item.hospital_name ? ` · ${item.hospital_name}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleDelete(item)}
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
        </div>
      ))}
    </div>
  );
}

function InteractionsTab({ targetProfileId }: { targetProfileId: number }) {
  const [result, setResult] = useState<FamilyInteractionCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    familyMedicationApi
      .checkInteractionsForFamily(targetProfileId)
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : "조합 확인에 실패했습니다."))
      .finally(() => setLoading(false));
  }, [targetProfileId]);

  if (loading) return <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>;
  if (error) return <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>;
  if (!result || result.warnings.length === 0) {
    return <p style={{ color: t.textMuted, fontSize: 13 }}>확인된 병용금기가 없어요.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {result.warnings.map((w, idx) => (
        <div
          key={idx}
          style={{
            border: `1px solid ${t.danger}`,
            borderRadius: 10,
            padding: "10px 14px",
            background: "#fff5f5",
          }}
        >
          <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: t.text }}>
            ⚠️ {w.drug_a_name} + {w.drug_b_name}
          </p>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: t.text }}>{w.description}</p>
        </div>
      ))}
    </div>
  );
}

function FoodTab({ targetProfileId }: { targetProfileId: number }) {
  const [result, setResult] = useState<FamilyFoodInteractionCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    familyMedicationApi
      .checkFoodInteractionsForFamily(targetProfileId)
      .then(setResult)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "음식 정보 확인에 실패했습니다."),
      )
      .finally(() => setLoading(false));
  }, [targetProfileId]);

  if (loading) return <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>;
  if (error) return <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>;
  if (!result || result.guide_cards.length === 0) {
    return <p style={{ color: t.textMuted, fontSize: 13 }}>등록된 약이 없어요.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {result.guide_cards.map((card, idx) => (
        <div
          key={idx}
          style={{ border: `1px solid ${t.border}`, borderRadius: 10, padding: "10px 14px" }}
        >
          <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: t.text }}>{card.title}</p>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: t.text }}>{card.content}</p>
        </div>
      ))}
    </div>
  );
}
