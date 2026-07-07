import { Link } from "react-router-dom";

/** 비로그인 상태의 진입 화면. "로그인"/"회원가입" 두 선택지만 보여준다.
 * (참고 앱의 스플래시 화면과 동일한 구조 - 첫 화면엔 폼을 바로 안 보여주고 선택만 시킨다.) */
export default function StartPage() {
  return (
    <div style={{ maxWidth: 320, margin: "120px auto", textAlign: "center" }}>
      <h1 style={{ marginBottom: 48 }}>ReMedi</h1>
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <Link
          to="/signup"
          style={{
            padding: "12px",
            borderRadius: "8px",
            background: "#ff6b35",
            color: "#fff",
            textDecoration: "none",
            fontWeight: "bold",
          }}
        >
          회원가입
        </Link>
        <Link
          to="/login"
          style={{
            padding: "12px",
            borderRadius: "8px",
            border: "1px solid #ff6b35",
            color: "#ff6b35",
            textDecoration: "none",
            fontWeight: "bold",
          }}
        >
          로그인
        </Link>
      </div>
    </div>
  );
}
