import { Link } from "react-router-dom";

const BACKEND_BASE_URL = "http://localhost:8000";

const socialButtonStyle = {
  textAlign: "center" as const,
  padding: "8px",
  border: "1px solid #ccc",
  textDecoration: "none",
  color: "#000",
  display: "block",
};

/** 회원가입 진입 화면. 소셜 3사 아이콘 + "이메일로 가입하기" 중 고르게 한다.
 * (참고 앱: SNS 아이콘 나열 + "또는" + "이메일로 가입하기" 구조와 동일) */
export default function SignupPage() {
  return (
    <div style={{ maxWidth: 320, margin: "80px auto" }}>
      <h1 style={{ textAlign: "center" }}>회원가입</h1>
      <p style={{ textAlign: "center", color: "#888", fontSize: 14 }}>간편하게 SNS로 가입하세요.</p>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px", margin: "16px 0" }}>
        {/* [T-AUTH-7] axios/fetch 호출이 아니라 진짜 페이지 이동이어야 한다(OAuth 리다이렉트) */}
        <a href={`${BACKEND_BASE_URL}/api/v1/auth/google/login`} style={socialButtonStyle}>
          구글로 가입하기
        </a>
        <a href={`${BACKEND_BASE_URL}/api/v1/auth/naver/login`} style={socialButtonStyle}>
          네이버로 가입하기
        </a>
        <a href={`${BACKEND_BASE_URL}/api/v1/auth/kakao/login`} style={socialButtonStyle}>
          카카오로 가입하기
        </a>
      </div>

      <p style={{ textAlign: "center", color: "#888", margin: "16px 0 8px" }}>또는</p>
      <Link
        to="/signup/email"
        style={{
          display: "block",
          textAlign: "center",
          padding: "8px",
          border: "1px solid #ccc",
          borderRadius: "4px",
          textDecoration: "none",
          color: "#000",
        }}
      >
        이메일로 가입하기
      </Link>

      <p style={{ textAlign: "center", marginTop: 16 }}>
        이미 계정이 있으신가요? <Link to="/login">로그인</Link>
      </p>
    </div>
  );
}