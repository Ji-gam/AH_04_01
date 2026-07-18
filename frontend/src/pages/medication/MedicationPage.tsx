import { useState, useEffect } from "react";

import { durApi } from "../../api/durApi";
import type {
  DurBasicScreeningResult,
  DurIngredientDetail,
  DurIngredientScreeningResponse,
  DurInteractionScreeningResponse,
  DurInteractionWarning,
  DurRecallInfo,
} from "../../api/types";
import FamilySwitcher from "../../components/family/FamilySwitcher";
import FamilyTrackerView from "../../components/family/FamilyTrackerView";
import { useAuth } from "../../hooks/useAuth";
import {
  useMedication,
  type FoodInteractionCheckResult,
  type FoodItem,
  type RecognitionCandidate,
  type RecognitionJobResult,
} from "../../hooks/useMedication";
import { pinkTheme } from "../../theme/pinkTheme";
import Modal from "../AlarmPage/components/Modal";

/** (T-DOC-4, 2026-07-15) 음식 칩/모달을 `FoodItem.polarity`별로 다르게 보여주기 위한 스타일
 * 묶음 — "avoid"(기본값)는 기존 핑크 주의색, "recommend"는 초록(같이 먹으면 좋음), "timing_caution"은
 * 호박색(동시 섭취는 피하되 시간차를 두면 괜찮음)으로 구분한다. */
const FOOD_POLARITY_STYLES = {
  avoid: { icon: "⚠️", label: "주의", color: pinkTheme.primary, bg: pinkTheme.primarySoft },
  recommend: { icon: "👍", label: "권장", color: "#2F8F5B", bg: "#EAF7EF" },
  timing_caution: { icon: "⏰", label: "시간차 주의", color: "#B8860B", bg: "#FDF3DC" },
} as const;

function foodPolarityStyle(polarity: FoodItem["polarity"]) {
  return FOOD_POLARITY_STYLES[polarity ?? "avoid"];
}

/** 탭 버튼 — 활성 탭은 핑크 채움, 비활성은 흰 카드. */
function tabStyle(isActive: boolean): React.CSSProperties {
  return {
    flex: 1,
    padding: "9px 4px",
    fontWeight: isActive ? 700 : 400,
    fontSize: 13,
    border: isActive ? "none" : `1px solid ${pinkTheme.border}`,
    borderRadius: 10,
    background: isActive ? pinkTheme.primary : pinkTheme.cardBg,
    color: isActive ? "#fff" : pinkTheme.text,
    cursor: "pointer",
  };
}

const durCardStyle: React.CSSProperties = {
  padding: "10px",
  marginBottom: "8px",
  borderRadius: 12,
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  cursor: "pointer",
};

/** 카드 클릭 전엔 요약(약물쌍/구분 배지)만 보이고, 클릭하면 설명/비고가 펼쳐진다 —
 * DUR 카드가 여러 개 나열될 때 한눈에 훑어보기 쉽게 하기 위함. */
function DurInteractionCard({ warning }: { warning: DurInteractionWarning }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={durCardStyle} onClick={() => setOpen((o) => !o)}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 12.5, fontWeight: 700 }}>
          {warning.drug_a.item_name}{" "}
          <span style={{ color: pinkTheme.textMuted, fontWeight: 400 }}>↔</span>{" "}
          {warning.drug_b.item_name}
        </div>
        <span style={{ fontSize: 11, color: pinkTheme.textMuted }}>{open ? "▲" : "▼"}</span>
      </div>
      <span
        style={{
          display: "inline-block",
          marginTop: 6,
          fontSize: 11,
          fontWeight: 700,
          color: pinkTheme.danger,
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
                color: pinkTheme.textMuted,
                background: pinkTheme.primarySoft,
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

function DurRecallCard({ recall }: { recall: DurRecallInfo }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={durCardStyle} onClick={() => setOpen((o) => !o)}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 12.5, fontWeight: 700 }}>회수: {recall.item_name}</div>
        <span style={{ fontSize: 11, color: pinkTheme.textMuted }}>{open ? "▲" : "▼"}</span>
      </div>
      <div style={{ fontSize: 11.5, color: pinkTheme.textMuted, marginTop: 2 }}>
        {recall.entp_name}
      </div>
      <span
        style={{
          display: "inline-block",
          marginTop: 6,
          fontSize: 11,
          fontWeight: 700,
          color: recall.enforced ? pinkTheme.danger : "#b26a00",
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
          <div style={{ fontSize: 11.5, color: pinkTheme.textMuted, marginTop: 4 }}>
            {recall.recall_command_date}
          </div>
        </>
      )}
    </div>
  );
}

/** 등록약이 2개 이상이어도, 이 성분을 실제로 포함한 약만 source_drugs에 나열된다 — 1개만
 * 나오면 "공유"가 아니라 그 약 하나의 성분 정보라는 뜻이라, 문구로 명시해서 헷갈리지 않게 한다. */
function DurIngredientCard({ ingredient }: { ingredient: DurIngredientDetail }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ ...durCardStyle, marginTop: 10 }} onClick={() => setOpen((o) => !o)}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            fontWeight: 700,
            color: pinkTheme.primaryHover,
            background: pinkTheme.primarySoft,
            border: `1px solid ${pinkTheme.primary}`,
            borderRadius: 999,
            padding: "5px 10px",
          }}
        >
          {ingredient.ingr_name} · {ingredient.ingr_code}
        </span>
        <span style={{ fontSize: 11, color: pinkTheme.textMuted }}>{open ? "▲" : "▼"}</span>
      </div>
      <div style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 6 }}>
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
                borderLeft: `2px solid ${pinkTheme.border}`,
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

/** 수동 등록의 검색 결과/부분일치 후보 카드 — OCR 인식 결과(5~8단계)의 카드(아이콘 박스 + 이름 +
 * DUR 주의사항 pill)를 그대로 차용한다. OCR은 처방전 한 장에 여러 약이 나올 수 있어 체크박스로
 * 다중 선택하지만, 여기는 한 번에 스케줄 하나만 등록하면 되므로 라디오(단일 선택)로 좁혔다. */
