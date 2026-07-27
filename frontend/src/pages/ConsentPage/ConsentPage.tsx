import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import PageTitle from "../../components/common/PageTitle";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";
import { hasConsented, markConsented } from "../../utils/healthInfoConsent";

/** 개인건강정보로 들어가는 모든 경로(홈 배너 "확인", 더보기 > 개인건강정보 링크 등)가 공통으로
 * 경유하는 개인정보(민감정보=건강정보) 제공동의 화면. 개인정보보호법 제23조 - 민감정보는 다른
 * 동의와 별도로, 동의를 먼저 받고 나서 수집해야 한다. 한 번 동의하면 다음부터는 자동으로 건너뛴다
 * (계정별로 localStorage에 기억). 동의해야만 다음(개인건강정보 입력)으로 넘어갈 수 있다.
 *
 * [2026-07-24] AI 챗봇 데이터 활용 동의를 여기 같이 넣었다가, 위치/문구/저장 방식을 더
 * 논의하기로 하고 롤백함(대화 저장 기능 자체를 아직 안 만든 상태라 서두를 필요 없음) - 다음
 * 논의 때 챗봇 화면(ChatPage) 진입 시점 등 다른 위치를 검토할 예정. */
export default function ConsentPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    if (user && hasConsented(user.email)) {
      navigate("/health-info", { replace: true });
    }
  }, [navigate, user]);

  function handleAgreeAndContinue() {
    if (user) markConsented(user.email);
    navigate("/health-info", { replace: true });
  }

  return (
    <div
      style={{
        minHeight: "100%",
        background: pinkTheme.pageBg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 360,
          background: pinkTheme.cardBg,
          border: `1px solid ${pinkTheme.border}`,
          borderRadius: "16px",
          padding: "24px",
          boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
        }}
      >
        <button
          type="button"
          onClick={() => navigate("/")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 12,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>

        <PageTitle icon={ShieldCheck} style={{ marginBottom: 12 }}>
          개인정보(건강정보) 제공동의
        </PageTitle>
        <div
          style={{
            background: pinkTheme.cardBg,
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: 16,
            padding: 18,
            fontSize: 13,
            color: pinkTheme.textMuted,
            lineHeight: 1.6,
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          <p style={{ margin: 0 }}>
            건강정보(나이, 성별, 키, 체중, 진단병력, 가족력 등)는 「개인정보 보호법」상 민감정보에
            해당하며, 서비스 이용을 위해 아래 목적으로만 수집·이용됩니다.
          </p>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            <li>맞춤형 건강관리 콘텐츠 및 복약 정보 제공</li>
            <li>서비스 품질 개선을 위한 통계 분석(비식별 처리)</li>
          </ul>
          <p style={{ margin: "8px 0 0" }}>
            수집된 정보는 회원 탈퇴 시 지체없이 파기되며, 동의하지 않으셔도 됩니다(다만 동의하지
            않으면 개인건강관리 기능은 이용할 수 없어요).
          </p>
        </div>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            margin: "16px 0",
            fontSize: 14,
            color: pinkTheme.text,
          }}
        >
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />위
          내용에 동의합니다. (필수)
        </label>

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            type="button"
            onClick={handleAgreeAndContinue}
            disabled={!agreed}
            style={{
              flex: 1,
              padding: "12px",
              border: "none",
              borderRadius: "10px",
              background: agreed ? pinkTheme.primary : pinkTheme.border,
              color: "#fff",
              fontWeight: 700,
              cursor: agreed ? "pointer" : "not-allowed",
            }}
          >
            동의하고 계속하기
          </button>
          <button
            type="button"
            onClick={() => navigate("/")}
            style={{
              padding: "12px 16px",
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: "10px",
              background: pinkTheme.cardBg,
              color: pinkTheme.textMuted,
              cursor: "pointer",
            }}
          >
            취소
          </button>
        </div>
      </div>
    </div>
  );
}
