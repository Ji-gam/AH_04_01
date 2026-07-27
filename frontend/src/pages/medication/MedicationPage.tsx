import { Pill } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { durApi } from "../../api/durApi";
import type {
  DurBasicScreeningResult,
  DurIngredientDetail,
  DurIngredientScreeningResponse,
  DurInteractionScreeningResponse,
  DurInteractionWarning,
  DurRecallInfo,
} from "../../api/types";
import PageTitle from "../../components/common/PageTitle";
import FamilySwitcher from "../../components/family/FamilySwitcher";
import FamilyTrackerView from "../../components/family/FamilyTrackerView";
import OcrProgressBar from "../../components/ui/OcrProgressBar";
import { useAuth } from "../../hooks/useAuth";
import {
  useMedication,
  type FoodInteractionCheckResult,
  type FoodItem,
  type RecognitionCandidate,
} from "../../hooks/useMedication";
import { pinkTheme } from "../../theme/pinkTheme";
import { isUnverifiedDrug } from "../../utils/medication";
import Modal from "../AlarmPage/components/Modal";

import DoseTimesInput from "./components/DoseTimesInput";

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

// 사진 등록 업로드 시 백엔드에 보내는 source_type 고정값. 알약 사진만 단독으로는 OCR 인식이
// 잘 안 돼 안내 문구/선택지에서 뺐고(사용자 확인, 2026-07), 나머지 문서 유형(처방전/진료기록/
// 복약안내문)은 어떤 값으로 보내도 서버 처리(_execute_ocr_logic)가 source_type에 따라
// 갈라지지 않아 사용자에게 굳이 고르게 할 이유가 없다 — 그중 하나로 고정해서 보낸다.
const PHOTO_SOURCE_TYPE = "prescription";

