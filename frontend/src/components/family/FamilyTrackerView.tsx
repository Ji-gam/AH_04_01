import { useEffect, useState } from "react";

import {
  familyMedicationApi,
  type FamilyFoodInteractionCheckResult,
  type FamilyInteractionCheckResult,
  type FamilyMedicationScheduleItem,
  type MedicationSearchResult,
} from "../../api/familyMedicationApi";
import { pinkTheme as t } from "../../theme/pinkTheme";

import FamilyOcrProgressBar from "./FamilyOcrProgressBar";
import FamilyTimeSlotRow from "./FamilyTimeSlotRow";

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

/** 하루 복용 횟수 선택지 - 본인 몫 복약알림(AlarmForm)과 같은 임상 표기 규칙을 따른다.
 * OCR로 인식된 횟수를 기본값으로 쓰되(deriveTimeSlots), 인식이 잘 안 됐을 때 사용자가
 * 수동으로 바꿀 수 있게 버튼으로 노출한다(2026-07-21, "+ 시간 추가" 방식은 인식이 잘못됐을
 * 때 몇 번을 눌러야 할지 감이 안 온다는 피드백으로 교체). */
const DOSE_COUNT_OPTIONS = [
  { count: 1, label: "1회 (qd)" },
  { count: 2, label: "2회 (bid)" },
  { count: 3, label: "3회 (tid)" },
  { count: 4, label: "4회 (qid)" },
] as const;

const DEFAULT_TIMES_BY_COUNT: Record<number, string[]> = {
  1: ["08:00"],
  2: ["08:00", "19:00"],
  3: ["08:00", "13:00", "19:00"],
  4: ["08:00", "13:00", "19:00", "22:00"],
};

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

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MedicationSearchResult[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<MedicationSearchResult | null>(null);
  // [2026-07-21] 쉼표구분 텍스트 입력 → 사진탭과 같은 오전/오후+복용횟수 스타일로 통일.
  // 검색 등록은 OCR 인식이 없어 기본값은 그냥 1회로 시작한다.
  const [searchTimeSlots, setSearchTimeSlots] = useState<string[]>(["08:00"]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

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
            // RecognitionCandidate.drug_code는 (T-MED-16 기준) 이미 item_seq 값을 담고
            // 있어서 그대로 옮겨 쓰면 된다 - 검색 결과(MedicationSearchResult)와 달리 이
            // 경로는 원래부터 필드명 버그가 없었다.
            const found = status.candidates.map((c) => ({
              item_seq: c.drug_code,
              medication_name: c.drug_name,
            }));
            setCandidates(found);
            setSelectedCodes(new Set(found.map((c) => c.item_seq)));

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
      await familyMedicationApi.registerForFamily(
        targetProfileId,
        selectedDrug.item_seq,
        searchTimeSlots,
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

  // 이미 입력/인식된 시각은 유지하고, 늘어나거나 줄어든 칸만 기본 시각으로 채우거나 잘라낸다
  // (AlarmForm의 handleDoseCountChange와 같은 패턴).
  function handleDoseCountChange(count: number) {
    setTimeSlots((prev) =>
      Array.from({ length: count }, (_, i) => prev[i] ?? DEFAULT_TIMES_BY_COUNT[count][i]),
    );
  }

  function updateSearchSlot(index: number, value: string) {
    setSearchTimeSlots((prev) => prev.map((s, i) => (i === index ? value : s)));
  }

  function handleSearchDoseCountChange(count: number) {
    setSearchTimeSlots((prev) =>
      Array.from({ length: count }, (_, i) => prev[i] ?? DEFAULT_TIMES_BY_COUNT[count][i]),
    );
  }

  async function handleRegisterSelectedFromPhoto() {
    if (!jobId || selectedCodes.size === 0) return;
    setError(null);
    setMessage(null);
    setIsBusy(true);
    const toRegister = candidates.filter((c) => selectedCodes.has(c.item_seq));
    try {
      // (#195) 본인 몫 등록(MedicationPage.handleConfirmSubmit)과 같은 이유로, 약품 개수만큼
      // confirm 요청을 순차 대기하지 않고 병렬로 보낸다.
      await Promise.all(
        toRegister.map((candidate) =>
          familyMedicationApi.confirmForFamily(
            jobId,
            targetProfileId,
            candidate.item_seq,
            timeSlots,
          ),
        ),
      );
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
                  key={r.item_seq}
                  type="button"
                  onClick={() => setSelectedDrug(r)}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 999,
                    border: `1.5px solid ${selectedDrug?.item_seq === r.item_seq ? t.primary : t.border}`,
                    background: selectedDrug?.item_seq === r.item_seq ? t.primary : t.cardBg,
                    color: selectedDrug?.item_seq === r.item_seq ? "#fff" : t.text,
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
              <p style={{ margin: "4px 0 0", fontSize: 12, color: t.textMuted }}>하루 복용 횟수:</p>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {DOSE_COUNT_OPTIONS.map((opt) => (
                  <button
                    key={opt.count}
                    type="button"
                    onClick={() => handleSearchDoseCountChange(opt.count)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: 999,
                      border: `1px solid ${t.border}`,
                      background: searchTimeSlots.length === opt.count ? t.primary : "white",
                      color: searchTimeSlots.length === opt.count ? "white" : t.text,
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {searchTimeSlots.map((slot, idx) => (
                  <FamilyTimeSlotRow
                    key={idx}
                    value={slot}
                    onChange={(v) => updateSearchSlot(idx, v)}
                  />
                ))}
              </div>
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

          {(jobStatus === "uploading" || jobStatus === "processing") && (
            <div style={{ padding: "12px 4px 4px" }}>
              <FamilyOcrProgressBar status={jobStatus} />
            </div>
          )}

          {jobStatus === "done" && candidates.length > 0 && (
            <>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: t.textMuted }}>
                의약품 후보 선택 (처방전에 여러 약이 있으면 전부 선택 가능):
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {candidates.map((c) => (
                  <label
                    key={c.item_seq}
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
                      checked={selectedCodes.has(c.item_seq)}
                      onChange={() => toggleCandidate(c.item_seq)}
                    />
                    💊 {c.medication_name}
                  </label>
                ))}
              </div>

              <p style={{ margin: "8px 0 0", fontSize: 12, color: t.textMuted }}>
                하루 복용 횟수 (처방전에서 인식된 횟수가 기본값으로 선택돼요 - 인식이 잘못됐으면
                직접 눌러서 바꿔주세요):
              </p>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {DOSE_COUNT_OPTIONS.map((opt) => (
                  <button
                    key={opt.count}
                    type="button"
                    onClick={() => handleDoseCountChange(opt.count)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: 999,
                      border: `1px solid ${t.border}`,
                      background: timeSlots.length === opt.count ? t.primary : "white",
                      color: timeSlots.length === opt.count ? "white" : t.text,
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {timeSlots.map((slot, idx) => (
                  <FamilyTimeSlotRow key={idx} value={slot} onChange={(v) => updateSlot(idx, v)} />
                ))}
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
