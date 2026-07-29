import { FolderOpen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import PageTitle from "../../components/common/PageTitle";
import { useMedication, type RecognitionJobSummary } from "../../hooks/useMedication";
import { pinkTheme as t } from "../../theme/pinkTheme";
import Modal from "../AlarmPage/components/Modal";
import ToggleSwitch from "../AlarmPage/components/ToggleSwitch";

const SOURCE_TYPE_LABELS: Record<string, string> = {
  pill_photo: "💊 알약 사진",
  prescription: "📄 처방전",
  medical_record: "🏥 진료기록",
  medication_guide: "🧾 약봉투/복약안내문",
};

function formatDateHeader(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });
}

/** created_at(ISO) 기준 날짜별로 묶는다 - 최신순 정렬은 API가 이미 보장한다. */
function groupByDate(jobs: RecognitionJobSummary[]): Array<[string, RecognitionJobSummary[]]> {
  const groups = new Map<string, RecognitionJobSummary[]>();
  for (const job of jobs) {
    const key = formatDateHeader(job.created_at);
    const list = groups.get(key);
    if (list) {
      list.push(job);
    } else {
      groups.set(key, [job]);
    }
  }
  return Array.from(groups.entries());
}

/**
 * REQ-DOC-003: "내 문서함" - 촬영/업로드한 원본 문서(처방전/약봉투/진료기록/알약사진)를
 * 날짜별로 다시 열람하거나, 원본+추출데이터를 완전히 삭제할 수 있는 화면. 본인 전용이며,
 * 가족(보호자) 공개 여부는 이 화면에서 직접 토글한다(기본 비공개).
 */
