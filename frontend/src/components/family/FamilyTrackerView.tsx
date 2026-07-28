import { useEffect, useRef, useState } from "react";

import {
  familyMedicationApi,
  type FamilyFoodInteractionCheckResult,
  type FamilyFoodItem,
  type FamilyMedicationScheduleItem,
  type MedicationSearchResult,
} from "../../api/familyMedicationApi";
import { durApi } from "../../api/durApi";
import type {
  DurBasicScreeningResult,
  DurIngredientDetail,
  DurIngredientScreeningResponse,
  DurInteractionScreeningResponse,
  DurInteractionWarning,
  DurRecallInfo,
} from "../../api/types";
import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme as t } from "../../theme/pinkTheme";
import { isUnverifiedDrug } from "../../utils/medication";
import OcrFullscreenOverlay from "../ui/OcrFullscreenOverlay";
import TimeInputField from "../ui/TimeInputField";

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: `1px solid ${t.border}`,
  borderRadius: 10,
  fontSize: "14px",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "10px 16px",
  border: "none",
  borderRadius: 10,
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
  { count: 1, label: "1회" },
  { count: 2, label: "2회" },
  { count: 3, label: "3회" },
  { count: 4, label: "4회" },
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
      {/* [2026-07-27] 제목(<h2>)은 MedicationPage.tsx의 가족화면 래퍼로 옮겼다 - 본인
        화면과 헤더 배치(뒤로가기 단독 줄 → 제목+FamilySwitcher 줄)를 통일하기 위함.
        여기서 targetName은 이제 아래 탭 콘텐츠에서만 쓰인다(직접 쓰이는 곳 없으면
        ESLint가 미사용 경고를 낼 수 있음 - 아래 탭 컴포넌트들에 넘겨줄 뿐 여기선 안 씀). */}
      <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
        {(
          [
            ["register", "시간표 / 분석"],
            ["list", "등록 목록"],
            ["interactions", "약품 궁합"],
            ["food", "음식 궁합"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            style={{
              flex: 1,
              padding: "9px 4px",
              borderRadius: 10,
              border: tab === key ? "none" : `1px solid ${t.border}`,
              background: tab === key ? t.primary : t.cardBg,
              color: tab === key ? "#fff" : t.text,
              fontWeight: 700,
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
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedDrug, setSelectedDrug] = useState<MedicationSearchResult | null>(null);
  // (2026-07-27) 본인용(MedicationPage.tsx)엔 있는데 가족용엔 아예 없던 DUR 주의사항
  // 표시 - 등록 확정 전에 미리 임부금기/노인주의 등 pill과, 후보끼리의 병용금기
  // 상호작용을 보여준다. 검색결과/사진인식후보 둘 다 같은 로직이라 상태만 따로 둔다.
  const [searchDurByName, setSearchDurByName] = useState<Record<string, DurBasicScreeningResult>>(
    {},
  );
  const [searchDurUnmatched, setSearchDurUnmatched] = useState<string[]>([]);
  const [searchDurLoading, setSearchDurLoading] = useState(false);
  // [2026-07-21] 쉼표구분 텍스트 입력 → 사진탭과 같은 오전/오후+복용횟수 스타일로 통일.
  // 검색 등록은 OCR 인식이 없어 기본값은 그냥 1회로 시작한다.
  const [searchTimeSlots, setSearchTimeSlots] = useState<string[]>(["08:00"]);
  // (2026-07-27) 본인용(MedicationPage.tsx)엔 있는데 가족용엔 빠져있던 필드 - API
  // 클라이언트(familyMedicationApi.registerForFamily/quickRegisterForFamily)는 이미
  // hospitalName 인자를 지원하는데, 여기서 값 자체를 안 만들고 안 넘기고 있었다.
  const [hospitalName, setHospitalName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  // 카메라 촬영/갤러리 선택을 각각 별도 버튼으로 분리한다 - <input capture>는 브라우저에
  // 따라 "카메라만" 강제로 열려버려서, 하나의 input만 쓰면 갤러리에서 고르는 게 아예
  // 안 되는 경우가 있다(2026-07-21, PWA 모바일 테스트 중 발견).
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<"uploading" | "processing" | "done" | "failed" | null>(
    null,
  );
  const [candidates, setCandidates] = useState<MedicationSearchResult[]>([]);
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());
  const [candidateDurByName, setCandidateDurByName] = useState<
    Record<string, DurBasicScreeningResult>
  >({});
  const [candidateDurUnmatched, setCandidateDurUnmatched] = useState<string[]>([]);
  const [candidateDurLoading, setCandidateDurLoading] = useState(false);
  const [candidateDurInteractions, setCandidateDurInteractions] =
    useState<DurInteractionScreeningResponse | null>(null);
  const [timeSlots, setTimeSlots] = useState<string[]>(["08:00"]);

  // (2026-07-27) 검색 결과가 나오면 본인용과 동일하게 미리 DUR 주의사항을 확인한다.
  useEffect(() => {
    if (results.length === 0) {
      setSearchDurByName({});
      setSearchDurUnmatched([]);
      return;
    }
    const names = results.map((r) => r.medication_name);
    setSearchDurLoading(true);
    durApi
      .screenBasic(names)
      .then((basic) => {
        const byName: Record<string, DurBasicScreeningResult> = {};
        basic.results.forEach((r) => {
          byName[r.queried_name] = r;
        });
        setSearchDurByName(byName);
        setSearchDurUnmatched(basic.unmatched_drug_names);
      })
      .catch((err) => console.error(err))
      .finally(() => setSearchDurLoading(false));
  }, [results]);

  // 사진 인식 후보도 동일하게 - 여러 개면 서로간의 병용금기 상호작용까지 같이 확인한다.
  useEffect(() => {
    if (candidates.length === 0) {
      setCandidateDurByName({});
      setCandidateDurUnmatched([]);
      setCandidateDurInteractions(null);
      return;
    }
    const names = candidates.map((c) => c.medication_name);
    setCandidateDurLoading(true);
    Promise.all([durApi.screenBasic(names), durApi.screenInteraction(names)])
      .then(([basic, interaction]) => {
        const byName: Record<string, DurBasicScreeningResult> = {};
        basic.results.forEach((r) => {
          byName[r.queried_name] = r;
        });
        setCandidateDurByName(byName);
        setCandidateDurUnmatched(basic.unmatched_drug_names);
        setCandidateDurInteractions(interaction);
      })
      .catch((err) => console.error(err))
      .finally(() => setCandidateDurLoading(false));
  }, [candidates]);

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
      setHasSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "검색에 실패했습니다.");
    } finally {
      setIsBusy(false);
    }
  }

  // 검색해도 원하는 약이 없을 때 - 입력한 이름 그대로 등록한다(T-MED-3 자동생성 정책을 가족
  // 몫에도 동일 적용). OCR 인식이 틀렸을 때도 "검색 탭에서 다른 약 등록하기"로 넘어와 이
  // 경로를 함께 쓴다.
  async function handleQuickRegisterFromSearch() {
    if (!query.trim()) return;
    setError(null);
    setMessage(null);
    setIsBusy(true);
    try {
      const res = await familyMedicationApi.quickRegisterForFamily(
        targetProfileId,
        query.trim(),
        searchTimeSlots,
        hospitalName.trim() || null,
      );
      if (res.status === "registered") {
        setMessage(
          res.auto_created
            ? `"${res.schedule?.drug_name}"이(가) 마스터 DB에 없어 새로 등록했습니다. 이 약은 상호작용(병용금기) 검사가 제공되지 않습니다.`
            : `${res.schedule?.drug_name} 등록 완료`,
        );
        setQuery("");
        setResults([]);
        setHasSearched(false);
        setHospitalName("");
      } else {
        setResults(
          res.candidates.map((c) => ({
            item_seq: c.drug_code,
            medication_name: c.medication_name,
          })),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "등록에 실패했습니다.");
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
        hospitalName.trim() || null,
      );
      setMessage(`${selectedDrug.medication_name} 등록 완료`);
      setSelectedDrug(null);
      setQuery("");
      setResults([]);
      setHospitalName("");
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
      <OcrFullscreenOverlay status={jobStatus} />
      <div style={{ display: "flex", gap: 6 }}>
        <button
          type="button"
          onClick={() => setSubTab("photo")}
          style={{
            flex: 1,
            padding: "6px",
            border: `1px solid ${subTab === "photo" ? t.primary : t.border}`,
            borderRadius: 10,
            background: subTab === "photo" ? t.primary : t.cardBg,
            color: subTab === "photo" ? "#fff" : t.textMuted,
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          사진등록
        </button>
        <button
          type="button"
          onClick={() => setSubTab("search")}
          style={{
            flex: 1,
            padding: "6px",
            border: `1px solid ${subTab === "search" ? t.primary : t.border}`,
            borderRadius: 10,
            background: subTab === "search" ? t.primary : t.cardBg,
            color: subTab === "search" ? "#fff" : t.textMuted,
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          수동등록
        </button>
      </div>

      {subTab === "search" ? (
        <div
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 16,
            padding: 18,
            background: t.cardBg,
            boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <h3 style={{ fontSize: 14, fontWeight: 700, color: t.text, margin: 0 }}>
            수동 약품 등록
          </h3>
          <p style={{ fontSize: 13, color: t.textMuted, margin: 0 }}>
            약품명을 검색해서 목록에서 선택하면 바로 복약 일정이 등록됩니다. 검색 결과에 원하는 약이
            없으면, 입력한 이름 그대로 새로 등록할 수도 있습니다(마스터 DB에 없는 약도 등록 자체는
            막히지 않습니다).
          </p>

          {/* (2026-07-27) 본인용과 동일하게 복용횟수/시각을 검색보다 먼저 배치 - 약을 고르기
            전에 미리 스케줄을 정해둘 수 있게 한다. */}
          <p style={{ margin: 0, fontSize: 13, color: t.textMuted }}>하루 복용 횟수</p>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {DOSE_COUNT_OPTIONS.map((opt) => (
              <button
                key={opt.count}
                type="button"
                onClick={() => handleSearchDoseCountChange(opt.count)}
                style={{
                  padding: "8px 14px",
                  borderRadius: 10,
                  border: `1px solid ${t.border}`,
                  background: searchTimeSlots.length === opt.count ? t.primary : t.cardBg,
                  color: searchTimeSlots.length === opt.count ? "#fff" : t.text,
                  fontSize: "13px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p style={{ margin: 0, fontSize: 13, color: t.textMuted }}>복용 시각</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {searchTimeSlots.map((slot, idx) => (
              <TimeInputField key={idx} value={slot} onChange={(v) => updateSearchSlot(idx, v)} />
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <label style={{ fontSize: 13, color: t.textMuted }}>처방 병원명 (선택):</label>
            <input
              type="text"
              value={hospitalName}
              onChange={(e) => setHospitalName(e.target.value)}
              placeholder="예: 서울건강내과"
              style={inputStyle}
            />
          </div>

          <div style={{ display: "flex", gap: 6 }}>
            <input
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setHasSearched(false);
              }}
              placeholder="약품명 검색 (예: 타이레놀)"
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
          {hasSearched && !isBusy && results.length === 0 && (
            <div>
              <p style={{ margin: "0 0 5px", fontSize: 12, color: t.textMuted }}>
                검색 결과가 없습니다.
              </p>
              <button
                type="button"
                onClick={handleQuickRegisterFromSearch}
                disabled={isBusy || !query.trim()}
                style={{
                  fontSize: 12,
                  color: t.textMuted,
                  background: "none",
                  border: "none",
                  textDecoration: "underline",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                찾는 약이 없나요? &quot;{query.trim()}&quot;(으)로 새로 등록
              </button>
            </div>
          )}
          {results.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {!searchDurLoading && searchDurUnmatched.length > 0 && (
                <div style={{ fontSize: 12.5, color: t.textMuted }}>
                  DUR 정보를 찾지 못한 약품명: {searchDurUnmatched.join(", ")}
                </div>
              )}
              {results.map((r) => {
                const durInfo = searchDurByName[r.medication_name];
                const activeFlags = durInfo?.dur_simple.filter((f) => f.present) ?? [];
                return (
                  <label
                    key={r.item_seq}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 8,
                      padding: "8px 10px",
                      border: `1px solid ${selectedDrug?.item_seq === r.item_seq ? t.primary : t.border}`,
                      borderRadius: 12,
                      fontSize: 13,
                      color: t.text,
                      cursor: "pointer",
                      background: t.cardBg,
                    }}
                  >
                    <input
                      type="radio"
                      checked={selectedDrug?.item_seq === r.item_seq}
                      onChange={() => setSelectedDrug(r)}
                      style={{ marginTop: 3 }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div>💊 {r.medication_name}</div>
                      {searchDurLoading && !durInfo && (
                        <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
                          DUR 주의사항 확인 중...
                        </div>
                      )}
                      {!searchDurLoading &&
                        !durInfo &&
                        searchDurUnmatched.includes(r.medication_name) && (
                          <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
                            DUR 데이터베이스에서 이 약을 찾지 못해 주의사항을 확인할 수 없습니다.
                          </div>
                        )}
                      {durInfo &&
                        (activeFlags.length > 0 ? (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                            {activeFlags.map((f) => (
                              <span
                                key={f.rule_code}
                                title={f.prohbt_content ?? undefined}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 5,
                                  fontSize: 11.5,
                                  fontWeight: 700,
                                  padding: "4px 9px",
                                  borderRadius: 999,
                                  background: "#fdecea",
                                  color: t.danger,
                                  border: `1px solid ${t.danger}`,
                                }}
                              >
                                <span
                                  style={{
                                    width: 6,
                                    height: 6,
                                    borderRadius: "50%",
                                    background: t.danger,
                                  }}
                                />
                                {f.rule_label}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
                            DUR 주의 사항 없음
                          </div>
                        ))}
                    </div>
                  </label>
                );
              })}
            </div>
          )}
          {selectedDrug && (
            <button
              type="button"
              onClick={handleRegisterFromSearch}
              disabled={isBusy}
              style={primaryButtonStyle}
            >
              {selectedDrug.medication_name} 등록하기
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            ref={cameraInputRef}

            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            style={{ display: "none" }}
          />
          <input
            ref={galleryInputRef}
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            style={{ display: "none" }}
          />
          {/* (2026-07-27) 본인용(MedicationPage.tsx)과 레이아웃 통일 - 카드 헤더 + 아이콘이
            위에 오는 큰 버튼 2개로 맞춤(기존엔 텍스트만 있는 얇은 pill 버튼이었음). */}
          <div
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 16,
              padding: 18,
              background: t.cardBg,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 14, color: t.primary }}>
              📷 처방전/알약 분석 시작
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                style={{
                  flex: 1,
                  background: t.cardBg,
                  border: `1px solid ${t.border}`,
                  borderRadius: 16,
                  padding: "16px 14px",
                  boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                  cursor: "pointer",
                }}
              >
                <p style={{ margin: "0 0 8px", fontSize: 20 }}>📷</p>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: t.text }}>
                  카메라로 촬영
                </p>
              </button>
              <button
                type="button"
                onClick={() => galleryInputRef.current?.click()}
                style={{
                  flex: 1,
                  background: t.cardBg,
                  border: `1px solid ${t.border}`,
                  borderRadius: 16,
                  padding: "16px 14px",
                  boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                  cursor: "pointer",
                }}
              >
                <p style={{ margin: "0 0 8px", fontSize: 20 }}>🖼️</p>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: t.text }}>
                  갤러리에서 선택
                </p>
              </button>
            </div>
            {file && (
              <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
                선택된 파일: {file.name}
              </p>
            )}
            <button
              type="button"
              onClick={handleUpload}
              disabled={!file || jobStatus === "uploading" || jobStatus === "processing"}
              style={{
                padding: "8px 14px",
                border: "none",
                borderRadius: 10,
                background: t.primary,
                color: "#fff",
                fontWeight: 700,
                fontSize: 13,
                cursor:
                  !file || jobStatus === "uploading" || jobStatus === "processing"
                    ? "not-allowed"
                    : "pointer",
                opacity: !file || jobStatus === "uploading" || jobStatus === "processing" ? 0.6 : 1,
              }}
            >
              {jobStatus === "uploading" || jobStatus === "processing"
                ? "인식 중..."
                : "처방전/알약 분석하기"}
            </button>
          </div>

          {jobStatus === "done" && candidates.length > 0 && (
            <div
              style={{
                border: `1px solid ${t.border}`,
                borderRadius: 16,
                padding: 18,
                background: t.cardBg,
                boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: t.text }}>
                분석 결과 및 매칭 추천
              </p>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: t.textMuted }}>
                의약품 후보 선택 (처방전에 여러 약이 있으면 전부 선택 가능):
              </p>
              {!candidateDurLoading && candidateDurUnmatched.length > 0 && (
                <div style={{ fontSize: 12.5, color: t.textMuted }}>
                  DUR 정보를 찾지 못한 약품명: {candidateDurUnmatched.join(", ")}
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {candidates.map((c) => {
                  const durInfo = candidateDurByName[c.medication_name];
                  const activeFlags = durInfo?.dur_simple.filter((f) => f.present) ?? [];
                  return (
                    <label
                      key={c.item_seq}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 8,
                        padding: "8px 10px",
                        border: `1px solid ${t.border}`,
                        borderRadius: 10,
                        fontSize: 13,
                        color: t.text,
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedCodes.has(c.item_seq)}
                        onChange={() => toggleCandidate(c.item_seq)}
                        style={{ marginTop: 3 }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div>💊 {c.medication_name}</div>
                        {candidateDurLoading && !durInfo && (
                          <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
                            DUR 주의사항 확인 중...
                          </div>
                        )}
                        {!candidateDurLoading &&
                          !durInfo &&
                          candidateDurUnmatched.includes(c.medication_name) && (
                            <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
                              DUR 데이터베이스에서 이 약을 찾지 못해 주의사항을 확인할 수 없습니다.
                            </div>
                          )}
                        {durInfo &&
                          (activeFlags.length > 0 ? (
                            <div
                              style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}
                            >
                              {activeFlags.map((f) => (
                                <span
                                  key={f.rule_code}
                                  title={f.prohbt_content ?? undefined}
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: 5,
                                    fontSize: 11.5,
                                    fontWeight: 700,
                                    padding: "4px 9px",
                                    borderRadius: 999,
                                    background: "#fdecea",
                                    color: t.danger,
                                    border: `1px solid ${t.danger}`,
                                  }}
                                >
                                  <span
                                    style={{
                                      width: 6,
                                      height: 6,
                                      borderRadius: "50%",
                                      background: t.danger,
                                    }}
                                  />
                                  {f.rule_label}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
                              DUR 주의 사항 없음
                            </div>
                          ))}
                      </div>
                    </label>
                  );
                })}
              </div>
              {candidateDurInteractions &&
                (candidateDurInteractions.drug_intrc.interactions.length > 0 ||
                  candidateDurInteractions.drug_intrc.recalls.length > 0) && (
                  <div
                    style={{
                      padding: "10px",
                      borderRadius: 10,
                      background: "#fdecea",
                      border: `1px solid ${t.danger}`,
                      fontSize: 12.5,
                      color: t.text,
                    }}
                  >
                    ⚠️ 선택한 약들 사이에 병용금기·효능군중복 등 상호작용이{" "}
                    {candidateDurInteractions.drug_intrc.interactions.length}건, 리콜 정보가{" "}
                    {candidateDurInteractions.drug_intrc.recalls.length}건 있어요. 등록 목록 → "약품
                    궁합" 탭에서 자세히 확인할 수 있어요.
                  </div>
                )}

              <p style={{ margin: "8px 0 0", fontSize: 12, color: t.textMuted }}>
                하루 복용 횟수 (처방전에서 인식된 횟수가 기본값으로 선택돼요 - 인식이 잘못됐으면
                직접 눌러서 바꿔주세요):
              </p>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {DOSE_COUNT_OPTIONS.map((opt) => (
                  <button
                    key={opt.count}
                    type="button"
                    onClick={() => handleDoseCountChange(opt.count)}
                    style={{
                      padding: "8px 14px",
                      borderRadius: 10,
                      border: `1px solid ${t.border}`,
                      background: timeSlots.length === opt.count ? t.primary : t.cardBg,
                      color: timeSlots.length === opt.count ? "#fff" : t.text,
                      fontSize: "13px",
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <p style={{ margin: 0, fontSize: 13, color: t.textMuted }}>복용 시각</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {timeSlots.map((slot, idx) => (
                  <TimeInputField key={idx} value={slot} onChange={(v) => updateSlot(idx, v)} />
                ))}
              </div>

              <button
                type="button"
                onClick={handleRegisterSelectedFromPhoto}
                disabled={isBusy || selectedCodes.size === 0}
                style={{
                  padding: "10px",
                  borderRadius: 10,
                  background: t.primary,
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 13,
                  border: "none",
                  cursor: isBusy || selectedCodes.size === 0 ? "not-allowed" : "pointer",
                  opacity: isBusy || selectedCodes.size === 0 ? 0.6 : 1,
                }}
              >
                선택한 {selectedCodes.size}개 약품 복약 스케줄 등록 확정
              </button>
              <button
                type="button"
                onClick={() => setSubTab("search")}
                style={{
                  fontSize: 12,
                  color: t.textMuted,
                  background: "none",
                  border: "none",
                  textDecoration: "underline",
                  cursor: "pointer",
                  padding: 0,
                  alignSelf: "flex-start",
                }}
              >
                인식이 잘못됐나요? 검색 탭에서 다른 약 등록하기
              </button>
            </div>
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
  // (2026-07-27) 본인용(MedicationPage.tsx)엔 있는데 가족용엔 없던 전체선택/일괄삭제 -
  // 본인 담당 화면이라 바로 포팅함.
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

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

  useEffect(() => {
    setSelectedIds((prev) => prev.filter((id) => items.some((i) => i.id === id)));
  }, [items]);

  async function handleDelete(item: FamilyMedicationScheduleItem) {
    if (!window.confirm(`"${item.drug_name}" 등록을 삭제할까요?`)) return;
    try {
      await familyMedicationApi.deleteForFamily(item.id);
      load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "삭제에 실패했습니다.");
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]));
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => (prev.length === items.length ? [] : items.map((i) => i.id)));
  }

  async function handleBulkDelete() {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`선택한 ${selectedIds.length}개의 복약 스케줄을 삭제하시겠습니까?`)) return;
    try {
      for (const id of selectedIds) {
        await familyMedicationApi.deleteForFamily(id);
      }
      setSelectedIds([]);
      load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "삭제에 실패했습니다.");
    }
  }

  if (loading) return <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>;
  if (error) return <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>;

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 700, color: t.text, margin: "0 0 8px" }}>
        등록 완료된 복약 스케줄 목록
      </h3>
      {items.length === 0 ? (
        <p style={{ fontSize: 14, color: t.text }}>등록된 약이 없어요.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "5px",
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={selectedIds.length === items.length}
                onChange={toggleSelectAll}
              />
              전체 선택 ({selectedIds.length}/{items.length})
            </label>
            <button
              onClick={handleBulkDelete}
              disabled={selectedIds.length === 0}
              style={{
                backgroundColor: t.danger,
                color: "#fff",
                border: "none",
                padding: "5px 12px",
                borderRadius: 10,
                cursor: selectedIds.length === 0 ? "not-allowed" : "pointer",
                opacity: selectedIds.length === 0 ? 0.5 : 1,
              }}
            >
              선택 삭제 ({selectedIds.length})
            </button>
          </div>
          {items.map((item) => {
            const checked = selectedIds.includes(item.id);
            return (
              <div
                key={item.id}
                style={{
                  border: `1px solid ${checked ? t.primary : t.border}`,
                  borderRadius: 12,
                  padding: 10,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 10,
                  background: t.cardBg,
                  boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                }}
              >
                <label
                  style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "flex-start",
                    cursor: "pointer",
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleSelect(item.id)}
                    style={{ marginTop: 3 }}
                  />
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      flex: "none",
                      borderRadius: 10,
                      background: t.primarySoft,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 18,
                    }}
                  >
                    💊
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>
                      {item.drug_name}
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 11,
                          fontWeight: 700,
                          color: t.textMuted,
                          border: `1px solid ${t.textMuted}`,
                          borderRadius: 999,
                          padding: "1px 8px",
                        }}
                      >
                        등록됨
                      </span>
                    </div>
                    <div style={{ fontSize: 11.5, color: t.textMuted }}>
                      복용 시간: {item.times.join(", ")}
                      {item.hospital_name ? ` · ${item.hospital_name}` : ""}
                    </div>
                    {isUnverifiedDrug(item.item_seq) && (
                      <div style={{ fontSize: 11, color: "#b26a00", marginTop: 4 }}>
                        ⚠️ 마스터 DB에 없는 약이라 상호작용(병용금기) 검사가 제공되지 않습니다.
                      </div>
                    )}
                    {item.source_job_id && (
                      <div style={{ fontSize: 11, color: t.success, marginTop: 4 }}>
                        ✓ OCR 인식을 통해 자동 등록됨
                      </div>
                    )}
                  </div>
                </label>
                <button
                  onClick={() => handleDelete(item)}
                  style={{
                    backgroundColor: t.danger,
                    color: "#fff",
                    border: "none",
                    padding: "5px 10px",
                    borderRadius: 10,
                    cursor: "pointer",
                    flex: "none",
                  }}
                >
                  삭제
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** 카드 클릭 전엔 요약만 보이고, 클릭하면 설명이 펼쳐진다 - 본인용(MedicationPage.tsx)의
 * DurInteractionCard와 동일한 패턴. */
function FamilyDurInteractionCard({ warning }: { warning: DurInteractionWarning }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      onClick={() => setOpen((o) => !o)}
      style={{
        padding: "10px",
        marginBottom: "8px",
        borderRadius: 12,
        background: t.cardBg,
        border: `1px solid ${t.border}`,
        cursor: "pointer",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 12.5, fontWeight: 700 }}>
          {warning.drug_a.item_name} <span style={{ color: t.textMuted }}>↔</span>{" "}
          {warning.drug_b.item_name}
        </div>
        <span style={{ fontSize: 11, color: t.textMuted }}>{open ? "▲" : "▼"}</span>
      </div>
      <span
        style={{
          display: "inline-block",
          marginTop: 6,
          fontSize: 11,
          fontWeight: 700,
          color: t.danger,
          background: "#fdecea",
          borderRadius: 999,
          padding: "3px 8px",
        }}
      >
        {warning.rule_type}
      </span>
      {open && (
        <>
          <p style={{ margin: "8px 0 0", fontSize: 12.5 }}>{warning.prohbt_content}</p>
          {warning.remark && (
            <div
              style={{
                marginTop: 6,
                fontSize: 11.5,
                color: t.textMuted,
                background: t.primarySoft,
                borderRadius: 8,
                padding: "7px 9px",
              }}
            >
              {warning.remark}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FamilyDurRecallCard({ recall }: { recall: DurRecallInfo }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      onClick={() => setOpen((o) => !o)}
      style={{
        padding: "10px",
        marginBottom: "8px",
        borderRadius: 12,
        background: t.cardBg,
        border: `1px solid ${t.border}`,
        cursor: "pointer",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 12.5, fontWeight: 700 }}>회수: {recall.item_name}</div>
        <span style={{ fontSize: 11, color: t.textMuted }}>{open ? "▲" : "▼"}</span>
      </div>
      <div style={{ fontSize: 11.5, color: t.textMuted, marginTop: 2 }}>{recall.entp_name}</div>
      <span
        style={{
          display: "inline-block",
          marginTop: 6,
          fontSize: 11,
          fontWeight: 700,
          color: recall.enforced ? t.danger : "#b26a00",
          background: recall.enforced ? "#fdecea" : "#fff3e0",
          borderRadius: 999,
          padding: "3px 8px",
        }}
      >
        {recall.enforced ? "강제 회수" : "자율 회수"}
      </span>
      {open && (
        <>
          <p style={{ margin: "8px 0 0", fontSize: 12.5 }}>{recall.recall_reason}</p>
          <div style={{ fontSize: 11.5, color: t.textMuted, marginTop: 4 }}>
            {recall.recall_command_date}
          </div>
        </>
      )}
    </div>
  );
}

function FamilyDurIngredientCard({ ingredient }: { ingredient: DurIngredientDetail }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      onClick={() => setOpen((o) => !o)}
      style={{
        marginTop: 10,
        padding: "10px",
        borderRadius: 12,
        background: t.cardBg,
        border: `1px solid ${t.border}`,
        cursor: "pointer",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: t.primaryHover,
            background: t.primarySoft,
            border: `1px solid ${t.primary}`,
            borderRadius: 999,
            padding: "5px 10px",
          }}
        >
          {ingredient.ingr_name} · {ingredient.ingr_code}
        </span>
        <span style={{ fontSize: 11, color: t.textMuted }}>{open ? "▲" : "▼"}</span>
      </div>
      <div style={{ fontSize: 11, color: t.textMuted, marginTop: 6 }}>
        {ingredient.source_drugs.length > 1
          ? "이 성분이 겹치는 등록 약: "
          : "이 성분을 포함한 등록 약: "}
        {ingredient.source_drugs
          .map((d) => (d.qnt && d.unit ? `${d.item_name}(${d.qnt}${d.unit})` : d.item_name))
          .join(", ")}
      </div>
      {open && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          {ingredient.rules.map((rule, idx) => (
            <div
              key={idx}
              style={{
                fontSize: 12,
                lineHeight: 1.5,
                paddingLeft: 10,
                borderLeft: `2px solid ${t.border}`,
              }}
            >
              <b>{rule.rule_type}</b> — {rule.prohbt_content}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InteractionsTab({ targetProfileId }: { targetProfileId: number }) {
  // (2026-07-27) 가족 전용 API(checkInteractionsForFamily)는 리콜/성분 정보가 없는
  // 더 단순한 응답이라, 본인용과 동일하게 durApi를 직접 호출하는 방식으로 바꿨다 -
  // durApi.screenInteraction/screenIngredient는 약품명 목록만 받는 개인정보 무관
  // 조회라 가족 몫 등록약 이름을 그대로 넘겨도 권한 문제 없음.
  const [scheduleCount, setScheduleCount] = useState<number | null>(null);
  const [interactions, setInteractions] = useState<DurInteractionScreeningResponse | null>(null);
  const [ingredients, setIngredients] = useState<DurIngredientScreeningResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    familyMedicationApi
      .listForFamily(targetProfileId)
      .then(async (items) => {
        if (cancelled) return;
        setScheduleCount(items.length);
        if (items.length < 2) return;
        const names = items.map((i) => i.drug_name);
        const [interaction, ingredient] = await Promise.all([
          durApi.screenInteraction(names),
          durApi.screenIngredient(names),
        ]);
        if (cancelled) return;
        setInteractions(interaction);
        setIngredients(ingredient);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "상호작용 확인에 실패했습니다.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [targetProfileId]);

  return (
    <div
      style={{
        background: t.cardBg,
        border: `1px solid ${t.border}`,
        borderRadius: 16,
        padding: 18,
        boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
      }}
    >
      <h3 style={{ fontSize: 14, fontWeight: 700, color: t.text, margin: "0 0 8px" }}>
        약물 상호작용 체크 (DUR)
      </h3>
      <p style={{ fontSize: 13, color: t.textMuted }}>
        등록하신 약들을 서로 대조해 식약처 DUR 데이터에서 병용금기·효능군중복·성분 주의를
        확인합니다. 지병(질병)과의 상충 여부는 아직 포함되지 않습니다.
      </p>

      {scheduleCount !== null && scheduleCount < 2 && (
        <div
          style={{
            padding: "10px",
            borderRadius: 10,
            background: t.primarySoft,
            border: `1px solid ${t.border}`,
            fontSize: 14,
            color: t.text,
          }}
        >
          비교할 수 있는 등록약이 2개 미만이라 상호작용을 확인할 수 없습니다.
        </div>
      )}

      {loading && <p style={{ fontSize: 13, color: t.textMuted }}>등록약을 대조하는 중입니다...</p>}

      {!loading && error && (
        <div
          style={{
            padding: "10px",
            borderRadius: 10,
            background: "#fdecea",
            border: `1px solid ${t.danger}`,
            fontSize: 14,
            color: t.danger,
          }}
        >
          {error}
        </div>
      )}

      {!loading && !error && interactions && ingredients && (
        <>
          <div style={{ display: "flex", gap: 8, margin: "10px 0" }}>
            <div
              style={{
                flex: 1,
                textAlign: "center",
                padding: "10px 8px",
                borderRadius: 12,
                background: t.cardBg,
                border: `1px solid ${t.border}`,
              }}
            >
              <div style={{ fontSize: 20, fontWeight: 800, color: t.danger }}>
                {interactions.drug_intrc.interactions.length}
              </div>
              <div style={{ fontSize: 10.5, color: t.textMuted, marginTop: 2 }}>상호작용</div>
            </div>
            <div
              style={{
                flex: 1,
                textAlign: "center",
                padding: "10px 8px",
                borderRadius: 12,
                background: t.cardBg,
                border: `1px solid ${t.border}`,
              }}
            >
              <div style={{ fontSize: 20, fontWeight: 800, color: "#b26a00" }}>
                {interactions.drug_intrc.recalls.length}
              </div>
              <div style={{ fontSize: 10.5, color: t.textMuted, marginTop: 2 }}>리콜</div>
            </div>
            <div
              style={{
                flex: 1,
                textAlign: "center",
                padding: "10px 8px",
                borderRadius: 12,
                background: t.cardBg,
                border: `1px solid ${t.border}`,
              }}
            >
              <div style={{ fontSize: 20, fontWeight: 800, color: t.text }}>
                {ingredients.ingredients.length}
              </div>
              <div style={{ fontSize: 10.5, color: t.textMuted, marginTop: 2 }}>성분 주의</div>
            </div>
          </div>

          {interactions.drug_intrc.interactions.length === 0 &&
            interactions.drug_intrc.recalls.length === 0 &&
            ingredients.ingredients.length === 0 && (
              <div
                style={{
                  padding: "10px",
                  borderRadius: 10,
                  background: "#EAF7EF",
                  border: `1px solid ${t.success}`,
                  fontSize: 14,
                  color: t.text,
                }}
              >
                등록하신 약들 사이에서 확인된 상호작용·리콜·성분 주의가 없습니다.
              </div>
            )}

          {interactions.drug_intrc.interactions.map((w, idx) => (
            <FamilyDurInteractionCard key={idx} warning={w} />
          ))}
          {interactions.drug_intrc.recalls.map((r) => (
            <FamilyDurRecallCard key={r.item_seq} recall={r} />
          ))}
          {ingredients.ingredients.length > 0 && (
            <div
              style={{
                padding: "10px",
                borderRadius: 12,
                background: t.cardBg,
                border: `1px solid ${t.border}`,
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: t.textMuted }}>성분 상세</div>
              {ingredients.ingredients.map((ing) => (
                <FamilyDurIngredientCard key={ing.ingr_code} ingredient={ing} />
              ))}
            </div>
          )}

          <small style={{ color: t.textMuted, display: "block", marginTop: 10 }}>
            본 서비스는 정보 제공 도구이며, 의학적 진단·처방을 대체하지 않습니다. 출처: 식약처
            의약품안전나라(DUR)
          </small>
        </>
      )}
    </div>
  );
}

const FAMILY_FOOD_POLARITY_STYLES: Record<
  FamilyFoodItem["polarity"],
  { icon: string; label: string; color: string; bg: string }
> = {
  avoid: { icon: "⚠️", label: "주의", color: t.primary, bg: t.primarySoft },
  recommend: { icon: "👍", label: "권장", color: "#2F8F5B", bg: "#EAF7EF" },
};

function FoodTab({ targetProfileId }: { targetProfileId: number }) {
  const [result, setResult] = useState<FamilyFoodInteractionCheckResult | null>(null);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // (2026-07-27) 본인용(MedicationPage.tsx)엔 있는데 가족용엔 안 쓰고 있던 기능 -
  // 백엔드(FamilyGuideCard.food_items)는 이미 이 데이터를 주고 있어서 프론트만 고치면 됨.
  const [openDetail, setOpenDetail] = useState<{ item: FamilyFoodItem; cardTitle: string } | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    familyMedicationApi
      .checkFoodInteractionsForFamily(targetProfileId)
      .then(async (fast) => {
        if (cancelled) return;
        setResult(fast);
        setLoading(false);
        // (2026-07-27 버그 수정) 등록약이 마스터DB 로컬 스냅샷에 없으면(주로 OCR로
        // 자동생성된 약) 빠른 응답만으로는 카드가 하나도 안 나와서 "등록된 약이
        // 없어요"로 잘못 보였다 - 실제로는 등록약은 있는데 느린 실시간 API로 마저
        // 확인해야 하는 상태였을 뿐. 백엔드에 이미 있던 pending 엔드포인트를 이어서 호출.
        if (fast.pending_medication_names.length > 0) {
          setPendingLoading(true);
          try {
            const pending =
              await familyMedicationApi.checkFoodInteractionsPendingForFamily(targetProfileId);
            if (cancelled) return;
            setResult((prev) => ({
              guide_cards: [...(prev?.guide_cards ?? []), ...pending.guide_cards],
              checked_count: fast.checked_count,
              pending_medication_names: [],
            }));
          } catch (err) {
            console.error(err);
          } finally {
            if (!cancelled) setPendingLoading(false);
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "음식 정보 확인에 실패했습니다.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [targetProfileId]);

  if (loading) return <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>;
  if (error) return <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>;
  if (!result || result.checked_count === 0) {
    return <p style={{ color: t.textMuted, fontSize: 13 }}>등록된 약이 없어요.</p>;
  }
  if (result.guide_cards.length === 0) {
    // 등록약은 있지만(checked_count > 0) 아직 확인된 음식 정보가 없는 경우 - "등록약이
    // 없다"는 예전 문구는 오해를 부르므로 구분해서 안내한다.
    return (
      <p style={{ color: t.textMuted, fontSize: 13 }}>
        {pendingLoading
          ? "등록약 정보를 마저 확인하는 중입니다..."
          : "등록약은 있지만 아직 확인된 음식 관련 주의사항이 없어요."}
      </p>
    );
  }

  return (
    <>
      {pendingLoading && (
        <p style={{ color: t.textMuted, fontSize: 12, marginBottom: 8 }}>
          일부 약 정보를 마저 확인하는 중...
        </p>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {result.guide_cards.map((card, idx) => (
          <div
            key={idx}
            style={{
              background: t.cardBg,
              border: `1px solid ${card.severity === "caution" ? t.danger : t.border}`,
              borderRadius: 12,
              padding: "10px",
            }}
          >
            <h5 style={{ fontSize: 14, fontWeight: 700, color: t.text, margin: "0 0 8px" }}>
              {card.title}
            </h5>
            {card.food_items && card.food_items.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {card.food_items.map((item) => {
                  const style = FAMILY_FOOD_POLARITY_STYLES[item.polarity];
                  const isAvoid = item.polarity === "avoid";
                  return (
                    <button
                      key={item.name}
                      type="button"
                      onClick={() => setOpenDetail({ item, cardTitle: card.title })}
                      style={{
                        padding: "6px 14px",
                        borderRadius: 10,
                        border: `1px solid ${isAvoid ? t.border : style.color}`,
                        background: style.bg,
                        color: isAvoid ? t.text : style.color,
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      {isAvoid ? "" : `${style.icon} `}
                      {item.name}
                    </button>
                  );
                })}
              </div>
            ) : (
              card.content
                .split(/\n\s*\n/)
                .map((s) => s.trim())
                .filter(Boolean)
                .map((paragraph, pIdx) => (
                  <p key={pIdx} style={{ margin: "6px 0", fontSize: 14, color: t.text }}>
                    {paragraph}
                  </p>
                ))
            )}
            <small style={{ color: t.textMuted }}>{card.disclaimer}</small>
          </div>
        ))}
      </div>

      {openDetail && (
        <Modal onClose={() => setOpenDetail(null)}>
          <div
            style={{
              background: t.cardBg,
              border: `1px solid ${t.border}`,
              borderRadius: 16,
              padding: 20,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>
                {FAMILY_FOOD_POLARITY_STYLES[openDetail.item.polarity].icon}
              </span>
              <p
                style={{
                  margin: 0,
                  fontSize: 17,
                  fontWeight: 700,
                  color: FAMILY_FOOD_POLARITY_STYLES[openDetail.item.polarity].color,
                }}
              >
                {openDetail.item.name}
              </p>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: FAMILY_FOOD_POLARITY_STYLES[openDetail.item.polarity].bg,
                  color: FAMILY_FOOD_POLARITY_STYLES[openDetail.item.polarity].color,
                }}
              >
                {FAMILY_FOOD_POLARITY_STYLES[openDetail.item.polarity].label}
              </span>
            </div>
            <p style={{ margin: "0 0 14px", fontSize: 12, color: t.textMuted }}>
              {openDetail.cardTitle}
            </p>
            <p style={{ margin: "0 0 18px", fontSize: 14, lineHeight: 1.6, color: t.text }}>
              {openDetail.item.detail}
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setOpenDetail(null)}
                style={{
                  padding: "9px 20px",
                  borderRadius: 10,
                  border: `1px solid ${t.border}`,
                  background: t.cardBg,
                  color: t.textMuted,
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                닫기
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
