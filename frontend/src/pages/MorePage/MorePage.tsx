import { Link } from "react-router-dom";

// [임시] 인증(심복규) 담당 링크만 우선 추가함 - 더보기 화면 본작업 시 위치/스타일 자유롭게 옮겨주세요.
// 계정 설정(회원정보 수정+탈퇴)은 헤더(Layout.tsx)의 로그아웃 버튼 옆에 있어요, 여기 안 넣습니다.
export default function MorePage() {
  return (
    <div>
      <h1>더보기</h1>
      <Link to="/health-info">개인건강관리</Link>
    </div>
  );
}
