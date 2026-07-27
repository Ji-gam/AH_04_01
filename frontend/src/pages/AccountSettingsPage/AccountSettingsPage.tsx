import { Settings } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { authApi } from "../../api/authApi";
import PageTitle from "../../components/common/PageTitle";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

const inputStyle: React.CSSProperties = {
  padding: "11px 13px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: 10,
  fontSize: 14,
  outline: "none",
};

/** 로그아웃 버튼 옆 "개인정보수정" 링크로 들어오는 화면.
 * - [변경] 이름(닉네임)만 수정 가능. 이메일은 로그인 식별자라 고정, PATCH /users/me가 애초에 안 받음.
 *   전화번호는 당장 안 쓰고, 성별은 더보기 > 개인건강정보에서 이미 받으므로 여기서는 뺐다.
 *   생년월일은 더 이상 안 쓴다 - 나이는 더보기 > 개인건강정보에서 관리한다.
 * - 회원탈퇴는 개인정보보호법 기준으로 즉시 완전 삭제라 되돌릴 수 없음 - 비밀번호 재확인 + 확인 문구 입력을 요구한다.
 * - 로그아웃은 더보기 화면 대신 여기(계정관리 > 회원탈퇴 아래)로 옮겼다 - 계정에 관한 동작은
 *   한 곳에 모아두는 게 자연스럽다는 디자인 반영(2026-07-16). */
export default function AccountSettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromMore = (location.state as { from?: string } | null)?.from === "more";

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

  async function handleLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  async function handleWithdraw(e: FormEvent) {
    e.preventDefault();
    setWithdrawError(null);
    setIsWithdrawing(true);
    try {
      await authApi.withdraw(withdrawPassword);
      await logout();
      navigate("/login", { replace: true });
    } catch {
      setWithdrawError("비밀번호가 잘못되었습니다.");
    } finally {
      setIsWithdrawing(false);
    }
  }

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100dvh", padding: "24px 16px" }}>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate(cameFromMore ? "/more" : "/")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 10,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          ← 뒤로가기
        </button>

        <PageTitle icon={Settings} style={{ marginBottom: 16 }}>
          개인정보수정
        </PageTitle>

        <form
          onSubmit={handleSave}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            background: pinkTheme.cardBg,
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: 16,
            padding: 18,
            boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
          }}
        >
          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              fontSize: 13,
              color: pinkTheme.textMuted,
            }}
          >
            이메일 (변경 불가)
            <input
              type="email"
              value={user?.email ?? ""}
              disabled
              style={{ ...inputStyle, background: pinkTheme.pageBg, color: pinkTheme.textMuted }}
            />
          </label>
          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              fontSize: 13,
              color: pinkTheme.textMuted,
            }}
          >
            이름
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              style={inputStyle}
            />
          </label>

          {savedMessage && (
            <p style={{ color: pinkTheme.success, fontSize: 13, margin: 0 }}>{savedMessage}</p>
          )}
          {saveError && (
            <p style={{ color: pinkTheme.danger, fontSize: 13, margin: 0 }}>{saveError}</p>
          )}

          <button
            type="submit"
            disabled={isSaving}
            style={{
              padding: "12px 0",
              border: "none",
              borderRadius: 10,
              background: pinkTheme.primary,
              color: "#fff",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            {isSaving ? "저장 중..." : "저장하기"}
          </button>
        </form>

        <div
          style={{
            marginTop: 20,
            background: pinkTheme.cardBg,
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: 16,
            padding: 18,
            boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
          }}
        >
          {!showWithdrawForm ? (
            <button
              type="button"
              onClick={() => setShowWithdrawForm(true)}
              style={{
                background: "none",
                border: "none",
                color: pinkTheme.danger,
                fontSize: 13,
                cursor: "pointer",
                padding: 0,
              }}
            >
              회원 탈퇴하기
            </button>
          ) : (
            <form
              onSubmit={handleWithdraw}
              style={{ display: "flex", flexDirection: "column", gap: 12 }}
            >
              <p style={{ color: pinkTheme.danger, fontWeight: 700, fontSize: 13, margin: 0 }}>
                탈퇴하시면 계정과 개인정보(건강정보, 복약알림 등 포함)가 즉시 완전히 삭제되며,
                되돌릴 수 없습니다.
              </p>
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  color: pinkTheme.textMuted,
                }}
              >
                현재 비밀번호
                <input
                  type="password"
                  value={withdrawPassword}
                  onChange={(e) => setWithdrawPassword(e.target.value)}
                  required
                  style={inputStyle}
                />
              </label>

              {withdrawError && (
                <p style={{ color: pinkTheme.danger, fontSize: 13, margin: 0 }}>{withdrawError}</p>
              )}

              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="submit"
                  disabled={isWithdrawing}
                  style={{
                    flex: 1,
                    padding: "11px 0",
                    border: "none",
                    borderRadius: 10,
                    background: pinkTheme.danger,
                    color: "#fff",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {isWithdrawing ? "처리 중..." : "정말 탈퇴합니다"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowWithdrawForm(false)}
                  style={{
                    padding: "11px 18px",
                    borderRadius: 10,
                    border: `1px solid ${pinkTheme.border}`,
                    background: pinkTheme.cardBg,
                    color: pinkTheme.textMuted,
                    cursor: "pointer",
                  }}
                >
                  취소
                </button>
              </div>
            </form>
          )}
        </div>

        <button
          type="button"
          onClick={handleLogout}
          style={{
            marginTop: 12,
            width: "100%",
            padding: "12px 0",
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: 10,
            background: pinkTheme.cardBg,
            color: pinkTheme.textMuted,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          로그아웃
        </button>
      </div>
    </div>
  );
}
