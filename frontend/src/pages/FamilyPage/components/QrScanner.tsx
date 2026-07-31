import jsQR from "jsqr";
import { useEffect, useRef, useState } from "react";

import { pinkTheme as t } from "../../../theme/pinkTheme";

interface Props {
  onScan: (text: string) => void;
  onClose: () => void;
}

/** 카메라로 QR코드를 찍어서 텍스트(초대코드)를 읽어낸다. 매 프레임을 캔버스에 그려서
 * jsQR로 디코딩하는, QR 스캐너의 표준적인 구현 방식이다 - 별도 네이티브 앱 없이 브라우저
 * 카메라 API(getUserMedia)만으로 동작한다. */
export default function QrScanner({ onScan, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        tick();
      } catch (err) {
        setError(
          err instanceof Error
            ? `카메라를 열 수 없어요. (${err.message})`
            : "카메라를 열 수 없어요.",
        );
      }
    }

    function tick() {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (video && canvas && video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const code = jsQR(imageData.data, imageData.width, imageData.height);
          if (code && code.data) {
            onScan(code.data);
            return; // 스캔 성공 - 더 이상 반복 안 함 (부모가 곧 이 컴포넌트를 닫을 것)
          }
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    }

    start();

    return () => {
      cancelled = true;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        alignItems: "center",
      }}
    >
      <p style={{ margin: 0, fontWeight: 600, color: t.text, fontSize: 14 }}>
        📷 상대방의 QR코드를 카메라에 비춰주세요
      </p>
      {error ? (
        <p style={{ margin: 0, color: t.danger, fontSize: 13, textAlign: "center" }}>{error}</p>
      ) : (
        <video
          ref={videoRef}
          playsInline
          muted
          style={{
            width: "100%",
            maxWidth: 320,
            borderRadius: 12,
            background: "#000",
          }}
        />
      )}
      <canvas ref={canvasRef} style={{ display: "none" }} />
      <button
        type="button"
        onClick={onClose}
        style={{
          padding: "10px 20px",
          border: `1px solid ${t.border}`,
          borderRadius: 10,
          background: t.cardBg,
          color: t.textMuted,
          cursor: "pointer",
        }}
      >
        취소
      </button>
    </div>
  );
}
