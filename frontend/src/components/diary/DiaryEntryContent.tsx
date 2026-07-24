import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { diaryApi } from "../../api/diaryApi";
import { pinkTheme as t } from "../../theme/pinkTheme";

const MAX_IMAGE_DIMENSION = 800;
const IMAGE_QUALITY = 0.8;

/** 사진을 그대로 base64로 보내면 용량이 커서, 업로드 즉시 캔버스로 최대 800px까지 줄이고
 * JPEG 80% 품질로 압축한 뒤 data URL로 변환한다 - 이 프로젝트엔 이미지를 디스크에 저장하고
 * 다시 서빙하는 인프라가 없어 DB에 직접 저장하는데(diary_entries.image_base64), 압축 없이
 * 넣으면 DB 용량이 금방 커진다. */
function fileToCompressedDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("파일을 읽지 못했습니다."));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("이미지를 불러오지 못했습니다."));
      img.onload = () => {
        let { width, height } = img;
        if (width > MAX_IMAGE_DIMENSION || height > MAX_IMAGE_DIMENSION) {
          const scale = MAX_IMAGE_DIMENSION / Math.max(width, height);
          width = Math.round(width * scale);
          height = Math.round(height * scale);
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("캔버스를 사용할 수 없습니다."));
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", IMAGE_QUALITY));
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
}

/** 마이다이어리 > "오늘의 한 줄" 모달 본문 - 오늘 하루를 한 줄로 남기고, 사진도 1장 첨부할
 * 수 있다. 저장은 diary_entries에 영구 저장되고(하루 1건, 다시 저장하면 덮어씀), 지난 기록은
 * DiaryEntriesPage(더보기 아님, 이 모달 하단 링크로 이동)에서 볼 수 있다. */
export default function DiaryEntryContent() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [content, setContent] = useState("");
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    diaryApi
      .getToday()
      .then((result) => {
        if (result.entry) {
          setContent(result.entry.content);
          setImageBase64(result.entry.image_base64);
        }
      })
      .finally(() => setLoadingInitial(false));
  }, []);

  async function handleImageSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImageError(null);
    try {
      setImageBase64(await fileToCompressedDataUrl(file));
    } catch (err) {
      setImageError(err instanceof Error ? err.message : "사진을 불러오지 못했습니다.");
    }
  }

  async function handleSave() {
    if (!content.trim()) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      await diaryApi.saveToday({ content: content.trim(), image_base64: imageBase64 ?? undefined });
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  }

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
      <p style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 700, color: t.primary }}>
        오늘의 마음을 담아주세요.
      </p>
      <p style={{ margin: "0 0 16px", fontSize: 13, color: t.textMuted }}>
        당신의 하루를 한 줄로 담아보세요.
      </p>

      {loadingInitial ? (
        <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>
      ) : (
        <>
          <textarea
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setSaved(false);
            }}
            placeholder="오늘 하루는 어땠나요?"
            rows={4}
            style={{
              width: "100%",
              boxSizing: "border-box",
              padding: "12px 14px",
              border: `1px solid ${t.border}`,
              borderRadius: 12,
              fontSize: 14,
              color: t.text,
              resize: "vertical",
              outline: "none",
              fontFamily: "inherit",
              marginBottom: 10,
            }}
          />

          {imageBase64 && (
            <div style={{ position: "relative", marginBottom: 10 }}>
              <img
                src={imageBase64}
                alt="첨부한 사진"
                style={{ width: "100%", borderRadius: 12, display: "block" }}
              />
              <button
                type="button"
                onClick={() => setImageBase64(null)}
                aria-label="사진 삭제"
                style={{
                  position: "absolute",
                  top: 8,
                  right: 8,
                  border: "none",
                  borderRadius: "50%",
                  width: 28,
                  height: 28,
                  background: "rgba(90, 74, 78, 0.6)",
                  color: "#fff",
                  fontSize: 14,
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageSelect}
            style={{ display: "none" }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            style={{
              width: "100%",
              padding: "10px 0",
              marginBottom: 10,
              borderRadius: 10,
              border: `1.5px dashed ${t.border}`,
              background: t.pageBg,
              color: t.textMuted,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {imageBase64 ? "📷 다른 사진으로 바꾸기" : "📷 사진 추가하기(선택)"}
          </button>
          {imageError && (
            <p style={{ color: t.danger, fontSize: 12, margin: "0 0 10px" }}>{imageError}</p>
          )}

          {saveError && (
            <p style={{ color: t.danger, fontSize: 13, margin: "0 0 10px" }}>{saveError}</p>
          )}

          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !content.trim()}
            style={{
              width: "100%",
              padding: "14px 0",
              borderRadius: 12,
              border: "none",
              background: t.primary,
              color: "#fff",
              fontSize: 15,
              fontWeight: 700,
              cursor: saving || !content.trim() ? "default" : "pointer",
              opacity: !content.trim() ? 0.5 : 1,
            }}
          >
            {saving ? "저장하는 중..." : "저장"}
          </button>

          {saved && (
            <p style={{ margin: "10px 0 0", fontSize: 13, color: t.success, textAlign: "center" }}>
              ✓ 오늘의 한 줄이 저장됐어요.
            </p>
          )}

          <button
            type="button"
            onClick={() => navigate("/diary")}
            style={{
              display: "block",
              width: "100%",
              marginTop: 14,
              padding: 0,
              border: "none",
              background: "none",
              color: t.textMuted,
              fontSize: 12.5,
              textAlign: "center",
              cursor: "pointer",
            }}
          >
            지난 기록 모아보기 →
          </button>
        </>
      )}
    </div>
  );
}
