import { Link } from "react-router-dom";

export default function MorePage() {
  return (
    <div>
      <h1>더보기</h1>
      <Link to="/health-info">개인건강정보</Link>
    </div>
  );
}
