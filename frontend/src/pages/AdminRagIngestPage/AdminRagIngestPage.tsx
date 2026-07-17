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
            {/* 컬렉션은 도메인이 아니라 다루는 방식으로 갈린다: CSV는 행이 곧 레코드라
                안 자르고(structured), 논문/안내서는 산문이라 자른다(unstructured).
                검색은 메타데이터 필터로 원하는 걸 골라내므로 도메인별로 쪼갤 이유가 없다. */}
            <li>구조화 문서(CSV — DUR 규칙 + e약은요): {status.structured_count}건</li>
            <li>산문 문서(논문 + 복약안내서): {status.unstructured_count}건</li>
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

      {/* source/는 드롭 폴더다. 넣으면 색인된다 — 등록 절차가 없다. 예전엔 매니페스트에
          등록해야만 색인돼서, 파일을 넣어도 아무 일도 아무 말도 없었다.
          이제 어긋날 수 있는 건 "읽을 줄 모르는 확장자" 하나뿐이라 그것만 드러낸다. */}
      <section style={{ marginBottom: 24 }}>
        <h2>source/ 드롭 폴더 상태</h2>
        {status ? (
          <ul>
            <li>색인 대상: {status.sources.indexed.length}개</li>
            {status.sources.unsupported.length > 0 && (
              <li>
                <strong>읽을 수 없음: {status.sources.unsupported.join(", ")}</strong>
                <br />
                <small>확장자를 읽을 줄 몰라 건너뜁니다. 지원 형식: .csv / .json / .md / .pdf</small>
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
