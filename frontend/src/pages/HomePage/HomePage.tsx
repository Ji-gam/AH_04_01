import { useAuth } from "../../hooks/useAuth";

export default function HomePage() {
  const { user } = useAuth();

  return (
    <div>
      <h1>홈</h1>
      {/* /users/me가 실제로 붙는지 증명하는 최소 출력 — profile_id까지 보이면 User/Profile 분리도 같이 확인됨 */}
      {user && (
        <p>
          안녕하세요, {user.name}님 ({user.email}) — profile_id: {user.profile_id}
        </p>
      )}
    </div>
  );
}
