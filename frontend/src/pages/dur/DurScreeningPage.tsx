import { useState } from "react";

import { durApi } from "../../api/durApi";
import type {
  DurBasicScreeningResponse,
  DurBasicScreeningResult,
  DurIngredientScreeningResponse,
  DurInteractionScreeningResponse,
} from "../../api/types";

/**
 * T-MED-14 DUR 스크리닝 4단계 화면. 색상/디자인 없는 와이어프레임 수준 — 실제 톤앤매너는
 * 디자인 확정 후 pinkTheme 등으로 다시 입힌다. 응답 필드 ↔ 화면 매핑 참고용 목업(아티팩트)과
 * 1:1로 맞춰져 있다.
 */

const box: React.CSSProperties = { border: "1px solid #000", padding: 12 };
const boxMuted: React.CSSProperties = { border: "1px solid #999", padding: 12, color: "#555" };
const label: React.CSSProperties = { fontSize: 11, fontWeight: 700, color: "#555" };
const button: React.CSSProperties = {
  border: "1px solid #000",
  background: "#fff",
  padding: "8px 14px",
  cursor: "pointer",
  fontWeight: 700,
};

type Step = "input" | "list" | "detail" | "report";

export default function DurScreeningPage() {
  const [drugNames, setDrugNames] = useState<string[]>([""]);
  const [step, setStep] = useState<Step>("input");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1차(목록/상세)용
  const [basicResult, setBasicResult] = useState<DurBasicScreeningResponse | null>(null);
  const [selectedDrug, setSelectedDrug] = useState<DurBasicScreeningResult | null>(null);
  const [expandedCodes, setExpandedCodes] = useState<Record<string, boolean>>({});

  // 2차/3차(상호작용 리포트)용 — 화면 4에서 한 번에 보여주므로 같이 불러온다.
  const [interactionResult, setInteractionResult] =
    useState<DurInteractionScreeningResponse | null>(null);
  const [ingredientResult, setIngredientResult] = useState<DurIngredientScreeningResponse | null>(
    null,
  );

  const handleAddRow = () => setDrugNames((prev) => [...prev, ""]);
  const handleRemoveRow = (idx: number) => setDrugNames((prev) => prev.filter((_, i) => i !== idx));
  const handleChangeRow = (idx: number, value: string) =>
    setDrugNames((prev) => prev.map((name, i) => (i === idx ? value : name)));

  // 화면 1 → 2: 입력한 약품명으로 1차 API 호출
  const handleSubmitNames = async () => {
    const names = drugNames.map((n) => n.trim()).filter(Boolean);
    if (names.length === 0) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await durApi.screenBasic(names);
      setBasicResult(result);
      setStep("list");
    } catch (err) {
      setError(err instanceof Error ? err.message : "약품 정보를 가져오는데 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  // 화면 2 → 3: 카드 탭 → 같은 1차 응답 객체를 그대로 상세 화면에 씀 (재조회 없음)
  const handleSelectDrug = (result: DurBasicScreeningResult) => {
    setSelectedDrug(result);
    setExpandedCodes({});
    setStep("detail");
  };

  const handleTogglePill = (ruleCode: string) =>
    setExpandedCodes((prev) => ({ ...prev, [ruleCode]: !prev[ruleCode] }));

  // 화면 2 → 4: 입력했던 약품명 전체로 2차+3차 API를 병렬 호출
  const handleViewReport = async () => {
    const names = drugNames.map((n) => n.trim()).filter(Boolean);
    setIsLoading(true);
    setError(null);
    try {
      const [interaction, ingredient] = await Promise.all([
        durApi.screenInteraction(names),
        durApi.screenIngredient(names),
      ]);
      setInteractionResult(interaction);
      setIngredientResult(ingredient);
      setStep("report");
    } catch (err) {
      setError(err instanceof Error ? err.message : "상호작용 리포트를 가져오는데 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setDrugNames([""]);
    setBasicResult(null);
    setSelectedDrug(null);
    setInteractionResult(null);
    setIngredientResult(null);
    setError(null);
    setStep("input");
  };

  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: "20px 12px", color: "#000" }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 4px" }}>DUR 스크리닝</h1>
      <p style={{ fontSize: 12, color: "#555", margin: "0 0 16px" }}>
        단계: {step === "input" && "1. 처방전 입력"}
        {step === "list" && "2. 약 목록"}
        {step === "detail" && "3. 약 상세"}
        {step === "report" && "4. 성분 상호작용 리포트"}
      </p>

      {error && (
        <div style={{ ...box, borderStyle: "dashed", marginBottom: 12 }}>
          <strong>오류</strong>
          <p style={{ margin: "4px 0 0" }}>{error}</p>
        </div>
      )}

      {/* ---- 화면 1: 처방전 입력 ---- */}
      {step === "input" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {drugNames.map((name, idx) => (
            <div key={idx} style={{ display: "flex", gap: 6 }}>
              <input
                type="text"
                value={name}
                placeholder="약품명 (예: 부루펜정200밀리그램(이부프로펜))"
                onChange={(e) => handleChangeRow(idx, e.target.value)}
                style={{ flex: 1, padding: 8, border: "1px solid #000" }}
              />
              {drugNames.length > 1 && (
                <button style={button} onClick={() => handleRemoveRow(idx)} aria-label="삭제">
                  ✕
                </button>
              )}
            </div>
          ))}
          <button style={button} onClick={handleAddRow}>
            + 약 추가
          </button>
          <button style={button} disabled={isLoading} onClick={handleSubmitNames}>
            {isLoading ? "확인 중..." : "확인하기"}
          </button>
        </div>
      )}

      {/* ---- 화면 2: 약 목록 ---- */}
      {step === "list" && basicResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {basicResult.unmatched_drug_names.length > 0 && (
            <div style={boxMuted}>
              찾지 못한 약품명: {basicResult.unmatched_drug_names.join(", ")}
            </div>
          )}

          {basicResult.results.map((r) => {
            const activeFlags = r.dur_simple.filter((f) => f.present);
            return (
              <div
                key={r.drug_detail.item_seq}
                style={{ ...box, cursor: "pointer" }}
                onClick={() => handleSelectDrug(r)}
              >
                <div style={{ fontWeight: 700 }}>{r.drug_detail.item_name}</div>
                <div style={{ fontSize: 12, color: "#555" }}>{r.drug_detail.entp_name}</div>
                {activeFlags.length === 0 ? (
                  <div style={{ fontSize: 12, color: "#555", marginTop: 6 }}>
                    DUR 주의 사항 없음
                  </div>
                ) : (
                  <div style={{ marginTop: 6, fontSize: 12 }}>
                    {activeFlags.map((f) => `[${f.rule_label}]`).join(" ")}
                  </div>
                )}
              </div>
            );
          })}

          <button style={button} disabled={isLoading} onClick={handleViewReport}>
            {isLoading ? "불러오는 중..." : "성분 상호작용 리포트 보기"}
          </button>
          <button style={{ ...button, borderStyle: "dashed" }} onClick={handleReset}>
            처음부터 다시
          </button>
        </div>
      )}

      {/* ---- 화면 3: 약 상세 ---- */}
      {step === "detail" && selectedDrug && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <button style={button} onClick={() => setStep("list")}>
            ← 목록으로
          </button>

          <div style={box}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>
              {selectedDrug.drug_detail.item_name}
            </div>
            <div style={{ fontSize: 12, color: "#555" }}>
              {selectedDrug.drug_detail.entp_name} · item_seq {selectedDrug.drug_detail.item_seq}
            </div>
            {(selectedDrug.drug_detail.etc_otc_name || selectedDrug.drug_detail.form_name) && (
              <div style={{ fontSize: 11, marginTop: 4 }}>
                {[selectedDrug.drug_detail.etc_otc_name, selectedDrug.drug_detail.form_name]
                  .filter(Boolean)
                  .map((t) => `[${t}]`)
                  .join(" ")}
              </div>
            )}
          </div>

          <div style={box}>
            <div style={label}>DUR 주의사항 6종 (탭하면 펼쳐짐)</div>
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
              {selectedDrug.dur_simple.map((f) => (
                <div key={f.rule_code}>
                  <div
                    style={{
                      cursor: f.present ? "pointer" : "default",
                      opacity: f.present ? 1 : 0.5,
                    }}
                    onClick={() => f.present && handleTogglePill(f.rule_code)}
                  >
                    {f.present ? "■" : "□"} {f.rule_label}
                  </div>
                  {f.present && expandedCodes[f.rule_code] && (
                    <div style={{ ...boxMuted, marginTop: 4, fontSize: 12 }}>
                      {f.prohbt_content}
                      {f.remark && <div style={{ marginTop: 4 }}>비고: {f.remark}</div>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div style={box}>
            <div style={label}>효능·효과</div>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>
              {selectedDrug.drug_detail.efcy_qesitm ?? "-"}
            </p>
            <div style={label}>용법·용량</div>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>
              {selectedDrug.drug_detail.use_method_qesitm ?? "-"}
            </p>
            <div style={label}>주의사항</div>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>
              {selectedDrug.drug_detail.atpn_warn_qesitm ?? "-"}
            </p>
            <div style={label}>부작용</div>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>
              {selectedDrug.drug_detail.se_qesitm ?? "-"}
            </p>
            <div style={label}>보관방법</div>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>
              {selectedDrug.drug_detail.deposit_method_qesitm ?? "-"}
            </p>
          </div>

          {selectedDrug.drug_detail.identification && (
            <div style={box}>
              <div style={label}>알약 식별</div>
              <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 13 }}>
                <span>모양: {selectedDrug.drug_detail.identification.shape ?? "-"}</span>
                <span>색상: {selectedDrug.drug_detail.identification.color ?? "-"}</span>
                <span>마크: {selectedDrug.drug_detail.identification.mark ?? "-"}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ---- 화면 4: 성분 상호작용 리포트 ---- */}
      {step === "report" && interactionResult && ingredientResult && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <button style={button} onClick={() => setStep("list")}>
            ← 목록으로
          </button>

          <div style={{ display: "flex", gap: 8 }}>
            <div style={{ ...box, flex: 1, textAlign: "center" }}>
              <div style={{ fontSize: 20, fontWeight: 700 }}>
                {interactionResult.drug_intrc.interactions.length}
              </div>
              <div style={label}>상호작용</div>
            </div>
            <div style={{ ...box, flex: 1, textAlign: "center" }}>
              <div style={{ fontSize: 20, fontWeight: 700 }}>
                {interactionResult.drug_intrc.recalls.length}
              </div>
              <div style={label}>리콜</div>
            </div>
            <div style={{ ...box, flex: 1, textAlign: "center" }}>
              <div style={{ fontSize: 20, fontWeight: 700 }}>
                {ingredientResult.ingredients.length}
              </div>
              <div style={label}>공유 성분</div>
            </div>
          </div>

          {interactionResult.drug_intrc.interactions.map((w, idx) => (
            <div key={idx} style={box}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>
                {w.drug_a.item_name} ↔ {w.drug_b.item_name}
              </div>
              <div style={{ fontSize: 12, marginTop: 4 }}>[{w.rule_type}]</div>
              <p style={{ fontSize: 13, margin: "6px 0 0" }}>{w.prohbt_content}</p>
              {w.remark && (
                <div style={{ ...boxMuted, marginTop: 6, fontSize: 12 }}>{w.remark}</div>
              )}
            </div>
          ))}

          {interactionResult.drug_intrc.recalls.map((r) => (
            <div key={r.item_seq} style={box}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>회수: {r.item_name}</div>
              <div style={{ fontSize: 12, color: "#555" }}>{r.entp_name}</div>
              <p style={{ fontSize: 13, margin: "6px 0 0" }}>{r.recall_reason}</p>
              <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
                {r.recall_command_date} · {r.enforced ? "강제 회수" : "자율 회수"}
              </div>
            </div>
          ))}

          {ingredientResult.ingredients.length > 0 && (
            <div style={box}>
              <div style={label}>공유 성분 상세 (3차)</div>
              {ingredientResult.ingredients.map((ing) => (
                <div key={ing.ingr_code} style={{ marginTop: 10 }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>
                    {ing.ingr_name} ({ing.ingr_code})
                  </div>
                  <div style={{ fontSize: 11, color: "#555" }}>
                    {ing.source_drug_names.join(", ")}
                  </div>
                  <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 4 }}>
                    {ing.rules.map((rule, idx) => (
                      <div
                        key={idx}
                        style={{ fontSize: 12, borderLeft: "2px solid #999", paddingLeft: 8 }}
                      >
                        [{rule.rule_type}] {rule.prohbt_content}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          <button style={{ ...button, borderStyle: "dashed" }} onClick={handleReset}>
            처음부터 다시
          </button>
        </div>
      )}
    </div>
  );
}
