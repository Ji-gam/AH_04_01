import { useState, useEffect } from "react";
import {
  useMedication,
  type InteractionCheckResult,
  type RecognitionCandidate,
  type RecognitionJobResult,
} from "../../hooks/useMedication";
import { useAuth } from "../../hooks/useAuth";

type ExtractedFields = NonNullable<RecognitionJobResult["extracted_fields"]>;
type GuideCard = { title: string; content: string; severity?: string; disclaimer?: string };

export default function MedicationPage() {
  const { user } = useAuth();
  const {
    schedules,
    isLoading,
    error,
    fetchSchedules,
    createManualSchedule,
    quickRegister,
    deleteSchedule,
    uploadJob,
    getJobStatus,
    confirmJob,
    checkInteractions,
  } = useMedication();

  // 상태 관리
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState("pill_photo");
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<RecognitionCandidate[]>([]);
  const [extractedFields, setExtractedFields] = useState<ExtractedFields | null>(null);

  // 사용자 확정 폼 입력 값 (처방전 한 장에 여러 약이 인식될 수 있어 다중 선택 지원)
  const [selectedDrugCodes, setSelectedDrugCodes] = useState<string[]>([]);
  const [confirmedTimes, setConfirmedTimes] = useState<string>("09:00, 13:00, 19:00");
  const [guideCards, setGuideCards] = useState<GuideCard[]>([]);

  // 수동 등록용 상태 — 약품명을 입력하고 등록 버튼 한 번으로 끝나는 게 기본 플로우(T-MED-3),
  // 이름이 여러 약과 부분일치할 때만 후보 목록을 보여줘 그중 하나를 고르게 한다.
  const [quickDrugName, setQuickDrugName] = useState("");
  const [manualTimes, setManualTimes] = useState("09:00, 13:00, 19:00");
  const [hospitalName, setHospitalName] = useState(""); // 처방 병원명(선택) — 복약 시간표에 표시 (T-NTFY-2)
  const [quickCandidates, setQuickCandidates] = useState<
    Array<{ drug_code: string; medication_name: string; form_type: string | null }>
  >([]);

  // 탭 상태 (12, 13번 확장용)
  const [activeTab, setActiveTab] = useState<"schedule" | "list" | "interaction" | "food">(
    "schedule",
  );

  // 약물 상호작용(병용금기) 체크 — 등록약이 바뀌지 않는 한 다시 조회하지 않도록 캐시 (T-MED-2-2)
  const [interactionResult, setInteractionResult] = useState<InteractionCheckResult | null>(null);
  const [interactionLoading, setInteractionLoading] = useState(false);
  const [interactionError, setInteractionError] = useState<string | null>(null);

  useEffect(() => {
    fetchSchedules();
  }, []);

  // 등록약 목록이 바뀌면(추가/삭제) 캐시를 무효화해 다음에 탭을 열 때 재조회한다.
  useEffect(() => {
    setInteractionResult(null);
  }, [schedules.length]);

  useEffect(() => {
    if (activeTab !== "interaction" || interactionResult || interactionLoading) return;
    setInteractionLoading(true);
    setInteractionError(null);
    checkInteractions()
      .then(setInteractionResult)
      .catch((err: unknown) => {
        setInteractionError(err instanceof Error ? err.message : "상호작용 확인에 실패했습니다.");
      })
      .finally(() => setInteractionLoading(false));
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

  // 분석 시작 핸들러 (1~4번 흐름)
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    try {
      setCandidates([]);
      setExtractedFields(null);
      setGuideCards([]);
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
      const allGuideCards: GuideCard[] = [];
      for (const drugCode of selectedDrugCodes) {
        const res = await confirmJob(currentJobId, drugCode, { times: timesArray });
        allGuideCards.push(...res.guide_cards);
      }
      setGuideCards(allGuideCards);
      alert(`${selectedDrugCodes.length}개 약품의 복약 스케줄 등록이 완료되었습니다!`);
      setCurrentJobId(null);
      setJobStatus(null);
    } catch (err) {
      console.error(err);
    }
  };

  // 약품명 입력 → 바로 등록 핸들러 (T-MED-3). 정확히 하나만 일치하면 즉시 등록되고,
  // 전혀 일치하지 않으면 새 약품을 즉석 생성해서라도 등록된다. 여러 개가 부분일치할 때만
  // 후보 목록을 보여주고, 그중 하나를 고르면 기존 createManualSchedule로 확정 등록한다.
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
        setQuickCandidates([]);
      } else {
        // 여러 약과 부분일치 — 사용자가 직접 골라야 하므로 후보만 보여주고 자동 등록하지 않는다.
        setQuickCandidates(res.candidates);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 부분일치 후보 중 하나를 사용자가 선택해 최종 등록하는 핸들러
  const handleSelectCandidate = async (drugCode: string) => {
    try {
      const timesArray = manualTimes
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await createManualSchedule(drugCode, timesArray, hospitalName.trim() || null);
      alert("복약 일정이 성공적으로 등록되었습니다!");
      setQuickDrugName("");
      setHospitalName("");
      setQuickCandidates([]);
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

  return (
    <div style={{ maxWidth: 480, margin: "20px auto", padding: "10px", fontFamily: "sans-serif" }}>
      <h1>복약 관리 (T-MED-1)</h1>

      {/* 탭 네비게이션 (시간표, 목록, 상호작용, 음식) */}
      <div style={{ display: "flex", gap: "5px", marginBottom: "15px" }}>
        <button
          onClick={() => setActiveTab("schedule")}
          style={{
            flex: 1,
            padding: "8px",
            fontWeight: activeTab === "schedule" ? "bold" : "normal",
          }}
        >
          시간표 / 분석
        </button>
        <button
          onClick={() => setActiveTab("list")}
          style={{ flex: 1, padding: "8px", fontWeight: activeTab === "list" ? "bold" : "normal" }}
        >
          등록 목록
        </button>
        <button
          onClick={() => setActiveTab("interaction")}
          style={{
            flex: 1,
            padding: "8px",
            fontWeight: activeTab === "interaction" ? "bold" : "normal",
          }}
        >
          조합 (12번)
        </button>
        <button
          onClick={() => setActiveTab("food")}
          style={{ flex: 1, padding: "8px", fontWeight: activeTab === "food" ? "bold" : "normal" }}
        >
          음식 (13번)
        </button>
      </div>

      {activeTab === "schedule" && (
        <div>
          {/* 1~3 단계: 분석 사진/처방전 업로드 */}
          <div style={{ border: "1px solid #ccc", padding: "15px", marginBottom: "15px" }}>
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
              <button type="submit" disabled={isLoading}>
                {isLoading ? "업로드 중..." : "처방전/알약 분석하기"}
              </button>
            </form>
          </div>

          {/* 4단계: 분석 진행 상태 노출 */}
          {jobStatus && (
            <div
              style={{
                border: "1px solid #ccc",
                padding: "15px",
                marginBottom: "15px",
                backgroundColor: "#f9f9f9",
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
                <p style={{ fontSize: "12px", color: "#666" }}>
                  단계: 약 정보 추출 중 → 복약 시간표 생성 중...
                </p>
              )}
            </div>
          )}

          {/* 5~8 단계: 분석 결과 확인 & 최종 매칭 정보 */}
          {candidates.length > 0 && (
            <div style={{ border: "1px solid #ccc", padding: "15px", marginBottom: "15px" }}>
              <h3>분석 결과 및 매칭 추천</h3>
              <p
                style={{ fontSize: "12px", color: "#333", backgroundColor: "#eee", padding: "5px" }}
              >
                <strong>인식된 raw 텍스트:</strong> {extractedFields?.ocr_raw_text}
              </p>

              <div
                style={{ display: "flex", flexDirection: "column", gap: "10px", margin: "10px 0" }}
              >
                <label>
                  <strong>의약품 후보 선택 (처방전에 여러 약이 있으면 전부 선택 가능):</strong>
                </label>
                {candidates.map((c) => (
                  <label key={c.drug_code} style={{ display: "block", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      value={c.drug_code}
                      checked={selectedDrugCodes.includes(c.drug_code)}
                      onChange={(e) =>
                        setSelectedDrugCodes((prev) =>
                          e.target.checked
                            ? [...prev, c.drug_code]
                            : prev.filter((code) => code !== c.drug_code),
                        )
                      }
                    />
                    {c.drug_name} (매칭률: {(c.match_rate * 100).toFixed(0)}%)
                    {c.match_rate < 0.6 && (
                      <span style={{ color: "#b26a00", fontSize: "11px" }}>
                        {" "}
                        — 마스터 DB 미등록, 신규 인식
                      </span>
                    )}
                  </label>
                ))}
              </div>

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

          {/* 수동 약품 등록 (T-MED-1 DoD 2번: 등록 자체는 막히지 않아야 한다 / T-MED-3: 약품명 입력 →
              바로 등록 한 단계로 개선) */}
          <div style={{ border: "1px solid #ccc", padding: "15px" }}>
            <h3>수동 약품 등록</h3>
            <p style={{ fontSize: "12px", color: "#666" }}>
              약품명을 입력하고 등록 버튼을 누르면 바로 복약 일정이 등록됩니다. 마스터 DB에 없는
              약도 새로 등록되며(OCR과 동일한 정책), 여러 약과 이름이 겹칠 때만 아래에 선택 목록이
              뜹니다.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "5px", margin: "10px 0" }}>
              <label>복용 시간대 (쉼표 구분):</label>
              <input
                type="text"
                value={manualTimes}
                onChange={(e) => setManualTimes(e.target.value)}
              />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "5px", margin: "10px 0" }}>
              <label>처방 병원명 (선택):</label>
              <input
                type="text"
                value={hospitalName}
                onChange={(e) => setHospitalName(e.target.value)}
                placeholder="예: 서울건강내과"
              />
            </div>
            <div style={{ display: "flex", gap: "5px", marginBottom: "10px" }}>
              <input
                type="text"
                value={quickDrugName}
                onChange={(e) => setQuickDrugName(e.target.value)}
                placeholder="등록할 약품명 입력"
                style={{ flex: 1 }}
              />
              <button onClick={handleQuickRegister} disabled={isLoading || !quickDrugName.trim()}>
                등록
              </button>
            </div>

            {quickCandidates.length > 0 && (
              <div
                style={{
                  border: "1px dashed #ccc",
                  padding: "10px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "5px",
                }}
              >
                <label style={{ fontSize: "13px", color: "#b26a00" }}>
                  여러 약품과 이름이 겹칩니다. 등록할 약품을 선택해주세요:
                </label>
                {quickCandidates.map((m) => (
                  <div
                    key={m.drug_code}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "5px",
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    <span>
                      {m.medication_name} ({m.form_type})
                    </span>
                    <button onClick={() => handleSelectCandidate(m.drug_code)}>이걸로 등록</button>
                  </div>
                ))}
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
                    border: "1px solid #ccc",
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
                      <span style={{ fontSize: "11px", color: "green" }}>
                        ✓ OCR 인식을 통해 자동 등록됨
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => handleDeleteSchedule(s.id)}
                    disabled={isLoading}
                    style={{
                      backgroundColor: "#e53935",
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
        <div style={{ padding: "15px", border: "1px solid #ccc" }}>
          {/* 12번 단계: 약물 상호작용 (T-MED-2-2) — 등록약 간 병용금기(DUR) 체크 */}
          <h3>약물 상호작용 체크 (DUR)</h3>
          <p style={{ color: "#666" }}>
            등록하신 약들을 서로 대조해 식약처 병용금기 데이터에서 함께 복용하면 위험한 조합이
            있는지 확인합니다. 지병(질병)과의 상충 여부는 아직 포함되지 않습니다.
          </p>

          {interactionLoading && <p>등록약을 대조하는 중입니다...</p>}

          {!interactionLoading && interactionError && (
            <div style={{ padding: "10px", backgroundColor: "#fdecea", border: "1px solid #f5c6cb" }}>
              {interactionError}
            </div>
          )}

          {!interactionLoading && !interactionError && interactionResult && (
            <>
              {interactionResult.checked_count < 2 ? (
                <div style={{ padding: "10px", backgroundColor: "#fffde7", border: "1px solid #fff59d" }}>
                  비교할 수 있는 등록약이 2개 미만이라 상호작용을 확인할 수 없습니다.
                </div>
              ) : interactionResult.warnings.length === 0 ? (
                <div style={{ padding: "10px", backgroundColor: "#e8f5e9", border: "1px solid #a5d6a7" }}>
                  등록하신 약들 사이에서 확인된 병용금기 조합이 없습니다.
                </div>
              ) : (
                interactionResult.warnings.map((w, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: "10px",
                      marginBottom: "10px",
                      backgroundColor: "#fdecea",
                      border: "1px solid #f5c6cb",
                    }}
                  >
                    <strong>
                      ⚠ {w.drug_a_name} + {w.drug_b_name}
                    </strong>
                    <p>{w.description}</p>
                    <small style={{ color: "#666" }}>{w.disclaimer}</small>
                  </div>
                ))
              )}
            </>
          )}

          {guideCards.length > 0 && (
            <div style={{ marginTop: "15px" }}>
              <h4>임시 분석 결과 가이드:</h4>
              {guideCards.map((g, idx) => (
                <div
                  key={idx}
                  style={{ border: "1px solid orange", padding: "10px", marginBottom: "10px" }}
                >
                  <h5>{g.title}</h5>
                  <p>{g.content}</p>
                  <small style={{ color: "red" }}>{g.disclaimer}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "food" && (
        <div style={{ padding: "15px", border: "1px solid #ccc" }}>
          {/* 13번 단계: 음식 주의사항 (확장 설계) */}
          <h3>식품 상호작용 체크</h3>
          <p style={{ color: "#666" }}>
            본 기능은 복용 약품과 피해야 할 음식(예: 자몽주스, 알코올 등)에 대해 분석하여 피드백을
            주기 위한 확장 설계 탭 영역입니다.
          </p>
          <div style={{ padding: "10px", backgroundColor: "#e3f2fd", border: "1px solid #90caf9" }}>
            <strong>[추후 개발 예정]</strong> 식약처 공공 데이터 및 의약지침과 연계하여 섭취 주의가
            필요한 음식 위험 가이드가 노출됩니다.
          </div>
        </div>
      )}

      {error && <p style={{ color: "red", marginTop: "15px" }}>에러: {error}</p>}
    </div>
  );
}