function MedicationSelectCard({
  name,
  subtitle,
  selected,
  onToggle,
  durInfo,
  durLoading,
  isUnmatched,
}: {
  name: string;
  subtitle?: string;
  selected: boolean;
  onToggle: () => void;
  durInfo: DurBasicScreeningResult | undefined;
  durLoading: boolean;
  isUnmatched: boolean;
}) {
  const activeFlags = durInfo?.dur_simple.filter((f) => f.present) ?? [];
  return (
    <label
      style={{
        display: "flex",
        gap: 10,
        alignItems: "flex-start",
        border: `1px solid ${selected ? pinkTheme.primary : pinkTheme.border}`,
        borderRadius: 12,
        padding: 10,
        cursor: "pointer",
        background: pinkTheme.cardBg,
        boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
      }}
    >
      <input type="radio" checked={selected} onChange={onToggle} style={{ marginTop: 3 }} />
      <div
        style={{
          width: 40,
          height: 40,
          flex: "none",
          borderRadius: 10,
          background: pinkTheme.primarySoft,
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
          {name}
          {subtitle && (
            <span style={{ fontWeight: 400, color: pinkTheme.textMuted }}> ({subtitle})</span>
          )}
        </div>
        {durLoading && !durInfo && (
          <div style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 4 }}>
            DUR 주의사항 확인 중...
          </div>
        )}
        {!durLoading && !durInfo && isUnmatched && (
          <div style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 4 }}>
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
                    color: pinkTheme.danger,
                    border: `1px solid ${pinkTheme.danger}`,
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: pinkTheme.danger,
                    }}
                  />
                  {f.rule_label}
                </span>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 4 }}>
              DUR 주의 사항 없음
            </div>
          ))}
      </div>
    </label>
  );
}

type ExtractedFields = NonNullable<RecognitionJobResult["extracted_fields"]>;

