import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../../api/authApi";
import { useAuth } from "../../hooks/useAuth";

/** 로그아웃 버튼 옆 "개인정보수정" 링크로 들어오는 화면.
 * - [변경] 이름(닉네임)만 수정 가능. 이메일은 로그인 식별자라 고정, PATCH /users/me가 애초에 안 받음.
 *   전화번호는 당장 안 쓰고, 성별은 더보기 > 개인건강정보에서 이미 받으므로 여기서는 뺐다.
 *   생년월일은 더 이상 안 쓴다 - 나이는 더보기 > 개인건강정보에서 관리한다.
 * - 회원탈퇴는 개인정보보호법 기준으로 즉시 완전 삭제라 되돌릴 수 없음 - 비밀번호 재확인 + 확인 문구 입력을 요구한다. */
export default function AccountSettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState(user?.name ?? "");

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const [showWithdrawForm, setShowWithdrawForm] = useState(false);
  const [withdrawPassword, setWithdrawPassword] = useState("");
  const [isWithdrawing, setIsWithdrawing] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSavedMessage(null);
    setIsSaving(true);
    try {
      await authApi.updateMe({ name });
      setSavedMessage("저장되었습니다.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleWithdraw(e: FormEvent) {
    e.preventDefault();
    setWithdrawError(null);
    setIsWithdrawing(true);
    try {
      await authApi.withdraw(withdrawPassword);
      logout();
      navigate("/login", { replace: true });
    } catch {
      setWithdrawError("비밀번호가 잘못되었습니다.");
    } finally {
      setIsWithdrawing(false);
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: "40px auto" }}>
      <button
        type="button"
        onClick={() => navigate("/")}
        style={{
          background: "none",
          border: "none",
          color: "#555",
          padding: 0,
          marginBottom: 8,
          cursor: "pointer",
        }}
      >
        ← 뒤로가기
      </button>

      <h1>개인정보수정</h1>

      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          이메일 (변경 불가)
          <input type="email" value={user?.email ?? ""} disabled />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          이름
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>

        {savedMessage && <p style={{ color: "green" }}>{savedMessage}</p>}
        {saveError && <p style={{ color: "red" }}>{saveError}</p>}

        <button type="submit" disabled={isSaving}>
          {isSaving ? "저장 중..." : "저장하기"}
        </button>
      </form>

      <hr style={{ margin: "32px 0" }} />

      {!showWithdrawForm ? (
        <button type="button" onClick={() => setShowWithdrawForm(true)} style={{ color: "red" }}>
          회원 탈퇴하기
        </button>
      ) : (
        <form
          onSubmit={handleWithdraw}
          style={{ display: "flex", flexDirection: "column", gap: "8px" }}
        >
          <p style={{ color: "red", fontWeight: "bold" }}>
            탈퇴하시면 계정과 개인정보(건강정보, 복약알림 등 포함)가 즉시 완전히 삭제되며, 되돌릴 수
            없습니다.
          </p>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            현재 비밀번호
            <input
              type="password"
              value={withdrawPassword}
              onChange={(e) => setWithdrawPassword(e.target.value)}
              required
            />
          </label>

          {withdrawError && <p style={{ color: "red" }}>{withdrawError}</p>}

          <div style={{ display: "flex", gap: "8px" }}>
            <button type="submit" disabled={isWithdrawing} style={{ color: "red" }}>
              {isWithdrawing ? "처리 중..." : "정말 탈퇴합니다"}
            </button>
            <button type="button" onClick={() => setShowWithdrawForm(false)}>
              취소
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
