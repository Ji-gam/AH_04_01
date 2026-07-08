import { Link } from "react-router-dom";

export default function MorePage() {
  return (
    <div style={{ padding: "20px" }}>
      <h1>더보기</h1>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "15px" }}>
        <Link
          to="/medication"
          style={{
            border: "1px solid #ccc",
            borderRadius: "8px",
            padding: "14px 16px",
            textDecoration: "none",
            color: "inherit",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>
            💊 복약 스케줄
            <span style={{ display: "block", fontSize: "12px", color: "#888", marginTop: "2px" }}>
              등록된 약과 복용 시간을 한눈에 관리해요
            </span>
          </span>
          <span aria-hidden>›</span>
        </Link>
      </div>
    </div>
  );
}