export default function MedicationPage() {
  const { user } = useAuth();

  // (가족관리) 가족 선택 시 화면 전체를 FamilyTrackerView로 전환한다 - 본인 몫 로직은 안 건드림.
  const [selectedFamily, setSelectedFamily] = useState<{ profileId: number; name: string } | null>(
    null,
  );

  const {
    schedules,
    isLoading,
    error,
    fetchSchedules,
    createManualSchedule,
    quickRegister,
    searchMedications,
    deleteSchedule,
    uploadJob,
    getJobStatus,
    confirmJob,
    checkFoodInteractions,
  } = useMedication();

  // 상태 관리
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState("pill_photo");
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<RecognitionCandidate[]>([]);
  const [extractedFields, setExtractedFields] = useState<ExtractedFields | null>(null);

  // OCR로 인식된 후보들에 대해, 등록 확정 전에 바로 DUR 주의사항(임부금기/노인주의 등 pill)과
  // 후보끼리의 병용금기/효능군중복 상호작용을 보여준다 — 기존 dur/screening API를 그대로
  // 재사용하고(백엔드 변경 없음), 표시만 이 페이지의 기존 pinkTheme 톤으로 맞춘다.
  const [durWarningsByName, setDurWarningsByName] = useState<
    Record<string, DurBasicScreeningResult>
  >({});
  const [durInteractions, setDurInteractions] = useState<DurInteractionScreeningResponse | null>(
    null,
  );
  const [durCheckLoading, setDurCheckLoading] = useState(false);
  const [durCheckError, setDurCheckError] = useState<string | null>(null);
  // DUR 로컬 DB(drug_light.db)는 커버리지가 좁아, 인식은 됐어도 DUR 조회에서 못 찾는 약이
  // 흔하다 — DurScreeningPage.tsx의 "찾지 못한 약품명" 요약과 동일하게, 조용히 비워두는 대신
  // 명시적으로 알려준다.
  const [durUnmatchedNames, setDurUnmatchedNames] = useState<string[]>([]);

  // 사용자 확정 폼 입력 값 (처방전 한 장에 여러 약이 인식될 수 있어 다중 선택 지원)
  const [selectedDrugCodes, setSelectedDrugCodes] = useState<string[]>([]);
  const [confirmedTimes, setConfirmedTimes] = useState<string>("09:00, 13:00, 19:00");

  // 수동 등록용 상태 — "더보기 > 약품 검색"과 동일하게 먼저 검색해서 목록에서 고르는 방식으로
  // 바꿨다(마스터 DB 통일 이후 검색 결과가 실제 등록 가능한 약과 일치하므로). 검색 결과에
  // 원하는 약이 없을 때만, 입력한 이름 그대로 새로 등록하는 기존 빠른 등록(T-MED-3, 자동 생성
  // 정책)을 보조 수단으로 남겨둔다.
  const [quickDrugName, setQuickDrugName] = useState("");
  const [manualTimes, setManualTimes] = useState("09:00, 13:00, 19:00");
  const [hospitalName, setHospitalName] = useState(""); // 처방 병원명(선택) — 복약 시간표에 표시 (T-NTFY-2)
  const [searchLoading, setSearchLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // 검색 결과/빠른 등록 부분일치 후보 — OCR 인식 결과(5~8단계)와 동일하게 후보를 목록으로
  // 보여주고 DUR 주의사항(임부금기/노인주의 등)까지 미리 확인시켜준다. OCR은 여러 개를 한 번에
  // 등록할 수 있어 체크박스+다중 선택이지만, 여기는 어차피 한 번에 하나의 스케줄만 등록하므로
  // 라디오(단일 선택) + 확정 버튼으로 좁혔다.
  const [manualCandidates, setManualCandidates] = useState<
    Array<{ drug_code: string; medication_name: string; form_type: string | null }>
  >([]);
  const [selectedManualCode, setSelectedManualCode] = useState<string | null>(null);
  const [manualDurWarningsByName, setManualDurWarningsByName] = useState<
    Record<string, DurBasicScreeningResult>
  >({});
  const [manualDurCheckLoading, setManualDurCheckLoading] = useState(false);
  const [manualDurUnmatchedNames, setManualDurUnmatchedNames] = useState<string[]>([]);

  // 탭 상태 (12, 13번 확장용)
  const [activeTab, setActiveTab] = useState<"schedule" | "list" | "interaction" | "food">(
    "schedule",
  );

  // 약물 상호작용(12번) — DurScreeningPage.tsx 화면4와 동일하게 durApi.screenInteraction/
  // screenIngredient를 등록약 이름으로 호출해서 상호작용/리콜/공유성분 3종을 함께 보여준다
  // (기존 /medications/interactions은 병용금기만 다뤄 효능군중복·공유성분을 놓쳤다).
  // 등록약이 바뀌지 않는 한 다시 조회하지 않도록 캐시 (T-MED-2-2)
  const [regDurInteractions, setRegDurInteractions] =
    useState<DurInteractionScreeningResponse | null>(null);
  const [regDurIngredients, setRegDurIngredients] = useState<DurIngredientScreeningResponse | null>(
    null,
  );
  const [regDurLoading, setRegDurLoading] = useState(false);
  const [regDurError, setRegDurError] = useState<string | null>(null);

  // 음식(13번) — 등록약 전체 기준 음식/음주 주의사항. OCR로 등록했든 수동으로 등록했든 상관없이
  // 등록약이 바뀌지 않는 한 다시 조회하지 않도록 캐시한다(조합 탭과 동일한 패턴, T-DOC-2).
  const [foodInteractionResult, setFoodInteractionResult] =
    useState<FoodInteractionCheckResult | null>(null);
  const [foodInteractionLoading, setFoodInteractionLoading] = useState(false);
  const [foodInteractionError, setFoodInteractionError] = useState<string | null>(null);

  // (T-DOC-4, 모달 개선) 음식 칩을 누르면 그 음식의 상세 이유를 모달로 띄운다 — null이면 닫힌 상태.
  // 아이콘/색상은 카드 severity가 아니라 음식 개별 polarity를 따른다 — 같은 카드 안에서도
  // "피해야 할 음식"과 "함께 먹으면 좋은 음식"이 섞여 있을 수 있기 때문(예: 아스피린 - 우유는
  // 권장, 카페인은 주의).
  const [openFoodDetail, setOpenFoodDetail] = useState<{
    item: FoodItem;
    cardTitle: string;
  } | null>(null);

  useEffect(() => {
    fetchSchedules();
  }, []);

  // 등록약 목록이 바뀌면(추가/삭제) 캐시를 무효화해 다음에 탭을 열 때 재조회한다.
  useEffect(() => {
    setRegDurInteractions(null);
    setRegDurIngredients(null);
    setFoodInteractionResult(null);
  }, [schedules.length]);

  useEffect(() => {
    if (activeTab !== "interaction" || regDurInteractions || regDurLoading) return;
    if (schedules.length === 0) return;

    const checkRegisteredDur = async () => {
      const names = schedules.map((s) => s.drug_name);
      setRegDurLoading(true);
      setRegDurError(null);
      try {
        const [interaction, ingredient] = await Promise.all([
          durApi.screenInteraction(names),
          durApi.screenIngredient(names),
        ]);
        setRegDurInteractions(interaction);
        setRegDurIngredients(ingredient);
      } catch (err) {
        setRegDurError(err instanceof Error ? err.message : "상호작용 확인에 실패했습니다.");
      } finally {
        setRegDurLoading(false);
      }
    };
    checkRegisteredDur();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, schedules]);

  useEffect(() => {
    if (activeTab !== "food" || foodInteractionResult || foodInteractionLoading) return;
    setFoodInteractionLoading(true);
    setFoodInteractionError(null);
    checkFoodInteractions()
      .then(setFoodInteractionResult)
      .catch((err: unknown) => {
        setFoodInteractionError(
          err instanceof Error ? err.message : "음식 주의사항 확인에 실패했습니다.",
        );
      })
      .finally(() => setFoodInteractionLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // 비동기 작업 폴링 처리
  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | undefined;
    if (currentJobId && (jobStatus === "pending" || jobStatus === "processing")) {
      intervalId = setInterval(async () => {
        try {
          const res = await getJobStatus(currentJobId);
          setJobStatus(res.status);
          if (res.status === "done") {
            setCandidates(res.candidates);
            setExtractedFields(res.extracted_fields ?? null);
            // 인식된 약이 여러 개일 수 있으므로 기본으로 전부 선택해두고, 사용자가 해제할 수 있게 한다.
            setSelectedDrugCodes(res.candidates.map((c) => c.drug_code));
            if (res.extracted_fields?.times) {
              setConfirmedTimes(res.extracted_fields.times.join(", "));
            }
            clearInterval(intervalId);
          } else if (res.status === "failed") {
            clearInterval(intervalId);
          }
        } catch (err) {
          console.error(err);
          clearInterval(intervalId);
        }
      }, 1000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [currentJobId, jobStatus]);

  // 인식된 후보가 확정되면(candidates가 채워지면) 등록 전 미리 DUR 주의사항/상호작용을 조회한다.
  // DurScreeningPage.tsx의 handleViewReport와 동일한 방식(async/await + try/catch/finally,
  // durApi.screenBasic/screenInteraction을 Promise.all로 병렬 호출)으로 맞췄다.
  useEffect(() => {
    if (candidates.length === 0) {
      setDurWarningsByName({});
      setDurInteractions(null);
      setDurCheckError(null);
      setDurUnmatchedNames([]);
      return;
    }

    const checkDurWarnings = async () => {
      const names = candidates.map((c) => c.drug_name);
      setDurCheckLoading(true);
      setDurCheckError(null);
      try {
        const [basic, interaction] = await Promise.all([
          durApi.screenBasic(names),
          durApi.screenInteraction(names),
        ]);
        const byName: Record<string, DurBasicScreeningResult> = {};
        basic.results.forEach((r) => {
          byName[r.drug_detail.item_name] = r;
        });
        setDurWarningsByName(byName);
        setDurInteractions(interaction);
        setDurUnmatchedNames(basic.unmatched_drug_names);
      } catch (err) {
        setDurCheckError(
          err instanceof Error ? err.message : "DUR 주의사항을 확인하지 못했습니다.",
        );
      } finally {
        setDurCheckLoading(false);
      }
    };
    checkDurWarnings();
  }, [candidates]);

  // 수동 등록 후보(검색 결과/빠른 등록 부분일치)가 채워지면, OCR 후보와 동일하게 등록 전 미리
  // DUR 주의사항을 조회한다. 여기서는 후보끼리의 상호작용은 의미가 없다(아직 등록된 게 아니라
  // 서로 비교할 대상이 없으므로) — 개별 약의 임부금기/노인주의 등만 확인한다.
  useEffect(() => {
    if (manualCandidates.length === 0) {
      setManualDurWarningsByName({});
      setManualDurUnmatchedNames([]);
      return;
    }

    const checkManualDurWarnings = async () => {
      const names = manualCandidates.map((c) => c.medication_name);
      setManualDurCheckLoading(true);
      try {
        const basic = await durApi.screenBasic(names);
        const byName: Record<string, DurBasicScreeningResult> = {};
        basic.results.forEach((r) => {
          byName[r.drug_detail.item_name] = r;
        });
        setManualDurWarningsByName(byName);
        setManualDurUnmatchedNames(basic.unmatched_drug_names);
      } catch (err) {
        console.error(err);
      } finally {
        setManualDurCheckLoading(false);
      }
    };
    checkManualDurWarnings();
  }, [manualCandidates]);

  // 분석 시작 핸들러 (1~4번 흐름)
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    try {
      setCandidates([]);
      setExtractedFields(null);
      setJobStatus("pending");
      const jobId = await uploadJob(file, sourceType);
      setCurrentJobId(jobId);
    } catch (err) {
      console.error(err);
    }
  };

  // 최종 등록 핸들러 (5~8번 및 9~10번 흐름) — 선택된 약을 각각 스케줄로 등록한다.
  const handleConfirmSubmit = async () => {
    if (!currentJobId || selectedDrugCodes.length === 0) return;
    try {
      const timesArray = confirmedTimes
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      // (T-MED, #195) 약품 개수만큼 confirm을 순차 대기하면, 약이 여러 개일수록 등록 시간이
      // 그대로 배로 늘어난다 — 서로 독립된 확정 요청이라 병렬로 보내고, 목록 재조회도
      // confirmJob마다가 아니라 전체가 끝난 뒤 한 번만 한다.
      await Promise.all(
        selectedDrugCodes.map((drugCode) => confirmJob(currentJobId, drugCode, { times: timesArray })),
      );
      await fetchSchedules();
      alert(`${selectedDrugCodes.length}개 약품의 복약 스케줄 등록이 완료되었습니다!`);
      setCurrentJobId(null);
      setJobStatus(null);
    } catch (err) {
      console.error(err);
    }
  };

  // 약품명 검색 핸들러 — "더보기 > 약품 검색"과 같은 마스터 DB(MySQL 캐시 + Tier1 SQLite)를
  // 조회하는 /medications/search를 그대로 쓴다. 결과는 OCR 후보와 동일한 모양(drug_code/
  // medication_name/form_type)으로 담아 manualCandidates에 넣고, 아래에서 하나를 골라 확정한다.
  const handleSearchMedications = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickDrugName.trim()) return;
    setSearchLoading(true);
    setSelectedManualCode(null);
    try {
      const results = await searchMedications(quickDrugName.trim());
      setManualCandidates(
        results.map((r) => ({
          drug_code: r.standard_code,
          medication_name: r.medication_name,
          form_type: r.form_type,
        })),
      );
      setHasSearched(true);
    } finally {
      setSearchLoading(false);
    }
  };

  // 약품명 입력 → 바로 등록 핸들러 (T-MED-3). 검색 결과에 원하는 약이 없을 때 쓰는 보조
  // 수단이다. 정확히 하나만 일치하면 즉시 등록되고, 전혀 일치하지 않으면 새 약품을 즉석
  // 생성해서라도 등록된다. 여러 개가 부분일치할 때만 (검색 결과와 동일한) 후보 목록을 보여주고,
  // 그중 하나를 골라 확정하면 createManualSchedule로 등록한다.
  const handleQuickRegister = async () => {
    if (!quickDrugName.trim()) return;
    try {
      const timesArray = manualTimes
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const res = await quickRegister(quickDrugName, timesArray, hospitalName.trim() || null);
      if (res.status === "registered") {
        alert(
          res.auto_created
            ? `"${res.schedule?.drug_name}"이(가) 마스터 DB에 없어 새로 등록하며 복약 일정을 저장했습니다.`
            : "복약 일정이 성공적으로 등록되었습니다!",
        );
        setQuickDrugName("");
        setHospitalName("");
        setManualCandidates([]);
        setSelectedManualCode(null);
        setHasSearched(false);
      } else {
        // 여러 약과 부분일치 — 사용자가 직접 골라야 하므로 후보만 보여주고 자동 등록하지 않는다.
        setManualCandidates(res.candidates);
        setSelectedManualCode(null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 라디오로 고른 후보 하나를 확정 등록하는 핸들러 (OCR의 handleConfirmSubmit과 동일한 확정
  // 단계지만, 여기는 한 번에 하나만 고를 수 있어 createManualSchedule 한 번으로 끝난다).
  const handleConfirmManualSelection = async () => {
    if (!selectedManualCode) return;
    try {
      const timesArray = manualTimes
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await createManualSchedule(selectedManualCode, timesArray, hospitalName.trim() || null);
      alert("복약 일정이 성공적으로 등록되었습니다!");
      setQuickDrugName("");
      setHospitalName("");
      setManualCandidates([]);
      setSelectedManualCode(null);
      setHasSearched(false);
    } catch (err) {
      console.error(err);
    }
  };

  // 스케줄 삭제 핸들러 (잘못 등록된 항목 취소용)
  const handleDeleteSchedule = async (scheduleId: number) => {
    if (!window.confirm("이 복약 스케줄을 삭제하시겠습니까?")) return;
    try {
      await deleteSchedule(scheduleId);
    } catch (err) {
      console.error(err);
    }
  };

  // (가족관리) 가족 선택 시 본인 몫의 복잡한 OCR/매칭 로직은 그대로 두고, 화면 전체를
  // FamilyTrackerView(4탭 전부 가족 대상)로 바꿔치기한다.
  if (selectedFamily) {
    return (
      <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "20px 12px" }}>
        <div style={{ maxWidth: 480, margin: "0 auto", color: pinkTheme.text }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
            }}
          >
            <button
              type="button"
              onClick={() => setSelectedFamily(null)}
              style={{
                border: "none",
                background: "none",
                color: pinkTheme.primary,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                padding: 0,
              }}
            >
              ← 내 복약 관리로
            </button>
            <FamilySwitcher
              selectedProfileId={selectedFamily.profileId}
              onSelect={setSelectedFamily}
            />
          </div>
          <FamilyTrackerView
            targetProfileId={selectedFamily.profileId}
            targetName={selectedFamily.name}
          />
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "20px 12px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto", color: pinkTheme.text }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: 0 }}>
            💊 복약 관리
          </h1>
          <FamilySwitcher selectedProfileId={null} onSelect={setSelectedFamily} />
        </div>

        {/* 탭 네비게이션 (시간표, 목록, 상호작용, 음식) */}
        <div style={{ display: "flex", gap: "5px", marginBottom: "15px" }}>
          <button
            onClick={() => setActiveTab("schedule")}
            style={tabStyle(activeTab === "schedule")}
          >
            시간표 / 분석
          </button>
          <button onClick={() => setActiveTab("list")} style={tabStyle(activeTab === "list")}>
            등록 목록
          </button>
          <button
            onClick={() => setActiveTab("interaction")}
            style={tabStyle(activeTab === "interaction")}
          >
            조합 (12번)
          </button>
          <button onClick={() => setActiveTab("food")} style={tabStyle(activeTab === "food")}>
            음식 (13번)
          </button>
        </div>

        {activeTab === "schedule" && (
          <div>
            {/* 1~3 단계: 분석 사진/처방전 업로드 */}
            <div
              style={{
                border: `1px solid ${pinkTheme.border}`,
                padding: "15px",
                marginBottom: "15px",
              }}
            >
              <h3>처방전/알약 분석 시작</h3>
              <form
                onSubmit={handleUploadSubmit}
                style={{ display: "flex", flexDirection: "column", gap: "10px" }}
              >
                <div>
                  <label>구분: </label>
                  <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                    <option value="pill_photo">알약 사진</option>
                    <option value="prescription">처방전 PDF/이미지</option>
                    <option value="medical_record">진료기록</option>
                    <option value="medication_guide">복약안내문</option>
                  </select>
                </div>
                <div>
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={isLoading}
                  style={{
                    background: "#fff",
                    border: `1px solid ${pinkTheme.border}`,
                    borderRadius: 8,
                    padding: "8px 12px",
                    color: pinkTheme.text,
                    cursor: isLoading ? "not-allowed" : "pointer",
                  }}
                >
                  {isLoading ? "업로드 중..." : "처방전/알약 분석하기"}
                </button>
              </form>
            </div>

            {/* 4단계: 분석 진행 상태 노출 */}
            {jobStatus && (
              <div
                style={{
                  border: `1px solid ${pinkTheme.border}`,
                  padding: "15px",
                  marginBottom: "15px",
                  backgroundColor: pinkTheme.pageBg,
                }}
              >
                <h4>
                  분석 상태:{" "}
                  {jobStatus === "pending"
                    ? "접수 대기 중..."
                    : jobStatus === "processing"
                      ? "이미지 분석 및 매칭 추출 중..."
                      : jobStatus}
                </h4>
                {jobStatus === "processing" && (
                  <p style={{ fontSize: "12px", color: pinkTheme.textMuted }}>
                    단계: 약 정보 추출 중 → 복약 시간표 생성 중...
                  </p>
                )}
              </div>
            )}

            {/* 5~8 단계: 분석 결과 확인 & 최종 매칭 정보 */}
            {candidates.length > 0 && (
              <div
                style={{
                  border: `1px solid ${pinkTheme.border}`,
                  padding: "15px",
                  marginBottom: "15px",
                }}
              >
                <h3>분석 결과 및 매칭 추천</h3>
                <p
                  style={{
                    fontSize: "12px",
                    color: pinkTheme.text,
                    backgroundColor: pinkTheme.primarySoft,
                    padding: "5px",
                  }}
                >
                  <strong>인식된 raw 텍스트:</strong> {extractedFields?.ocr_raw_text}
                </p>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                    margin: "10px 0",
                  }}
                >
                  <strong>의약품 후보 선택 (처방전에 여러 약이 있으면 전부 선택 가능):</strong>
                  {/* DurScreeningPage.tsx 화면2의 "찾지 못한 약품명" 요약(dur-list-summary)과 동일 —
                    로컬 DUR DB 커버리지가 좁아 인식은 됐어도 못 찾는 약이 흔하므로, 조용히 비워두지
                    않고 명시적으로 알려준다. */}
                  {!durCheckLoading && durUnmatchedNames.length > 0 && (
                    <div style={{ fontSize: 12.5, color: pinkTheme.textMuted }}>
                      DUR 정보를 찾지 못한 약품명: {durUnmatchedNames.join(", ")}
                    </div>
                  )}
                  {/* 카드형 약 목록 + pill 경고 — DurScreeningPage.tsx 화면2(dur-drug-card/dur-pill)와
                    같은 틀을 쓰되, 색상은 그 페이지의 녹색 accent 대신 이 페이지의 pinkTheme로 칠했다. */}
                  {candidates.map((c) => {
                    const durInfo = durWarningsByName[c.drug_name];
                    const activeFlags = durInfo?.dur_simple.filter((f) => f.present) ?? [];
                    const checked = selectedDrugCodes.includes(c.drug_code);
                    return (
                      <label
                        key={c.drug_code}
                        style={{
                          display: "flex",
                          gap: 10,
                          alignItems: "flex-start",
                          border: `1px solid ${checked ? pinkTheme.primary : pinkTheme.border}`,
                          borderRadius: 12,
                          padding: 10,
                          cursor: "pointer",
                          background: pinkTheme.cardBg,
                          boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                        }}
                      >
                        <input
                          type="checkbox"
                          value={c.drug_code}
                          checked={checked}
                          style={{ marginTop: 3 }}
                          onChange={(e) =>
                            setSelectedDrugCodes((prev) =>
                              e.target.checked
                                ? [...prev, c.drug_code]
                                : prev.filter((code) => code !== c.drug_code),
                            )
                          }
                        />
                        <div
                          style={{
                            width: 40,
                            height: 40,
                            flex: "none",
                            borderRadius: 10,
                            background: pinkTheme.primarySoft,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 18,
                          }}
                        >
                          💊
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 700, fontSize: 14 }}>{c.drug_name}</div>
                          <div style={{ fontSize: 11.5, color: pinkTheme.textMuted }}>
                            매칭률 {(c.match_rate * 100).toFixed(0)}%
                            {c.match_rate < 0.6 && " · 마스터 DB 미등록, 신규 인식"}
                          </div>
                          {durCheckLoading && !durInfo && (
                            <div style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 4 }}>
                              DUR 주의사항 확인 중...
                            </div>
                          )}
                          {!durCheckLoading &&
                            !durInfo &&
                            durUnmatchedNames.includes(c.drug_name) && (
                              <div
                                style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 4 }}
                              >
                                DUR 데이터베이스에서 이 약을 찾지 못해 주의사항을 확인할 수
                                없습니다.
                              </div>
                            )}
                          {durInfo &&
                            (activeFlags.length > 0 ? (
                              <div
                                style={{
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: 6,
                                  marginTop: 6,
                                }}
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
                                      color: pinkTheme.danger,
                                      border: `1px solid ${pinkTheme.danger}`,
                                    }}
                                  >
                                    <span
                                      style={{
                                        width: 6,
                                        height: 6,
                                        borderRadius: "50%",
                                        background: pinkTheme.danger,
                                      }}
                                    />
                                    {f.rule_label}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <div
                                style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 4 }}
                              >
                                DUR 주의 사항 없음
                              </div>
                            ))}
                        </div>
                      </label>
                    );
                  })}
                </div>

                {/* 상호작용 리포트 — DurScreeningPage.tsx 화면4(dur-stat 요약 + dur-intrc-* 카드)와
                  같은 틀, pinkTheme 색상. 등록 확정 전에 인식된 후보끼리 미리 대조해서 보여준다. */}
                {durCheckError && (
                  <div
                    style={{
                      padding: "10px",
                      marginBottom: "10px",
                      backgroundColor: "#fdecea",
                      border: "1px solid #f5c6cb",
                      fontSize: "13px",
                    }}
                  >
                    {durCheckError}
                  </div>
                )}
                {durInteractions &&
                  (durInteractions.drug_intrc.interactions.length > 0 ||
                    durInteractions.drug_intrc.recalls.length > 0) && (
                    <div style={{ margin: "14px 0" }}>
                      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                        <div
                          style={{
                            flex: 1,
                            textAlign: "center",
                            padding: "10px 8px",
                            borderRadius: 12,
                            background: pinkTheme.cardBg,
                            border: `1px solid ${pinkTheme.border}`,
                          }}
                        >
                          <div style={{ fontSize: 20, fontWeight: 800, color: pinkTheme.danger }}>
                            {durInteractions.drug_intrc.interactions.length}
                          </div>
                          <div style={{ fontSize: 10.5, color: pinkTheme.textMuted, marginTop: 2 }}>
                            상호작용
                          </div>
                        </div>
                        <div
                          style={{
                            flex: 1,
                            textAlign: "center",
                            padding: "10px 8px",
                            borderRadius: 12,
                            background: pinkTheme.cardBg,
                            border: `1px solid ${pinkTheme.border}`,
                          }}
                        >
                          <div style={{ fontSize: 20, fontWeight: 800, color: "#b26a00" }}>
                            {durInteractions.drug_intrc.recalls.length}
                          </div>
                          <div style={{ fontSize: 10.5, color: pinkTheme.textMuted, marginTop: 2 }}>
                            리콜
                          </div>
                        </div>
                      </div>

                      {durInteractions.drug_intrc.interactions.map((w, idx) => (
                        <DurInteractionCard key={idx} warning={w} />
                      ))}

                      {durInteractions.drug_intrc.recalls.map((r) => (
                        <DurRecallCard key={r.item_seq} recall={r} />
                      ))}

                      <small style={{ color: pinkTheme.textMuted }}>
                        본 서비스는 정보 제공 도구이며, 의학적 진단·처방을 대체하지 않습니다. 출처:
                        식약처 의약품안전나라(DUR)
                      </small>
                    </div>
                  )}

                {/* 9~10 단계: 복약 시간표 설정 */}
                <div
                  style={{ display: "flex", flexDirection: "column", gap: "5px", margin: "10px 0" }}
                >
                  <label>
                    <strong>복용 시간대 설정 (쉼표 구분):</strong>
                  </label>
                  <input
                    type="text"
                    value={confirmedTimes}
                    onChange={(e) => setConfirmedTimes(e.target.value)}
                    placeholder="예: 09:00, 13:00, 19:00"
                  />
                </div>

                <button
                  onClick={handleConfirmSubmit}
                  disabled={selectedDrugCodes.length === 0}
                  style={{
                    width: "100%",
                    padding: "10px",
                    backgroundColor: "#4caf50",
                    color: "#fff",
                    border: "none",
                  }}
                >
                  선택한 {selectedDrugCodes.length}개 약품 복약 스케줄 등록 확정
                </button>
              </div>
            )}

            {/* 수동 약품 등록 — "더보기 > 약품 검색"과 동일하게 먼저 검색하고, 검색 결과 목록에서
              하나를 선택해 등록한다(T-MED-1 DoD 2번: 등록 자체는 막히지 않아야 한다는 원칙은
              유지 — 검색 결과에 원하는 약이 없으면 입력한 이름 그대로 새로 등록하는 보조
              수단을 아래에 남겨뒀다). */}
            <div style={{ border: `1px solid ${pinkTheme.border}`, padding: "15px" }}>
              <h3>수동 약품 등록</h3>
              <p style={{ fontSize: "12px", color: pinkTheme.textMuted }}>
                약품명을 검색해서 목록에서 선택하면 바로 복약 일정이 등록됩니다. 검색 결과에 원하는
                약이 없으면, 입력한 이름 그대로 새로 등록할 수도 있습니다(마스터 DB에 없는 약도 등록
                자체는 막히지 않습니다).
              </p>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "5px", margin: "10px 0" }}
              >
                <label>복용 시간대 (쉼표 구분):</label>
                <input
                  type="text"
                  value={manualTimes}
                  onChange={(e) => setManualTimes(e.target.value)}
                />
              </div>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "5px", margin: "10px 0" }}
              >
                <label>처방 병원명 (선택):</label>
                <input
                  type="text"
                  value={hospitalName}
                  onChange={(e) => setHospitalName(e.target.value)}
                  placeholder="예: 서울건강내과"
                />
              </div>

              <form
                onSubmit={handleSearchMedications}
                style={{ display: "flex", gap: "5px", marginBottom: "10px" }}
              >
                <input
                  type="text"
                  value={quickDrugName}
                  onChange={(e) => {
                    setQuickDrugName(e.target.value);
                    setHasSearched(false);
                    setManualCandidates([]);
                    setSelectedManualCode(null);
                  }}
                  placeholder="약품명 검색 (예: 타이레놀)"
                  style={{ flex: 1 }}
                />
                <button type="submit" disabled={searchLoading || !quickDrugName.trim()}>
                  {searchLoading ? "검색 중..." : "검색"}
                </button>
              </form>

              {hasSearched && !searchLoading && manualCandidates.length === 0 && (
                <div style={{ marginBottom: "10px" }}>
                  <p style={{ fontSize: "13px", color: pinkTheme.textMuted, margin: "0 0 5px" }}>
                    검색 결과가 없습니다.
                  </p>
                  <button
                    onClick={handleQuickRegister}
                    disabled={isLoading || !quickDrugName.trim()}
                    style={{
                      fontSize: "12.5px",
                      color: pinkTheme.textMuted,
                      background: "none",
                      border: "none",
                      textDecoration: "underline",
                      cursor: "pointer",
                      padding: 0,
                    }}
                  >
                    찾는 약이 없나요? &quot;{quickDrugName.trim()}&quot;(으)로 새로 등록
                  </button>
                </div>
              )}

              {/* 후보 목록 — OCR 5~8단계와 동일한 DUR 확인 + 카드 UI, 다만 라디오로 하나만 고른다. */}
              {manualCandidates.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                    marginBottom: "10px",
                  }}
                >
                  {!manualDurCheckLoading && manualDurUnmatchedNames.length > 0 && (
                    <div style={{ fontSize: 12.5, color: pinkTheme.textMuted }}>
                      DUR 정보를 찾지 못한 약품명: {manualDurUnmatchedNames.join(", ")}
                    </div>
                  )}
                  {manualCandidates.map((m) => (
                    <MedicationSelectCard
                      key={m.drug_code}
                      name={m.medication_name}
                      subtitle={m.form_type ?? undefined}
                      selected={selectedManualCode === m.drug_code}
                      onToggle={() => setSelectedManualCode(m.drug_code)}
                      durInfo={manualDurWarningsByName[m.medication_name]}
                      durLoading={manualDurCheckLoading}
                      isUnmatched={manualDurUnmatchedNames.includes(m.medication_name)}
                    />
                  ))}
                  <button
                    onClick={handleConfirmManualSelection}
                    disabled={!selectedManualCode}
                    style={{
                      width: "100%",
                      padding: "10px",
                      backgroundColor: "#4caf50",
                      color: "#fff",
                      border: "none",
                      cursor: selectedManualCode ? "pointer" : "not-allowed",
                    }}
                  >
                    선택한 약품 복약 스케줄 등록 확정
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "list" && (
          <div>
            {/* 11번 단계: 약 목록 및 스케줄 확인 */}
            <h3>등록 완료된 복약 스케줄 목록</h3>
            {schedules.length === 0 ? (
              <p>등록된 복약 스케줄이 없습니다.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {schedules.map((s) => (
                  <div
                    key={s.id}
                    style={{
                      border: `1px solid ${pinkTheme.border}`,
                      padding: "10px",
                      borderRadius: "4px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                    }}
                  >
                    <div>
                      <strong>{s.drug_name}</strong>
                      <p style={{ margin: "5px 0 0 0", fontSize: "14px" }}>
                        복용 시간: {s.times.join(", ")}
                      </p>
                      {s.source_job_id && (
                        <span style={{ fontSize: "11px", color: pinkTheme.success }}>
                          ✓ OCR 인식을 통해 자동 등록됨
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteSchedule(s.id)}
                      disabled={isLoading}
                      style={{
                        backgroundColor: pinkTheme.danger,
                        color: "#fff",
                        border: "none",
                        padding: "5px 10px",
                        borderRadius: "4px",
                        cursor: "pointer",
                      }}
                    >
                      삭제
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "interaction" && (
          <div style={{ padding: "15px", border: `1px solid ${pinkTheme.border}` }}>
            {/* 12번 단계: 약물 상호작용 — DurScreeningPage.tsx 화면4(상호작용/리콜/공유성분 통계
              박스 + 상호작용/성분 카드)와 같은 틀, 색상은 pinkTheme. durApi.screenInteraction과
              screenIngredient를 등록약 이름으로 그대로 호출한다(백엔드 변경 없음). */}
            <h3>약물 상호작용 체크 (DUR)</h3>
            <p style={{ color: pinkTheme.textMuted }}>
              등록하신 약들을 서로 대조해 식약처 DUR 데이터에서 병용금기·효능군중복·성분 주의를
              확인합니다. 지병(질병)과의 상충 여부는 아직 포함되지 않습니다.
            </p>

            {schedules.length < 2 && (
              <div
                style={{ padding: "10px", backgroundColor: "#fffde7", border: "1px solid #fff59d" }}
              >
                비교할 수 있는 등록약이 2개 미만이라 상호작용을 확인할 수 없습니다.
              </div>
            )}

            {regDurLoading && <p>등록약을 대조하는 중입니다...</p>}

            {!regDurLoading && regDurError && (
              <div
                style={{ padding: "10px", backgroundColor: "#fdecea", border: "1px solid #f5c6cb" }}
              >
                {regDurError}
              </div>
            )}

            {!regDurLoading && !regDurError && regDurInteractions && regDurIngredients && (
              <>
                <div style={{ display: "flex", gap: 8, margin: "10px 0" }}>
                  <div
                    style={{
                      flex: 1,
                      textAlign: "center",
                      padding: "10px 8px",
                      borderRadius: 12,
                      background: pinkTheme.cardBg,
                      border: `1px solid ${pinkTheme.border}`,
                    }}
                  >
                    <div style={{ fontSize: 20, fontWeight: 800, color: pinkTheme.danger }}>
                      {regDurInteractions.drug_intrc.interactions.length}
                    </div>
                    <div style={{ fontSize: 10.5, color: pinkTheme.textMuted, marginTop: 2 }}>
                      상호작용
                    </div>
                  </div>
                  <div
                    style={{
                      flex: 1,
                      textAlign: "center",
                      padding: "10px 8px",
                      borderRadius: 12,
                      background: pinkTheme.cardBg,
                      border: `1px solid ${pinkTheme.border}`,
                    }}
                  >
                    <div style={{ fontSize: 20, fontWeight: 800, color: "#b26a00" }}>
                      {regDurInteractions.drug_intrc.recalls.length}
                    </div>
                    <div style={{ fontSize: 10.5, color: pinkTheme.textMuted, marginTop: 2 }}>
                      리콜
                    </div>
                  </div>
                  <div
                    style={{
                      flex: 1,
                      textAlign: "center",
                      padding: "10px 8px",
                      borderRadius: 12,
                      background: pinkTheme.cardBg,
                      border: `1px solid ${pinkTheme.border}`,
                    }}
                  >
                    <div style={{ fontSize: 20, fontWeight: 800, color: pinkTheme.text }}>
                      {regDurIngredients.ingredients.length}
                    </div>
                    <div style={{ fontSize: 10.5, color: pinkTheme.textMuted, marginTop: 2 }}>
                      성분 주의
                    </div>
                  </div>
                </div>

                {regDurInteractions.drug_intrc.interactions.length === 0 &&
                  regDurInteractions.drug_intrc.recalls.length === 0 &&
                  regDurIngredients.ingredients.length === 0 && (
                    <div
                      style={{
                        padding: "10px",
                        backgroundColor: "#e8f5e9",
                        border: "1px solid #a5d6a7",
                      }}
                    >
                      등록하신 약들 사이에서 확인된 상호작용·리콜·성분 주의가 없습니다.
                    </div>
                  )}

                {regDurInteractions.drug_intrc.interactions.map((w, idx) => (
                  <DurInteractionCard key={idx} warning={w} />
                ))}

                {regDurInteractions.drug_intrc.recalls.map((r) => (
                  <DurRecallCard key={r.item_seq} recall={r} />
                ))}

                {regDurIngredients.ingredients.length > 0 && (
                  <div
                    style={{
                      padding: "10px",
                      borderRadius: 12,
                      background: pinkTheme.cardBg,
                      border: `1px solid ${pinkTheme.border}`,
                    }}
                  >
                    <div style={{ fontSize: 11, fontWeight: 700, color: pinkTheme.textMuted }}>
                      성분 상세
                    </div>
                    {regDurIngredients.ingredients.map((ing) => (
                      <DurIngredientCard key={ing.ingr_code} ingredient={ing} />
                    ))}
                  </div>
                )}

                <small style={{ color: pinkTheme.textMuted, display: "block", marginTop: 10 }}>
                  본 서비스는 정보 제공 도구이며, 의학적 진단·처방을 대체하지 않습니다. 출처: 식약처
                  의약품안전나라(DUR)
                </small>
              </>
            )}
          </div>
        )}

        {activeTab === "food" && (
          <div style={{ padding: "15px", border: `1px solid ${pinkTheme.border}` }}>
            {/* 13번 단계: 음식 주의사항 (T-DOC-2) — 등록된 약 전체(OCR/수동 등록 무관)의 e약은요
              상호작용 문항(intrcQesitm)에서 음식/음주 관련 주의사항을 그대로 보여준다. */}
            <h3>복약 중 음식 주의사항</h3>
            <p style={{ color: pinkTheme.textMuted }}>
              현재 등록된 약 전체를 기준으로, 식약처 e약은요 정보에서 확인된 음식·음주 관련
              주의사항을 보여줍니다.
            </p>

            {foodInteractionLoading && <p>등록약을 확인하는 중입니다...</p>}

            {!foodInteractionLoading && foodInteractionError && (
              <div
                style={{ padding: "10px", backgroundColor: "#fdecea", border: "1px solid #f5c6cb" }}
              >
                {foodInteractionError}
              </div>
            )}

            {!foodInteractionLoading && !foodInteractionError && foodInteractionResult && (
              <>
                {foodInteractionResult.checked_count === 0 ? (
                  <div
                    style={{
                      padding: "10px",
                      backgroundColor: "#e3f2fd",
                      border: "1px solid #90caf9",
                    }}
                  >
                    등록된 약이 없습니다. 처방전/알약 분석 또는 수동 등록으로 약을 등록해보세요.
                  </div>
                ) : (
                  // 등록약마다 반드시 카드 하나씩 나온다(찾은 정보가 없어도 "확인 불가" 카드로
                  // 명시) — 일부만 카드가 사라지면 그 약은 검사 안 한 것처럼 보이기 때문.
                  foodInteractionResult.guide_cards.map((g, idx) => (
                    <div
                      key={idx}
                      style={{
                        border: `1px solid ${g.severity === "caution" ? "#f0ad4e" : pinkTheme.border}`,
                        padding: "10px",
                        marginBottom: "10px",
                      }}
                    >
                      <h5>{g.title}</h5>
                      {g.food_items && g.food_items.length > 0 ? (
                        // (T-DOC-4, 모달 개선) 음식명이 식별되면 이유 줄글 대신 칩으로 먼저 보여주고,
                        // 칩을 누르면 상세 이유를 모달로 띄운다 — 원문이 긴 카테고리도 다른 칩
                        // 목록을 밀어내지 않고 한 곳에 집중해서 읽을 수 있다.
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                          {g.food_items.map((item) => {
                            const style = foodPolarityStyle(item.polarity);
                            const isAvoid = (item.polarity ?? "avoid") === "avoid";
                            return (
                              <button
                                key={item.name}
                                type="button"
                                onClick={() => setOpenFoodDetail({ item, cardTitle: g.title })}
                                style={{
                                  padding: "6px 14px",
                                  borderRadius: "999px",
                                  border: `1px solid ${isAvoid ? pinkTheme.border : style.color}`,
                                  background: style.bg,
                                  color: isAvoid ? pinkTheme.text : style.color,
                                  fontSize: 13,
                                  fontWeight: 600,
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
                        // 음식명이 식별되지 않으면(사전에 없는 음식이거나 e약은요 자유 텍스트)
                        // 기존처럼 원문 전체를 그대로 보여준다. e약은요 원문은 항목이 빈 줄로
                        // 구분된 여러 문단이라, 빈 줄 기준으로 나눠 문단별로 렌더링한다.
                        g.content
                          .split(/\n\s*\n/)
                          .map((s) => s.trim())
                          .filter(Boolean)
                          .map((paragraph, pIdx) => (
                            <p key={pIdx} style={{ margin: "6px 0" }}>
                              {paragraph}
                            </p>
                          ))
                      )}
                      <small style={{ color: pinkTheme.textMuted }}>{g.disclaimer}</small>
                    </div>
                  ))
                )}
              </>
            )}
          </div>
        )}

        {error && <p style={{ color: pinkTheme.danger, marginTop: "15px" }}>에러: {error}</p>}
      </div>

      {openFoodDetail && (
        <Modal onClose={() => setOpenFoodDetail(null)}>
          <div
            style={{
              background: pinkTheme.cardBg,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 16,
              padding: 20,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>
                {foodPolarityStyle(openFoodDetail.item.polarity).icon}
              </span>
              <p
                style={{
                  margin: 0,
                  fontSize: 17,
                  fontWeight: 700,
                  color: foodPolarityStyle(openFoodDetail.item.polarity).color,
                }}
              >
                {openFoodDetail.item.name}
              </p>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: foodPolarityStyle(openFoodDetail.item.polarity).bg,
                  color: foodPolarityStyle(openFoodDetail.item.polarity).color,
                }}
              >
                {foodPolarityStyle(openFoodDetail.item.polarity).label}
              </span>
            </div>
            <p style={{ margin: "0 0 14px", fontSize: 12, color: pinkTheme.textMuted }}>
              {openFoodDetail.cardTitle}
            </p>
            <p style={{ margin: "0 0 18px", fontSize: 14, lineHeight: 1.6, color: pinkTheme.text }}>
              {openFoodDetail.item.detail}
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setOpenFoodDetail(null)}
                style={{
                  padding: "9px 20px",
                  borderRadius: 10,
                  border: `1px solid ${pinkTheme.border}`,
                  background: pinkTheme.cardBg,
                  color: pinkTheme.textMuted,
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
    </div>
  );
}