export default function DocumentBoxPage() {
  const navigate = useNavigate();
  const {
    listRecognitionJobs,
    getRecognitionJobImageBlob,
    deleteRecognitionJobDocument,
    getGuardianDocumentAccess,
    setGuardianDocumentAccess,
  } = useMedication();

  const [jobs, setJobs] = useState<RecognitionJobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [guardianAccess, setGuardianAccessState] = useState(false);
  const [viewingJobId, setViewingJobId] = useState<string | null>(null);
  const [viewingImageUrl, setViewingImageUrl] = useState<string | null>(null);
  const [viewingError, setViewingError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [jobList, allowGuardian] = await Promise.all([
        listRecognitionJobs(),
        getGuardianDocumentAccess(),
      ]);
      setJobs(jobList);
      setGuardianAccessState(allowGuardian);
    } catch {
      setError("문서함을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [listRecognitionJobs, getGuardianDocumentAccess]);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 모달을 닫거나 언마운트될 때 blob URL을 정리해 메모리 누수를 막는다.
  useEffect(() => {
    return () => {
      if (viewingImageUrl) URL.revokeObjectURL(viewingImageUrl);
    };
  }, [viewingImageUrl]);

  const handleToggleGuardianAccess = async () => {
    const next = !guardianAccess;
    setGuardianAccessState(next); // 낙관적 반영
    try {
      await setGuardianDocumentAccess(next);
    } catch {
      setGuardianAccessState(!next); // 실패 시 되돌림
      setError("가족 공개 설정을 저장하지 못했습니다.");
    }
  };

  const openViewer = async (job: RecognitionJobSummary) => {
    if (!job.has_image) return;
    setViewingJobId(job.job_id);
    setViewingError(null);
    setViewingImageUrl(null);
    try {
      const blob = await getRecognitionJobImageBlob(job.job_id);
      setViewingImageUrl(URL.createObjectURL(blob));
    } catch {
      setViewingError("이미지를 불러오지 못했습니다.");
    }
  };

  const closeViewer = () => {
    setViewingJobId(null);
    setViewingImageUrl(null);
    setViewingError(null);
  };

  const handleDelete = async (jobId: string) => {
    if (!window.confirm("이 문서와 추출된 정보를 완전히 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")) {
      return;
    }
    try {
      await deleteRecognitionJobDocument(jobId);
      if (viewingJobId === jobId) closeViewer();
      await reload();
    } catch {
      setError("문서를 삭제하지 못했습니다.");
    }
  };

  const dateGroups = groupByDate(jobs);

  return (
    <div style={{ background: t.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{ background: "none", border: "none", color: t.textMuted, padding: 0, marginBottom: 12, cursor: "pointer" }}
        >
          ← 뒤로가기
        </button>
        <PageTitle icon={FolderOpen} style={{ marginBottom: 6 }}>
          내 문서함
        </PageTitle>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: t.textMuted, lineHeight: 1.5 }}>
          촬영/업로드한 처방전·약봉투·진료기록을 날짜별로 다시 볼 수 있어요. 더 이상 필요 없다면
          완전히 삭제할 수 있습니다.
        </p>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            padding: "14px 12px",
            marginBottom: 16,
            borderRadius: 12,
            background: t.cardBg,
            border: `1px solid ${t.border}`,
          }}
        >
          <span>
            <p style={{ fontSize: 14, fontWeight: 700, color: t.text, margin: 0 }}>
              가족에게 문서 이미지 공개
            </p>
            <p style={{ fontSize: 12.5, color: t.textMuted, margin: "3px 0 0" }}>
              켜면 승인된 보호자가 이 문서함의 원본 이미지를 볼 수 있어요 (삭제는 항상 본인만 가능).
              기본값은 비공개입니다.
            </p>
          </span>
          <ToggleSwitch
            checked={guardianAccess}
            onChange={handleToggleGuardianAccess}
            ariaLabel="가족에게 문서 이미지 공개"
          />
        </div>

        {loading && <p style={{ color: t.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>}

        {!loading && jobs.length === 0 && (
          <p style={{ color: t.textMuted, fontSize: 14, textAlign: "center", padding: "32px 0" }}>
            아직 보관된 문서가 없어요.
          </p>
        )}

        {dateGroups.map(([dateLabel, items]) => (
          <div key={dateLabel} style={{ marginBottom: 18 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: t.textMuted, margin: "0 0 8px" }}>
              {dateLabel}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {items.map((job) => (
                <div
                  key={job.job_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 10,
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: t.cardBg,
                    border: `1px solid ${t.border}`,
                  }}
                >
                  <button
                    type="button"
                    onClick={() => openViewer(job)}
                    disabled={!job.has_image}
                    style={{
                      flex: 1,
                      textAlign: "left",
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: job.has_image ? "pointer" : "default",
                    }}
                  >
                    <p style={{ fontSize: 14, fontWeight: 600, color: t.text, margin: 0 }}>
                      {SOURCE_TYPE_LABELS[job.source_type] ?? job.source_type}
                    </p>
                    <p style={{ fontSize: 12.5, color: t.textMuted, margin: "3px 0 0" }}>
                      {job.has_image ? "탭해서 보기" : "이미지 없음"}
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(job.job_id)}
                    style={{
                      background: "none",
                      border: `1px solid ${t.border}`,
                      borderRadius: 8,
                      padding: "6px 10px",
                      color: t.danger,
                      fontSize: 12.5,
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    삭제
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {viewingJobId && (
        <Modal onClose={closeViewer}>
          <div style={{ background: t.cardBg, borderRadius: 16, padding: 16 }}>
            {viewingError && <p style={{ color: t.danger, fontSize: 13 }}>{viewingError}</p>}
            {!viewingError && !viewingImageUrl && (
              <p style={{ color: t.textMuted, fontSize: 14, textAlign: "center", padding: "40px 0" }}>
                불러오는 중...
              </p>
            )}
            {viewingImageUrl && (
              <img
                src={viewingImageUrl}
                alt="원본 문서"
                style={{ width: "100%", borderRadius: 10, display: "block" }}
              />
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