/** 탭 버튼 — 활성 탭은 핑크 채움, 비활성은 흰 카드. */
function tabStyle(isActive: boolean): React.CSSProperties {
  return {
    flex: 1,
    padding: "9px 4px",
    fontWeight: 700,
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

export default function MedicationPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // (가족관리) 가족 선택 시 화면 전체를 FamilyTrackerView로 전환한다 - 본인 몫 로직은 안 건드림.
  const [selectedFamily, setSelectedFamily] = useState<{ profileId: number; name: string } | null>(
    null,
  );

  const {
    schedules,
    isLoading,
    error,
    clearError,
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

  // 등록 방식 선택 — 가족 등록 화면(FamilyTrackerView)의 검색/사진 탭과 동일하게, 수동 검색
  // 등록과 사진(OCR) 등록 중 하나만 골라 보여준다(둘 다 항상 같이 보이던 것을 정리).
  const [regMode, setRegMode] = useState<"photo" | "manual">("photo");

  // 상태 관리
  const [file, setFile] = useState<File | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<RecognitionCandidate[]>([]);

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
  const [confirmedTimes, setConfirmedTimes] = useState<string[]>(["09:00", "13:00", "19:00"]);
  // OCR 확정등록 버튼 중복 클릭 방지용 (state는 재렌더 전까지 반영이 늦어 클릭 사이 gap이
  // 생길 수 있어, 클릭 즉시 동기적으로 막아야 하는 이 용도로는 ref를 함께 쓴다).
  const [isConfirmingJob, setIsConfirmingJob] = useState(false);
  const isConfirmingJobRef = useRef(false);

  // OCR 후보가 잘못 인식됐을 때 "다른 약이에요"로 텍스트 검색해 바로잡는 기능 — 새 매칭/
  // 할루시네이션 로직을 새로 만들지 않고, 수동등록 탭이 이미 쓰는 searchMedications/
  // createManualSchedule/quickRegister를 후보 카드 안에서 인라인으로 재사용한다.
  const [editingCandidateCode, setEditingCandidateCode] = useState<string | null>(null);
  const [candidateSearchText, setCandidateSearchText] = useState("");
  const [candidateSearchResults, setCandidateSearchResults] = useState<
    Array<{ item_seq: string; medication_name: string }>
  >([]);
  const [candidateSearchLoading, setCandidateSearchLoading] = useState(false);
  const [candidateSearchDone, setCandidateSearchDone] = useState(false);

  // 수동 등록용 상태 — "더보기 > 약품 검색"과 동일하게 먼저 검색해서 목록에서 고르는 방식으로
  // 바꿨다(마스터 DB 통일 이후 검색 결과가 실제 등록 가능한 약과 일치하므로). 검색 결과에
  // 원하는 약이 없을 때만, 입력한 이름 그대로 새로 등록하는 기존 빠른 등록(T-MED-3, 자동 생성
  // 정책)을 보조 수단으로 남겨둔다.
  const [quickDrugName, setQuickDrugName] = useState("");
  const [manualTimes, setManualTimes] = useState<string[]>(["09:00", "13:00", "19:00"]);
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

  // 11번 단계: 등록약 목록 복수 선택 삭제용 — 개별 삭제 버튼과 별개로, 여러 개를 한 번에
  // 지울 수 있도록 체크박스 선택 상태를 둔다.
  const [selectedScheduleIds, setSelectedScheduleIds] = useState<number[]>([]);

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

  // 목록이 갱신되면(삭제/재조회) 이미 사라진 스케줄 id는 선택 상태에서도 걷어낸다.
  useEffect(() => {
    setSelectedScheduleIds((prev) => prev.filter((id) => schedules.some((s) => s.id === id)));
  }, [schedules]);

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
      // 백엔드가 어떤 이유로든 job을 done/failed로 확정하지 못해 계속 processing으로 남으면
      // 여기서 무한 폴링하게 되므로, 최대 시도 횟수를 방어선으로 둔다(1초 간격 × 90 = 90초).
      const MAX_POLLS = 90;
      let polls = 0;
      intervalId = setInterval(async () => {
        try {
          polls += 1;
          const res = await getJobStatus(currentJobId);
          setJobStatus(res.status);
          if (res.status === "done") {
            setCandidates(res.candidates);
            // 인식된 약이 여러 개일 수 있으므로 기본으로 전부 선택해두고, 사용자가 해제할 수 있게 한다.
            setSelectedDrugCodes(res.candidates.map((c) => c.drug_code));
            if (res.extracted_fields?.times) {
              setConfirmedTimes(res.extracted_fields.times);
            }
            clearInterval(intervalId);
          } else if (res.status === "failed") {
            clearInterval(intervalId);
          } else if (polls >= MAX_POLLS) {
            // 상한 초과: 응답이 안 오는 것으로 보고 실패 처리해 기존 실패 UI로 넘긴다.
            clearInterval(intervalId);
            setJobStatus("failed");
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
          byName[r.queried_name] = r;
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
          byName[r.queried_name] = r;
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
      // 이전 job의 폴링이 재시작되지 않도록, 상태를 pending으로 바꾸기 전에
      // currentJobId부터 비워서 폴링 useEffect 조건(currentJobId && pending)이 거짓이 되게 한다.
      setCurrentJobId(null);
      setJobStatus("pending");
      const jobId = await uploadJob(file, PHOTO_SOURCE_TYPE);
      setCurrentJobId(jobId);
    } catch (err) {
      console.error(err);
    }
  };

  // 최종 등록 핸들러 (5~8번 및 9~10번 흐름) — 선택된 약을 각각 스케줄로 등록한다.
  const handleConfirmSubmit = async () => {
    if (!currentJobId || selectedDrugCodes.length === 0) return;
    if (isConfirmingJobRef.current) return;
    isConfirmingJobRef.current = true;
    setIsConfirmingJob(true);
    try {
      const timesArray = confirmedTimes;
      // (T-MED, #195) 약품 개수만큼 confirm을 순차 대기하면, 약이 여러 개일수록 등록 시간이
      // 그대로 배로 늘어난다 — 서로 독립된 확정 요청이라 병렬로 보내고, 목록 재조회도
      // confirmJob마다가 아니라 전체가 끝난 뒤 한 번만 한다.
      // (#DRUG-REG-BLOCKED-BUG) Promise.all은 하나라도 실패하면 전체가 reject되어, 나머지
      // 정상 약까지 등록 안 된 것처럼 보이고 체크박스도 그대로 남았다 — allSettled로 바꿔
      // 성공한 약은 그대로 등록되게 하고, 실패한 약만 선택 상태를 남겨 재시도할 수 있게 한다.
      const results = await Promise.allSettled(
        selectedDrugCodes.map((drugCode) =>
          confirmJob(currentJobId, drugCode, { times: timesArray }),
        ),
      );
      const failedCodes = selectedDrugCodes.filter((_, i) => results[i].status === "rejected");
      await fetchSchedules();

      if (failedCodes.length === 0) {
        alert(`${selectedDrugCodes.length}개 약품의 복약 스케줄 등록이 완료되었습니다!`);
        // currentJobId/candidates는 그대로 둔다 — 후보별 등록 여부는 등록약 목록(schedules)에서
        // 파생되므로(아래 isRegistered), 등록 목록에서 삭제하면 같은 후보를 재업로드 없이 다시
        // 선택해 등록할 수 있어야 한다. 방금 제출한 선택 상태만 비운다.
        setSelectedDrugCodes([]);
      } else {
        const succeededCount = selectedDrugCodes.length - failedCodes.length;
        const failedNames = failedCodes.map(
          (code) => candidates.find((c) => c.drug_code === code)?.drug_name ?? code,
        );
        alert(
          `${succeededCount}개 약품은 등록되었지만, 다음 약품은 실패했습니다: ${failedNames.join(", ")}`,
        );
        // 실패한 약만 선택 상태로 남겨 재시도할 수 있게 한다.
        setSelectedDrugCodes(failedCodes);
      }
    } catch (err) {
      console.error(err);
    } finally {
      isConfirmingJobRef.current = false;
      setIsConfirmingJob(false);
    }
  };

  // "다른 약이에요" 클릭 → 편집 모드 진입. 후보 카드 하나만 검색창으로 바꾼다.
  const handleStartEditCandidate = (drugCode: string) => {
    setEditingCandidateCode(drugCode);
    setCandidateSearchText("");
    setCandidateSearchResults([]);
    setCandidateSearchDone(false);
  };

  const handleCancelEditCandidate = () => {
    setEditingCandidateCode(null);
    setCandidateSearchText("");
    setCandidateSearchResults([]);
    setCandidateSearchDone(false);
  };

  // 편집 중인 OCR 후보에 대해 마스터 DB(Tier1)를 검색한다 — 수동등록 탭의 handleSearchMedications와
  // 동일한 API(searchMedications)를 그대로 쓴다.
  const handleSearchCandidateReplacement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!candidateSearchText.trim()) return;
    setCandidateSearchLoading(true);
    try {
      const results = await searchMedications(candidateSearchText.trim());
      setCandidateSearchResults(results);
      setCandidateSearchDone(true);
    } finally {
      setCandidateSearchLoading(false);
    }
  };

  // 검색 결과 중 정확한 약을 골랐을 때 — createManualSchedule(수동등록 탭과 동일 API)로 바로
  // 등록한다. 성공하면 내부에서 fetchSchedules()가 실행되어, 기존 isRegistered 파생 로직이 이
  // 후보를 자동으로 "등록됨"으로 표시해준다(별도 상태 동기화 불필요).
  const handleSelectCandidateReplacement = async (itemSeq: string) => {
    try {
      await createManualSchedule(itemSeq, confirmedTimes, hospitalName.trim() || null);
      handleCancelEditCandidate();
    } catch (err) {
      console.error(err);
    }
  };

  // 검색해도 원하는 약이 없을 때 — 입력한 이름 그대로 등록(quickRegister, T-MED-3 자동생성 정책).
  const handleRegisterCandidateAsTyped = async () => {
    if (!candidateSearchText.trim()) return;
    try {
      const res = await quickRegister(
        candidateSearchText.trim(),
        confirmedTimes,
        hospitalName.trim() || null,
      );
      if (res.status === "registered") {
        alert(
          res.auto_created
            ? `"${res.schedule?.drug_name}"이(가) 마스터 DB에 없어 새로 등록하며 복약 일정을 저장했습니다. 이 약은 상호작용(병용금기) 검사가 제공되지 않습니다.`
            : "복약 일정이 성공적으로 등록되었습니다!",
        );
        handleCancelEditCandidate();
      } else {
        // 여러 약과 부분일치 — 검색 결과 목록에 반영해 다시 고르게 한다.
        setCandidateSearchResults(
          res.candidates.map((c) => ({
            item_seq: c.drug_code,
            medication_name: c.medication_name,
          })),
        );
        setCandidateSearchDone(true);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 약품명 검색 핸들러 — "더보기 > 약품 검색"과 같은 마스터 DB(MySQL dur_prod_master_list)를
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
          drug_code: r.item_seq,
          medication_name: r.medication_name,
          form_type: null,
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
      const timesArray = manualTimes;
      const res = await quickRegister(quickDrugName, timesArray, hospitalName.trim() || null);
      if (res.status === "registered") {
        alert(
          res.auto_created
            ? `"${res.schedule?.drug_name}"이(가) 마스터 DB에 없어 새로 등록하며 복약 일정을 저장했습니다. 이 약은 상호작용(병용금기) 검사가 제공되지 않습니다.`
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
      const timesArray = manualTimes;
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

  const toggleScheduleSelection = (scheduleId: number) => {
    setSelectedScheduleIds((prev) =>
      prev.includes(scheduleId) ? prev.filter((id) => id !== scheduleId) : [...prev, scheduleId],
    );
  };

  const toggleSelectAllSchedules = () => {
    setSelectedScheduleIds((prev) =>
      prev.length === schedules.length ? [] : schedules.map((s) => s.id),
    );
  };

  // 복수 선택 삭제 — deleteSchedule이 건마다 목록을 재조회하므로, 경합을 피하려고 순차 처리한다.
  const handleBulkDeleteSchedules = async () => {
    if (selectedScheduleIds.length === 0) return;
    if (!window.confirm(`선택한 ${selectedScheduleIds.length}개의 복약 스케줄을 삭제하시겠습니까?`))
      return;
    try {
      for (const scheduleId of selectedScheduleIds) {
        await deleteSchedule(scheduleId);
      }
      setSelectedScheduleIds([]);
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
        <button
          type="button"
          onClick={() => navigate("/")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 12,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <PageTitle icon={Pill}>복약 관리</PageTitle>
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
            약품 궁합
          </button>
          <button onClick={() => setActiveTab("food")} style={tabStyle(activeTab === "food")}>
            음식 궁합
          </button>
        </div>

        {activeTab === "schedule" && (
          <div>
            {/* 등록 방식 선택 — 가족 등록 화면(FamilyTrackerView)의 검색/사진 탭과 같은 pill
              버튼 스타일. 사진등록/수동등록 중 하나만 아래에 표시한다. */}
            <div style={{ display: "flex", gap: 6, marginBottom: 15 }}>
              <button
                type="button"
                onClick={() => setRegMode("photo")}
                style={{
                  flex: 1,
                  padding: "6px",
                  border: `1px solid ${regMode === "photo" ? pinkTheme.primary : pinkTheme.border}`,
                  borderRadius: 10,
                  background: regMode === "photo" ? pinkTheme.primary : pinkTheme.cardBg,
                  color: regMode === "photo" ? "#fff" : pinkTheme.textMuted,
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                사진등록
              </button>
              <button
                type="button"
                onClick={() => setRegMode("manual")}
                style={{
                  flex: 1,
                  padding: "6px",
                  border: `1px solid ${regMode === "manual" ? pinkTheme.primary : pinkTheme.border}`,
                  borderRadius: 10,
                  background: regMode === "manual" ? pinkTheme.primary : pinkTheme.cardBg,
                  color: regMode === "manual" ? "#fff" : pinkTheme.textMuted,
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                수동등록
              </button>
            </div>

            {regMode === "photo" && (
              <>
                {/* 1~3 단계: 분석 사진/처방전 업로드 — 가족 등록 화면(FamilyTrackerView)과 같은
                  pink 테두리 카드 + pill 버튼 스타일로 통일 */}
                <div
                  style={{
                    border: `1px solid ${pinkTheme.border}`,
                    borderRadius: 16,
                    padding: 18,
                    marginBottom: "15px",
                    background: pinkTheme.cardBg,
                    boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
                  }}
                >
                  <div
                    style={{
                      fontWeight: 700,
                      fontSize: 14,
                      color: pinkTheme.primary,
                      marginBottom: 10,
                    }}
                  >
                    📷 처방전/알약 분석 시작
                  </div>
                  <form
                    onSubmit={handleUploadSubmit}
                    style={{ display: "flex", flexDirection: "column", gap: 8 }}
                  >
                    <input
                      type="file"
                      accept="image/*,application/pdf"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                      required
                      style={{ fontSize: 12 }}
                    />
                    <button
                      type="submit"
                      disabled={isLoading}
                      style={{
                        padding: "8px 14px",
                        border: "none",
                        borderRadius: 10,
                        background: pinkTheme.primary,
                        color: "#fff",
                        fontWeight: 700,
                        fontSize: 13,
                        cursor: isLoading ? "not-allowed" : "pointer",
                        opacity: isLoading ? 0.6 : 1,
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
                      background: pinkTheme.cardBg,
                      border: `1px solid ${pinkTheme.border}`,
                      borderRadius: 16,
                      padding: 18,
                      marginBottom: "15px",
                      boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
                    }}
                  >
                    <h4
                      style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: pinkTheme.text,
                        margin: "0 0 8px",
                      }}
                    >
                      분석 상태:{" "}
                      {jobStatus === "pending"
                        ? "접수 대기 중..."
                        : jobStatus === "processing"
                          ? "이미지 분석 및 매칭 추출 중..."
                          : jobStatus}
                    </h4>
                    {(jobStatus === "pending" || jobStatus === "processing") && (
                      <div style={{ marginTop: 8 }}>
                        <OcrProgressBar status={jobStatus} />
                      </div>
                    )}
                  </div>
                )}

                {/* 5~8 단계: 분석 결과 확인 & 최종 매칭 정보 */}
                {candidates.length > 0 && (
                  <div
                    style={{
                      background: pinkTheme.cardBg,
                      border: `1px solid ${pinkTheme.border}`,
                      borderRadius: 16,
                      padding: 18,
                      marginBottom: "15px",
                      boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: pinkTheme.text,
                        margin: "0 0 8px",
                      }}
                    >
                      분석 결과 및 매칭 추천
                    </h3>

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
                        // 등록 여부는 등록약 목록(schedules)에서 이름으로 파생한다 — 등록약이 목록에서
                        // 삭제되면 자동으로 다시 선택 가능해지고, 이미지를 다시 올릴 필요가 없다.
                        const isRegistered = schedules.some((s) => s.item_seq === c.drug_code);
                        const checked = !isRegistered && selectedDrugCodes.includes(c.drug_code);

                        // 이 후보가 편집(다른 약이에요) 모드면, 카드 대신 인라인 검색 UI를 보여준다.
                        if (editingCandidateCode === c.drug_code) {
                          return (
                            <div
                              key={c.drug_code}
                              style={{
                                border: `1px solid ${pinkTheme.primary}`,
                                borderRadius: 12,
                                padding: 10,
                                background: pinkTheme.cardBg,
                              }}
                            >
                              <form
                                onSubmit={handleSearchCandidateReplacement}
                                style={{ display: "flex", gap: 5, marginBottom: 8 }}
                              >
                                <input
                                  type="text"
                                  value={candidateSearchText}
                                  onChange={(e) => {
                                    setCandidateSearchText(e.target.value);
                                    setCandidateSearchDone(false);
                                    setCandidateSearchResults([]);
                                  }}
                                  placeholder="실제 약품명 검색 (예: 타이레놀)"
                                  autoFocus
                                  style={{ flex: 1 }}
                                />
                                <button
                                  type="submit"
                                  disabled={candidateSearchLoading || !candidateSearchText.trim()}
                                >
                                  {candidateSearchLoading ? "검색 중..." : "검색"}
                                </button>
                              </form>

                              {candidateSearchDone &&
                                !candidateSearchLoading &&
                                candidateSearchResults.length === 0 && (
                                  <div style={{ marginBottom: 8 }}>
                                    <p
                                      style={{
                                        fontSize: 12.5,
                                        color: pinkTheme.textMuted,
                                        margin: "0 0 5px",
                                      }}
                                    >
                                      검색 결과가 없습니다.
                                    </p>
                                    <button
                                      onClick={handleRegisterCandidateAsTyped}
                                      disabled={isLoading}
                                      style={{
                                        fontSize: 12.5,
                                        color: pinkTheme.textMuted,
                                        background: "none",
                                        border: "none",
                                        textDecoration: "underline",
                                        cursor: "pointer",
                                        padding: 0,
                                      }}
                                    >
                                      찾는 약이 없나요? &quot;{candidateSearchText.trim()}
                                      &quot;(으)로 새로 등록
                                    </button>
                                  </div>
                                )}

                              {candidateSearchResults.length > 0 && (
                                <div
                                  style={{
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 6,
                                    marginBottom: 8,
                                  }}
                                >
                                  {candidateSearchResults.map((r) => (
                                    <button
                                      key={r.item_seq}
                                      onClick={() => handleSelectCandidateReplacement(r.item_seq)}
                                      disabled={isLoading}
                                      style={{
                                        textAlign: "left",
                                        padding: "8px 10px",
                                        borderRadius: 8,
                                        border: `1px solid ${pinkTheme.border}`,
                                        background: pinkTheme.pageBg,
                                        cursor: "pointer",
                                        fontSize: 13,
                                      }}
                                    >
                                      {r.medication_name}
                                    </button>
                                  ))}
                                </div>
                              )}

                              <button
                                onClick={handleCancelEditCandidate}
                                style={{
                                  fontSize: 12,
                                  color: pinkTheme.textMuted,
                                  background: "none",
                                  border: "none",
                                  cursor: "pointer",
                                  padding: 0,
                                }}
                              >
                                취소
                              </button>
                            </div>
                          );
                        }

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
                              cursor: isRegistered ? "not-allowed" : "pointer",
                              background: isRegistered ? pinkTheme.border : pinkTheme.cardBg,
                              opacity: isRegistered ? 0.6 : 1,
                              boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                            }}
                          >
                            <input
                              type="checkbox"
                              value={c.drug_code}
                              checked={checked}
                              disabled={isRegistered}
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
                              <div style={{ fontWeight: 700, fontSize: 14 }}>
                                {c.drug_name}
                                {isRegistered && (
                                  <span
                                    style={{
                                      marginLeft: 8,
                                      fontSize: 11,
                                      fontWeight: 700,
                                      color: pinkTheme.textMuted,
                                      border: `1px solid ${pinkTheme.textMuted}`,
                                      borderRadius: 999,
                                      padding: "1px 8px",
                                    }}
                                  >
                                    등록됨
                                  </span>
                                )}
                                {!isRegistered && (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.preventDefault();
                                      handleStartEditCandidate(c.drug_code);
                                    }}
                                    style={{
                                      marginLeft: 8,
                                      fontSize: 11,
                                      color: pinkTheme.primary,
                                      background: "none",
                                      border: "none",
                                      textDecoration: "underline",
                                      cursor: "pointer",
                                      padding: 0,
                                      fontWeight: 400,
                                    }}
                                  >
                                    다른 약이에요
                                  </button>
                                )}
                              </div>
                              <div style={{ fontSize: 11.5, color: pinkTheme.textMuted }}>
                                매칭률 {(c.match_rate * 100).toFixed(0)}%
                                {c.match_rate < 0.6 &&
                                  " · 마스터 DB 미등록, 신규 인식(상호작용 검사 미지원)"}
                              </div>
                              {durCheckLoading && !durInfo && (
                                <div
                                  style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 4 }}
                                >
                                  DUR 주의사항 확인 중...
                                </div>
                              )}
                              {!durCheckLoading &&
                                !durInfo &&
                                durUnmatchedNames.includes(c.drug_name) && (
                                  <div
                                    style={{
                                      fontSize: 11,
                                      color: pinkTheme.textMuted,
                                      marginTop: 4,
                                    }}
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
                                    style={{
                                      fontSize: 11,
                                      color: pinkTheme.textMuted,
                                      marginTop: 4,
                                    }}
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
                          background: "#fdecea",
                          border: `1px solid ${pinkTheme.danger}`,
                          borderRadius: 10,
                          fontSize: 14,
                          color: pinkTheme.danger,
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
                              <div
                                style={{ fontSize: 20, fontWeight: 800, color: pinkTheme.danger }}
                              >
                                {durInteractions.drug_intrc.interactions.length}
                              </div>
                              <div
                                style={{ fontSize: 10.5, color: pinkTheme.textMuted, marginTop: 2 }}
                              >
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
                              <div
                                style={{ fontSize: 10.5, color: pinkTheme.textMuted, marginTop: 2 }}
                              >
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
                            본 서비스는 정보 제공 도구이며, 의학적 진단·처방을 대체하지 않습니다.
                            출처: 식약처 의약품안전나라(DUR)
                          </small>
                        </div>
                      )}

                    {/* 9~10 단계: 복약 시간표 설정 */}
                    <div style={{ margin: "10px 0" }}>
                      <DoseTimesInput value={confirmedTimes} onChange={setConfirmedTimes} />
                    </div>

                    <button
                      onClick={handleConfirmSubmit}
                      disabled={!currentJobId || selectedDrugCodes.length === 0 || isConfirmingJob}
                      style={{
                        width: "100%",
                        padding: "10px",
                        borderRadius: 10,
                        background: pinkTheme.primary,
                        color: "#fff",
                        fontWeight: 700,
                        fontSize: 13,
                        border: "none",
                        cursor: isConfirmingJob ? "not-allowed" : "pointer",
                        opacity: isConfirmingJob ? 0.6 : 1,
                      }}
                    >
                      {isConfirmingJob
                        ? "등록 중..."
                        : `선택한 ${selectedDrugCodes.length}개 약품 복약 스케줄 등록 확정`}
                    </button>
                  </div>
                )}
              </>
            )}

            {regMode === "manual" && (
              /* 수동 약품 등록 — "더보기 > 약품 검색"과 동일하게 먼저 검색하고, 검색 결과 목록에서
              하나를 선택해 등록한다(T-MED-1 DoD 2번: 등록 자체는 막히지 않아야 한다는 원칙은
              유지 — 검색 결과에 원하는 약이 없으면 입력한 이름 그대로 새로 등록하는 보조
              수단을 아래에 남겨뒀다). */
              <div
                style={{
                  background: pinkTheme.cardBg,
                  border: `1px solid ${pinkTheme.border}`,
                  borderRadius: 16,
                  padding: 18,
                  boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
                }}
              >
                <h3
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: pinkTheme.text,
                    margin: "0 0 8px",
                  }}
                >
                  수동 약품 등록
                </h3>
                <p style={{ fontSize: 13, color: pinkTheme.textMuted }}>
                  약품명을 검색해서 목록에서 선택하면 바로 복약 일정이 등록됩니다. 검색 결과에
                  원하는 약이 없으면, 입력한 이름 그대로 새로 등록할 수도 있습니다(마스터 DB에 없는
                  약도 등록 자체는 막히지 않습니다).
                </p>
                <div style={{ margin: "10px 0" }}>
                  <DoseTimesInput value={manualTimes} onChange={setManualTimes} />
                </div>
                <div
                  style={{ display: "flex", flexDirection: "column", gap: "5px", margin: "10px 0" }}
                >
                  <label style={{ fontSize: 13, color: pinkTheme.textMuted }}>
                    처방 병원명 (선택):
                  </label>
                  <input
                    type="text"
                    value={hospitalName}
                    onChange={(e) => setHospitalName(e.target.value)}
                    placeholder="예: 서울건강내과"
                    style={{
                      fontSize: 14,
                      color: pinkTheme.text,
                      border: `1px solid ${pinkTheme.border}`,
                      borderRadius: 10,
                      padding: "8px 10px",
                    }}
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
                    style={{
                      flex: 1,
                      fontSize: 14,
                      color: pinkTheme.text,
                      border: `1px solid ${pinkTheme.border}`,
                      borderRadius: 10,
                      padding: "8px 10px",
                    }}
                  />
                  <button
                    type="submit"
                    disabled={searchLoading || !quickDrugName.trim()}
                    style={{
                      padding: "8px 14px",
                      border: "none",
                      borderRadius: 10,
                      background: pinkTheme.primary,
                      color: "#fff",
                      fontWeight: 700,
                      fontSize: 13,
                      cursor: searchLoading || !quickDrugName.trim() ? "not-allowed" : "pointer",
                      opacity: searchLoading || !quickDrugName.trim() ? 0.6 : 1,
                    }}
                  >
                    {searchLoading ? "검색 중..." : "검색"}
                  </button>
                </form>

                {hasSearched && !searchLoading && manualCandidates.length === 0 && (
                  <div style={{ marginBottom: "10px" }}>
                    <p style={{ fontSize: 13, color: pinkTheme.textMuted, margin: "0 0 5px" }}>
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
                        borderRadius: 10,
                        background: pinkTheme.primary,
                        color: "#fff",
                        fontWeight: 700,
                        fontSize: 13,
                        border: "none",
                        cursor: selectedManualCode ? "pointer" : "not-allowed",
                        opacity: selectedManualCode ? 1 : 0.6,
                      }}
                    >
                      선택한 약품 복약 스케줄 등록 확정
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "list" && (
          <div>
            {/* 11번 단계: 약 목록 및 스케줄 확인 */}
            <h3 style={{ fontSize: 14, fontWeight: 700, color: pinkTheme.text, margin: "0 0 8px" }}>
              등록 완료된 복약 스케줄 목록
            </h3>
            {schedules.length === 0 ? (
              <p style={{ fontSize: 14, color: pinkTheme.text }}>등록된 복약 스케줄이 없습니다.</p>
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
                      checked={selectedScheduleIds.length === schedules.length}
                      onChange={toggleSelectAllSchedules}
                    />
                    전체 선택 ({selectedScheduleIds.length}/{schedules.length})
                  </label>
                  <button
                    onClick={handleBulkDeleteSchedules}
                    disabled={isLoading || selectedScheduleIds.length === 0}
                    style={{
                      backgroundColor: pinkTheme.danger,
                      color: "#fff",
                      border: "none",
                      padding: "5px 12px",
                      borderRadius: 10,
                      cursor:
                        isLoading || selectedScheduleIds.length === 0 ? "not-allowed" : "pointer",
                      opacity: selectedScheduleIds.length === 0 ? 0.5 : 1,
                    }}
                  >
                    선택 삭제 ({selectedScheduleIds.length})
                  </button>
                </div>
                {schedules.map((s) => {
                  const checked = selectedScheduleIds.includes(s.id);
                  return (
                    <div
                      key={s.id}
                      style={{
                        border: `1px solid ${checked ? pinkTheme.primary : pinkTheme.border}`,
                        borderRadius: 12,
                        padding: 10,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        gap: 10,
                        background: pinkTheme.cardBg,
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
                          onChange={() => toggleScheduleSelection(s.id)}
                          style={{ marginTop: 3 }}
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
                          <div style={{ fontWeight: 700, fontSize: 14 }}>
                            {s.drug_name}
                            <span
                              style={{
                                marginLeft: 8,
                                fontSize: 11,
                                fontWeight: 700,
                                color: pinkTheme.textMuted,
                                border: `1px solid ${pinkTheme.textMuted}`,
                                borderRadius: 999,
                                padding: "1px 8px",
                              }}
                            >
                              등록됨
                            </span>
                          </div>
                          <div style={{ fontSize: 11.5, color: pinkTheme.textMuted }}>
                            복용 시간: {s.times.join(", ")}
                          </div>
                          {isUnverifiedDrug(s.item_seq) && (
                            <div style={{ fontSize: 11, color: "#b26a00", marginTop: 4 }}>
                              ⚠️ 마스터 DB에 없는 약이라 상호작용(병용금기) 검사가 제공되지
                              않습니다.
                            </div>
                          )}
                          {s.source_job_id && (
                            <div style={{ fontSize: 11, color: pinkTheme.success, marginTop: 4 }}>
                              ✓ OCR 인식을 통해 자동 등록됨
                            </div>
                          )}
                        </div>
                      </label>
                      <button
                        onClick={() => handleDeleteSchedule(s.id)}
                        disabled={isLoading}
                        style={{
                          backgroundColor: pinkTheme.danger,
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
        )}

        {activeTab === "interaction" && (
          <div
            style={{
              background: pinkTheme.cardBg,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 16,
              padding: 18,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
            }}
          >
            {/* 12번 단계: 약물 상호작용 — DurScreeningPage.tsx 화면4(상호작용/리콜/공유성분 통계
              박스 + 상호작용/성분 카드)와 같은 틀, 색상은 pinkTheme. durApi.screenInteraction과
              screenIngredient를 등록약 이름으로 그대로 호출한다(백엔드 변경 없음). */}
            <h3 style={{ fontSize: 14, fontWeight: 700, color: pinkTheme.text, margin: "0 0 8px" }}>
              약물 상호작용 체크 (DUR)
            </h3>
            <p style={{ fontSize: 13, color: pinkTheme.textMuted }}>
              등록하신 약들을 서로 대조해 식약처 DUR 데이터에서 병용금기·효능군중복·성분 주의를
              확인합니다. 지병(질병)과의 상충 여부는 아직 포함되지 않습니다.
            </p>

            {schedules.length < 2 && (
              <div
                style={{
                  padding: "10px",
                  borderRadius: 10,
                  background: pinkTheme.primarySoft,
                  border: `1px solid ${pinkTheme.border}`,
                  fontSize: 14,
                  color: pinkTheme.text,
                }}
              >
                비교할 수 있는 등록약이 2개 미만이라 상호작용을 확인할 수 없습니다.
              </div>
            )}

            {regDurLoading && (
              <p style={{ fontSize: 13, color: pinkTheme.textMuted }}>
                등록약을 대조하는 중입니다...
              </p>
            )}

            {!regDurLoading && regDurError && (
              <div
                style={{
                  padding: "10px",
                  borderRadius: 10,
                  background: "#fdecea",
                  border: `1px solid ${pinkTheme.danger}`,
                  fontSize: 14,
                  color: pinkTheme.danger,
                }}
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
                        borderRadius: 10,
                        background: "#EAF7EF",
                        border: `1px solid ${pinkTheme.success}`,
                        fontSize: 14,
                        color: pinkTheme.text,
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
          <div
            style={{
              background: pinkTheme.cardBg,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 16,
              padding: 18,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
            }}
          >
            {/* 13번 단계: 음식 주의사항 (T-DOC-2) — 등록된 약 전체(OCR/수동 등록 무관)의 e약은요
              상호작용 문항(intrcQesitm)에서 음식/음주 관련 주의사항을 그대로 보여준다. */}
            <h3 style={{ fontSize: 14, fontWeight: 700, color: pinkTheme.text, margin: "0 0 8px" }}>
              복약 중 음식 주의사항
            </h3>
            <p style={{ fontSize: 13, color: pinkTheme.textMuted }}>
              현재 등록된 약 전체를 기준으로, 식약처 e약은요 정보에서 확인된 음식·음주 관련
              주의사항을 보여줍니다.
            </p>

            {foodInteractionLoading && (
              <p style={{ fontSize: 13, color: pinkTheme.textMuted }}>
                등록약을 확인하는 중입니다...
              </p>
            )}

            {!foodInteractionLoading && foodInteractionError && (
              <div
                style={{
                  padding: "10px",
                  borderRadius: 10,
                  background: "#fdecea",
                  border: `1px solid ${pinkTheme.danger}`,
                  fontSize: 14,
                  color: pinkTheme.danger,
                }}
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
                      borderRadius: 10,
                      background: pinkTheme.primarySoft,
                      border: `1px solid ${pinkTheme.border}`,
                      fontSize: 14,
                      color: pinkTheme.text,
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
                        background: pinkTheme.cardBg,
                        border: `1px solid ${g.severity === "caution" ? pinkTheme.danger : pinkTheme.border}`,
                        borderRadius: 12,
                        padding: "10px",
                        marginBottom: "10px",
                      }}
                    >
                      <h5
                        style={{
                          fontSize: 14,
                          fontWeight: 700,
                          color: pinkTheme.text,
                          margin: "0 0 8px",
                        }}
                      >
                        {g.title}
                      </h5>
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
                                  borderRadius: 10,
                                  border: `1px solid ${isAvoid ? pinkTheme.border : style.color}`,
                                  background: style.bg,
                                  color: isAvoid ? pinkTheme.text : style.color,
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
                        // 음식명이 식별되지 않으면(사전에 없는 음식이거나 e약은요 자유 텍스트)
                        // 기존처럼 원문 전체를 그대로 보여준다. e약은요 원문은 항목이 빈 줄로
                        // 구분된 여러 문단이라, 빈 줄 기준으로 나눠 문단별로 렌더링한다.
                        g.content
                          .split(/\n\s*\n/)
                          .map((s) => s.trim())
                          .filter(Boolean)
                          .map((paragraph, pIdx) => (
                            <p
                              key={pIdx}
                              style={{ margin: "6px 0", fontSize: 14, color: pinkTheme.text }}
                            >
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
      </div>

      {error && (
        <Modal onClose={clearError}>
          <div
            style={{
              background: pinkTheme.cardBg,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 16,
              padding: 20,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 20 }}>⚠️</span>
              <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: pinkTheme.danger }}>
                오류가 발생했어요
              </p>
            </div>
            <p style={{ margin: "0 0 18px", fontSize: 14, lineHeight: 1.6, color: pinkTheme.text }}>
              {error}
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={clearError}
                style={{
                  padding: "9px 20px",
                  borderRadius: 10,
                  border: "none",
                  background: pinkTheme.primary,
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                확인
              </button>
            </div>
          </div>
        </Modal>
      )}

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
