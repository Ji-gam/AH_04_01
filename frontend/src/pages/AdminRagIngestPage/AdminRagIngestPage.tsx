import { useEffect, useState } from "react";

import { adminApi } from "../../api/adminApi";
import type { IngestStatusResult } from "../../api/types";

/** T-ADMIN-1: RAG 인제스트 트리거 화면. 관리자 전용, 스타일링 없음. */
export default function AdminRagIngestPage() {
  const [status, setStatus] = useState<IngestStatusResult | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const loadStatus = () => adminApi.getIngestStatus().then(setStatus);

  useEffect(() => {
    loadStatus();
  }, []);

  const handleUploadCsv = async () => {
    if (!csvFile) return;
    setIsBusy(true);
    setMessage(null);
    try {
      const result = await adminApi.uploadCsv(csvFile);
      const base = `인제스트 완료: ${result.filename} — 삭제 ${result.deleted}건, 신규/갱신 ${result.ingested}건 (전체 ${result.collection_count}건)`;
      setMessage(result.errors.length > 0 ? `${base}\n경고: ${result.errors.join("; ")}` : base);
      await loadStatus();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "업로드 실패");
    } finally {
      setIsBusy(false);
    }
  };

  const handleResetDur = async () => {
    setIsBusy(true);
    setMessage(null);
    try {
      await adminApi.resetDurCollection();
      setMessage("DUR 컬렉션 리셋 완료");
      await loadStatus();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "리셋 실패");
    } finally {
      setIsBusy(false);
    }
  };

  const handleTriggerPapers = async () => {
    setIsBusy(true);
    setMessage(null);
    try {
      const result = await adminApi.triggerPaperIngest();
      setMessage(`논문 인제스트 트리거됨: ${result.status}`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "트리거 실패");
    } finally {
      setIsBusy(false);
    }
  };

  const handleResetPapers = async () => {
    setIsBusy(true);
    setMessage(null);
    try {
      await adminApi.resetPaperCollection();
      setMessage("논문 컬렉션 리셋 완료");
      await loadStatus();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "리셋 실패");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <h1>RAG 소스 인제스트</h1>

      <section style={{ marginBottom: 24 }}>
        <h2>현재 상태</h2>
        {status ? (
          <ul>
            <li>dur_rules 문서 수: {status.dur_rules_count}</li>
            <li>pubmed_papers 문서 수: {status.pubmed_papers_count}</li>
            <li>
              질환별 원본 논문 파일 건수:{" "}
              {Object.entries(status.papers_raw_counts)
                .map(([disease, count]) => `${disease}=${count}`)
                .join(", ")}
            </li>
          </ul>
        ) : (
          <p>로딩 중...</p>
        )}
      </section>

      {/* source/는 드롭 폴더다. 예전엔 등록 안 된 파일을 조용히 무시해서, 데이터를 넣어도
          아무 일도 아무 말도 없었다. 여기서 그걸 드러낸다. */}
      <section style={{ marginBottom: 24 }}>
        <h2>source/ 폴더 상태</h2>
        {status ? (
          <ul>
            <li>색인 대상: {status.sources.indexed.length}개</li>
            <li>RAG 제외(의도적): {status.sources.excluded.length}개</li>
            <li>
              <strong>미등록: {status.sources.unregistered.length}개</strong>
              {status.sources.unregistered.length > 0 && (
                <>
                  {" — "}
                  {status.sources.unregistered.join(", ")}
                  <br />
                  <small>
                    source/에 있지만 _manifest.yaml에 없어 색인되지 않습니다. 쓰려면 매니페스트에 등록하세요.
                  </small>
                </>
              )}
            </li>
            {status.sources.missing.length > 0 && (
              <li>
                <strong>파일 없음: {status.sources.missing.join(", ")}</strong>
                <br />
                <small>매니페스트에 선언됐지만 source/에 파일이 없습니다.</small>
              </li>
            )}
          </ul>
        ) : (
          <p>로딩 중...</p>
        )}
      </section>

      <section style={{ marginBottom: 24 }}>
        <h2>DUR CSV 업로드</h2>
        <input
          type="file"
          accept=".csv"
          onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
        />
        <button onClick={handleUploadCsv} disabled={!csvFile || isBusy} style={{ marginLeft: 8 }}>
          업로드 + 인제스트
        </button>
        <button onClick={handleResetDur} disabled={isBusy} style={{ marginLeft: 8 }}>
          DUR 컬렉션 리셋
        </button>
      </section>

      <section style={{ marginBottom: 24 }}>
        <h2>논문(PubMed) 인제스트</h2>
        <button onClick={handleTriggerPapers} disabled={isBusy}>
          파이프라인 트리거
        </button>
        <button onClick={handleResetPapers} disabled={isBusy} style={{ marginLeft: 8 }}>
          컬렉션 리셋
        </button>
      </section>

      {message && <p>{message}</p>}
    </div>
  );
}
