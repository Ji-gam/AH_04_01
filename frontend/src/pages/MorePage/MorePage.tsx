import { Link } from "react-router-dom";

export default function MorePage() {
  return (
    <div style={{ padding: "20px" }}>
      <h1>더보기</h1>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "15px" }}>
        <Link
          to="/schedule"
          style={{
            background: "#FFF8FA",
            border: "1px solid #FFE3EB",
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
            ⏰ 복약 시간표
            <span style={{ display: "block", fontSize: "12px", color: "#888", marginTop: "2px" }}>
              오늘 먹을 약을 시간순으로 확인하고 복용 체크해요
            </span>
          </span>
          <span aria-hidden>›</span>
        </Link>
      </div>
    </div>
  );
}
