import { useState, useEffect } from "react";
import { useMedication, type RecognitionCandidate } from "../../hooks/useMedication";

export default function MedicationPage() {
  const {
    schedules,
    isLoading,
    error,
    fetchSchedules,
    createManualSchedule,
    searchMedications,
    uploadJob,
    getJobStatus,
    confirmJob,
  } = useMedication();

  // 상태 관리
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState("pill_photo");
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<RecognitionCandidate[]>([]);
  const [extractedFields, setExtractedFields] = useState<any>(null);
  
  // 사용자 확정 폼 입력 값
  const [selectedDrugCode, setSelectedDrugCode] = useState<string>("");
  const [confirmedTimes, setConfirmedTimes] = useState<string>("09:00, 13:00, 19:00");
  const [guideCards, setGuideCards] = useState<any[]>([]);

  // 수동 등록/검색용 상태
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [manualTimes, setManualTimes] = useState("09:00, 13:00, 19:00");

  // 탭 상태 (12, 13번 확장용)
  const [activeTab, setActiveTab] = useState<"schedule" | "list" | "interaction" | "food">("schedule");

  useEffect(() => {
    fetchSchedules();
  }, []);

  // 비동기 작업 폴링 처리
  useEffect(() => {
    let intervalId: any;
    if (currentJobId && (jobStatus === "pending" || jobStatus === "processing")) {
      intervalId = setInterval(async () => {
        try {
          const res = await getJobStatus(currentJobId);
          setJobStatus(res.status);
          if (res.status === "done") {
            setCandidates(res.candidates);
            setExtractedFields(res.extracted_fields);
            if (res.candidates.length > 0) {
              setSelectedDrugCode(res.candidates[0].drug_code);
            }
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

  // 최종 등록 핸들러 (5~8번 및 9~10번 흐름)
  const handleConfirmSubmit = async () => {
    if (!currentJobId) return;
    try {
      const timesArray = confirmedTimes.split(",").map(t => t.trim()).filter(Boolean);
      const res = await confirmJob(currentJobId, selectedDrugCode || null, { times: timesArray });
      setGuideCards(res.guide_cards);
      alert("스케줄 등록 및 확정이 완료되었습니다!");
      setCurrentJobId(null);
      setJobStatus(null);
    } catch (err) {
      console.error(err);
    }
  };

  // 수동 검색 핸들러
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    const res = await searchMedications(searchQuery);
    setSearchResults(res);
  };

  // 수동 등록 핸들러
  const handleManualRegister = async (drugCode: string) => {
    try {
      const timesArray = manualTimes.split(",").map(t => t.trim()).filter(Boolean);
      await createManualSchedule(drugCode, timesArray);
      alert("수동 복약 일정이 성공적으로 등록되었습니다!");
      setSearchQuery("");
      setSearchResults([]);
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
          style={{ flex: 1, padding: "8px", fontWeight: activeTab === "schedule" ? "bold" : "normal" }}
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
          style={{ flex: 1, padding: "8px", fontWeight: activeTab === "interaction" ? "bold" : "normal" }}
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
            <form onSubmit={handleUploadSubmit} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
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
            <div style={{ border: "1px solid #ccc", padding: "15px", marginBottom: "15px", backgroundColor: "#f9f9f9" }}>
              <h4>분석 상태: {jobStatus === "pending" ? "접수 대기 중..." : jobStatus === "processing" ? "이미지 분석 및 매칭 추출 중..." : jobStatus}</h4>
              {jobStatus === "processing" && <p style={{ fontSize: "12px", color: "#666" }}>단계: 약 정보 추출 중 → 복약 시간표 생성 중...</p>}
            </div>
          )}

          {/* 5~8 단계: 분석 결과 확인 & 최종 매칭 정보 */}
          {candidates.length > 0 && (
            <div style={{ border: "1px solid #ccc", padding: "15px", marginBottom: "15px" }}>
              <h3>분석 결과 및 매칭 추천</h3>
              <p style={{ fontSize: "12px", color: "#333", backgroundColor: "#eee", padding: "5px" }}>
                <strong>인식된 raw 텍스트:</strong> {extractedFields?.ocr_raw_text}
              </p>
              
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", margin: "10px 0" }}>
                <label><strong>의약품 후보 선택 (DoD 검증용):</strong></label>
                {candidates.map((c) => (
                  <label key={c.drug_code} style={{ display: "block", cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="candidate_select"
                      value={c.drug_code}
                      checked={selectedDrugCode === c.drug_code}
                      onChange={() => setSelectedDrugCode(c.drug_code)}
                    />
                    {c.drug_name} (매칭률: {(c.match_rate * 100).toFixed(0)}%)
                  </label>
                ))}
              </div>

              {/* 9~10 단계: 복약 시간표 설정 */}
              <div style={{ display: "flex", flexDirection: "column", gap: "5px", margin: "10px 0" }}>
                <label><strong>복용 시간대 설정 (쉼표 구분):</strong></label>
                <input
                  type="text"
                  value={confirmedTimes}
                  onChange={(e) => setConfirmedTimes(e.target.value)}
                  placeholder="예: 09:00, 13:00, 19:00"
                />
              </div>

              <button onClick={handleConfirmSubmit} style={{ width: "100%", padding: "10px", backgroundColor: "#4caf50", color: "#fff", border: "none" }}>
                최종 복약 스케줄 등록 확정
              </button>
            </div>
          )}

          {/* 수동 검색Fallback (DoD 2번 요건) */}
          <div style={{ border: "1px solid #ccc", padding: "15px" }}>
            <h3>수동 약품 등록</h3>
            <div style={{ display: "flex", gap: "5px", marginBottom: "10px" }}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="검색할 약품명 입력"
              />
              <button onClick={handleSearch}>검색</button>
            </div>

            {searchResults.length > 0 && (
              <div style={{ border: "1px dashed #ccc", padding: "10px", display: "flex", flexDirection: "column", gap: "5px" }}>
                <label>복용 시간대 (수동):</label>
                <input
                  type="text"
                  value={manualTimes}
                  onChange={(e) => setManualTimes(e.target.value)}
                />
                {searchResults.map((m) => (
                  <div key={m.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px", borderBottom: "1px solid #eee" }}>
                    <span>{m.medication_name} ({m.form_type})</span>
                    <button onClick={() => handleManualRegister(m.standard_code)}>스케줄 등록</button>
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
                <div key={s.id} style={{ border: "1px solid #ccc", padding: "10px", borderRadius: "4px" }}>
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
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "interaction" && (
        <div style={{ padding: "15px", border: "1px solid #ccc" }}>
          {/* 12번 단계: 약물 상호작용 (확장 설계) */}
          <h3>약물 상호작용 체크 (DUR)</h3>
          <p style={{ color: "#666" }}>
            본 기능은 추후 연동될 약물 상호작용 분석 엔진 및 F-MED-2 기능과의 조율을 고려하여 확장 가능하도록 탭 구조로 설계되었습니다.
          </p>
          <div style={{ padding: "10px", backgroundColor: "#fffde7", border: "1px solid #fff59d" }}>
            <strong>[추후 개발 예정]</strong> 다른 처방전/알약과의 조합 시 상충되거나 중복 처방되는 위험성 감지 결과가 표시됩니다.
          </div>

          {guideCards.length > 0 && (
            <div style={{ marginTop: "15px" }}>
              <h4>임시 분석 결과 가이드:</h4>
              {guideCards.map((g, idx) => (
                <div key={idx} style={{ border: "1px solid orange", padding: "10px", marginBottom: "10px" }}>
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
            본 기능은 복용 약품과 피해야 할 음식(예: 자몽주스, 알코올 등)에 대해 분석하여 피드백을 주기 위한 확장 설계 탭 영역입니다.
          </p>
          <div style={{ padding: "10px", backgroundColor: "#e3f2fd", border: "1px solid #90caf9" }}>
            <strong>[추후 개발 예정]</strong> 식약처 공공 데이터 및 의약지침과 연계하여 섭취 주의가 필요한 음식 위험 가이드가 노출됩니다.
          </div>
        </div>
      )}

      {error && <p style={{ color: "red", marginTop: "15px" }}>에러: {error}</p>}
    </div>
  );
}
