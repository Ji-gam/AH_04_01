import { useState } from "react";

import { durApi } from "../../api/durApi";
import type {
  DurBasicScreeningResponse,
  DurBasicScreeningResult,
  DurIngredientScreeningResponse,
  DurInteractionScreeningResponse,
} from "../../api/types";
import "./DurScreeningPage.css";

/**
 * T-MED-14 DUR 스크리닝 4단계 화면. Claude Design 목업(아티팩트 4e74cabf-...)의 디자인 토큰을
 * 그대로 포팅 — 응답 필드 ↔ 화면 매핑은 그 목업과 1:1로 맞춰져 있고, T-MED-14-1에서 추가된
 * atc_code/is_rare_drug/narcotic_kind_name(상세)과 source_drugs 함량(qnt/unit, 리포트)도
 * 반영했다.
 */

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
    <div className="dur">
      <div className="dur-shell">
        <div>
          <div className="dur-app-title">DUR 스크리닝</div>
          <div className="dur-sub">
            단계: {step === "input" && "1. 처방전 입력"}
            {step === "list" && "2. 약 목록"}
            {step === "detail" && "3. 약 상세"}
            {step === "report" && "4. 성분 상호작용 리포트"}
          </div>
        </div>

        {error && (
          <div className="dur-card-error">
            <strong>오류</strong>
            <p style={{ margin: "4px 0 0" }}>{error}</p>
          </div>
        )}

        {/* ---- 화면 1: 처방전 입력 ---- */}
        {step === "input" && (
          <>
            <div className="dur-card">
              {drugNames.map((name, idx) => (
                <div className="dur-rx-row" key={idx}>
                  <input
                    type="text"
                    className="dur-input"
                    value={name}
                    placeholder="약품명 (예: 부루펜정200밀리그램(이부프로펜))"
                    onChange={(e) => handleChangeRow(idx, e.target.value)}
                  />
                  {drugNames.length > 1 && (
                    <button
                      type="button"
                      className="dur-icon-btn"
                      onClick={() => handleRemoveRow(idx)}
                      aria-label="삭제"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button type="button" className="dur-add" onClick={handleAddRow}>
              + 약 추가
            </button>
            <button
              type="button"
              className="dur-cta"
              disabled={isLoading}
              onClick={handleSubmitNames}
            >
              {isLoading ? "확인 중..." : "확인하기"}
            </button>
          </>
        )}

        {/* ---- 화면 2: 약 목록 ---- */}
        {step === "list" && basicResult && (
          <>
            {basicResult.unmatched_drug_names.length > 0 && (
              <div className="dur-list-summary">
                찾지 못한 약품명: {basicResult.unmatched_drug_names.join(", ")}
              </div>
            )}

            {basicResult.results.map((r) => {
              const activeFlags = r.dur_simple.filter((f) => f.present);
              return (
                <div
                  key={r.drug_detail.item_seq}
                  className="dur-card dur-drug-card"
                  onClick={() => handleSelectDrug(r)}
                >
                  <div className="dur-thumb">💊</div>
                  <div className="dur-drug-main">
                    <div>
                      <div className="dur-drug-name">{r.drug_detail.item_name}</div>
                      <div className="dur-drug-entp">{r.drug_detail.entp_name}</div>
                    </div>
                    {activeFlags.length === 0 ? (
                      <div className="dur-drug-clean">DUR 주의 사항 없음</div>
                    ) : (
                      <div className="dur-pillrow">
                        {activeFlags.map((f) => (
                          <span className="dur-pill is-danger" key={f.rule_code}>
                            <span className="dur-pill-dot" />
                            {f.rule_label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            <button
              type="button"
              className="dur-cta-soft"
              disabled={isLoading}
              onClick={handleViewReport}
            >
              {isLoading ? "불러오는 중..." : "성분 상호작용 리포트 보기 →"}
            </button>
            <button type="button" className="dur-btn-ghost" onClick={handleReset}>
              처음부터 다시
            </button>
          </>
        )}

        {/* ---- 화면 3: 약 상세 ---- */}
        {step === "detail" && selectedDrug && (
          <>
            <button type="button" className="dur-btn-ghost" onClick={() => setStep("list")}>
              ← 목록으로
            </button>

            <div className="dur-detail-head">
              <div className="dur-detail-thumb">💊</div>
              <div>
                <div className="dur-detail-name">{selectedDrug.drug_detail.item_name}</div>
                <div className="dur-detail-meta">
                  {selectedDrug.drug_detail.entp_name} · item_seq{" "}
                  {selectedDrug.drug_detail.item_seq}
                </div>
                <div style={{ marginTop: 6 }}>
                  {selectedDrug.drug_detail.etc_otc_name && (
                    <span className="dur-detail-tag">{selectedDrug.drug_detail.etc_otc_name}</span>
                  )}
                  {selectedDrug.drug_detail.form_name && (
                    <span className="dur-detail-tag">{selectedDrug.drug_detail.form_name}</span>
                  )}
                  {selectedDrug.drug_detail.atc_code && (
                    <span className="dur-detail-tag is-accent">
                      ATC {selectedDrug.drug_detail.atc_code}
                    </span>
                  )}
                  {selectedDrug.drug_detail.is_rare_drug && (
                    <span className="dur-detail-tag is-accent">희귀의약품</span>
                  )}
                  {selectedDrug.drug_detail.narcotic_kind_name && (
                    <span className="dur-detail-tag is-accent">
                      {selectedDrug.drug_detail.narcotic_kind_name}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="dur-card">
              <div className="dur-section-label">DUR 주의사항 6종</div>
              <div className="dur-pillrow" style={{ marginTop: 8 }}>
                {selectedDrug.dur_simple.map((f) => (
                  <span
                    key={f.rule_code}
                    className={`dur-pill ${f.present ? "is-danger is-present" : "is-off"}`}
                    onClick={() => f.present && handleTogglePill(f.rule_code)}
                  >
                    <span className="dur-pill-dot" />
                    {f.rule_label}
                  </span>
                ))}
              </div>
              {selectedDrug.dur_simple
                .filter((f) => f.present && expandedCodes[f.rule_code])
                .map((f) => (
                  <div className="dur-pill-expanded" key={f.rule_code}>
                    <b>{f.rule_label}</b> {f.prohbt_content}
                    {f.remark && <div style={{ marginTop: 4 }}>비고: {f.remark}</div>}
                  </div>
                ))}
            </div>

            <div className="dur-card">
              <div className="dur-section-label">효능·효과</div>
              <p className="dur-section-body">{selectedDrug.drug_detail.efcy_qesitm ?? "-"}</p>

              <div className="dur-divider">
                <div className="dur-section-label">용법·용량</div>
                <p className="dur-section-body">
                  {selectedDrug.drug_detail.use_method_qesitm ?? "-"}
                </p>
              </div>

              <div className="dur-divider">
                <div className="dur-section-label">주의사항</div>
                <p className="dur-section-body">
                  {selectedDrug.drug_detail.atpn_warn_qesitm ?? "-"}
                </p>
              </div>

              <div className="dur-divider">
                <div className="dur-section-label">부작용</div>
                <p className="dur-section-body is-muted">
                  {selectedDrug.drug_detail.se_qesitm ?? "-"}
                </p>
              </div>

              <div className="dur-divider">
                <div className="dur-section-label">보관방법</div>
                <p className="dur-section-body is-muted">
                  {selectedDrug.drug_detail.deposit_method_qesitm ?? "-"}
                </p>
              </div>
            </div>

            {selectedDrug.drug_detail.identification && (
              <div className="dur-card">
                <div className="dur-section-label">알약 식별</div>
                <div className="dur-id-grid">
                  <div className="dur-id-cell">
                    <div className="dur-id-cell-k">모양</div>
                    <div className="dur-id-cell-v">
                      {selectedDrug.drug_detail.identification.shape ?? "-"}
                    </div>
                  </div>
                  <div className="dur-id-cell">
                    <div className="dur-id-cell-k">색상</div>
                    <div className="dur-id-cell-v">
                      {selectedDrug.drug_detail.identification.color ?? "-"}
                    </div>
                  </div>
                  <div className="dur-id-cell">
                    <div className="dur-id-cell-k">마크</div>
                    <div className="dur-id-cell-v">
                      {selectedDrug.drug_detail.identification.mark ?? "-"}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* ---- 화면 4: 성분 상호작용 리포트 ---- */}
        {step === "report" && interactionResult && ingredientResult && (
          <>
            <button type="button" className="dur-btn-ghost" onClick={() => setStep("list")}>
              ← 목록으로
            </button>

            <div className="dur-report-summary">
              <div className="dur-stat">
                <div className="dur-stat-n is-danger">
                  {interactionResult.drug_intrc.interactions.length}
                </div>
                <div className="dur-stat-k">상호작용</div>
              </div>
              <div className="dur-stat">
                <div className="dur-stat-n is-warn">
                  {interactionResult.drug_intrc.recalls.length}
                </div>
                <div className="dur-stat-k">리콜</div>
              </div>
              <div className="dur-stat">
                <div className="dur-stat-n">{ingredientResult.ingredients.length}</div>
                <div className="dur-stat-k">공유 성분</div>
              </div>
            </div>

            {interactionResult.drug_intrc.interactions.map((w, idx) => (
              <div className="dur-card" key={idx}>
                <div className="dur-intrc-pair">
                  {w.drug_a.item_name} <span className="vs">↔</span> {w.drug_b.item_name}
                </div>
                <div
                  className={`dur-intrc-badge ${w.rule_type === "병용금기" ? "is-danger" : "is-warn"}`}
                >
                  {w.rule_type}
                </div>
                <p className="dur-intrc-body">{w.prohbt_content}</p>
                {w.remark && <div className="dur-intrc-remark">{w.remark}</div>}
              </div>
            ))}

            {interactionResult.drug_intrc.recalls.map((r) => (
              <div className="dur-card" key={r.item_seq}>
                <div className="dur-intrc-pair">회수: {r.item_name}</div>
                <div className="dur-drug-entp" style={{ marginTop: 2 }}>
                  {r.entp_name}
                </div>
                <div className={`dur-intrc-badge ${r.enforced ? "is-danger" : "is-warn"}`}>
                  {r.enforced ? "강제 회수" : "자율 회수"}
                </div>
                <p className="dur-intrc-body">{r.recall_reason}</p>
                <div className="dur-intrc-remark">{r.recall_command_date}</div>
              </div>
            ))}

            {ingredientResult.ingredients.length > 0 && (
              <div className="dur-card">
                <div className="dur-section-label">공유 성분 상세 (3차)</div>
                {ingredientResult.ingredients.map((ing) => (
                  <div key={ing.ingr_code} style={{ marginTop: 10 }}>
                    <span className="dur-ingr-chip">
                      {ing.ingr_name} · {ing.ingr_code}
                    </span>
                    <div className="dur-ingr-sources">
                      {ing.source_drugs
                        .map((d) =>
                          d.qnt && d.unit ? `${d.item_name}(${d.qnt}${d.unit})` : d.item_name,
                        )
                        .join(", ")}
                    </div>
                    <div className="dur-ingr-rule-list">
                      {ing.rules.map((rule, idx) => (
                        <div className="dur-ingr-rule" key={idx}>
                          <b>{rule.rule_type}</b> — {rule.prohbt_content}
                          {rule.rule_detail ? ` (${rule.rule_detail})` : ""}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
