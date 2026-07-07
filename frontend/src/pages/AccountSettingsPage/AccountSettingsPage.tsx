import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { accountApi, userApi } from "../../api/userApi";
import { useAuth } from "../../hooks/useAuth";

/** 계정 설정 화면: 회원정보 수정 + 회원탈퇴를 한 화면에서 처리한다.
 * 소셜 가입자는 비밀번호가 없으므로 탈퇴 시 비밀번호 입력칸 자체를 감춘다. */
export default function AccountSettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // --- 회원정보 수정 ---
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [phoneNumber, setPhoneNumber] = useState(user?.phone_number ?? "");
  const [birthday, setBirthday] = useState(user?.birthday ?? "");
  const [gender, setGender] = useState<"MALE" | "FEMALE">(user?.gender ?? "MALE");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // --- 회원탈퇴 ---
  const [showWithdrawConfirm, setShowWithdrawConfirm] = useState(false);
  const [withdrawPassword, setWithdrawPassword] = useState("");
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [isWithdrawing, setIsWithdrawing] = useState(false);

  // 소셜 가입 여부는 서버가 따로 안 내려주고 있어서, 지금은 "비밀번호 입력칸을 항상 보여주되
  // 소셜 가입자는 빈 값으로 제출해도 서버가 알아서 통과시켜준다" 방식으로 간단히 처리한다.
  // (필요하면 나중에 UserInfoResult에 sns_provider를 추가해서 조건부로 아예 숨길 수 있다.)

  async function handleSaveProfile(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaveMessage(null);
    setIsSaving(true);
    try {
      await userApi.updateProfile({ name, email, phone_number: phoneNumber, birthday, gender });
      setSaveMessage("저장되었습니다.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleWithdraw() {
    setWithdrawError(null);
    setIsWithdrawing(true);
    try {
      await accountApi.withdraw(withdrawPassword ? { password: withdrawPassword } : {});
      logout();
      navigate("/start", { replace: true });
    } catch (err) {
      setWithdrawError(err instanceof Error ? err.message : "탈퇴 처리 중 오류가 발생했습니다.");
    } finally {
      setIsWithdrawing(false);
    }
  }

  return (
    <div style={{ maxWidth: 320, margin: "40px auto" }}>
      <h1>계정 설정</h1>

      <h2 style={{ fontSize: 16, marginTop: 24 }}>회원정보 수정</h2>
      <form onSubmit={handleSaveProfile} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <input type="text" placeholder="이름" value={name} onChange={(e) => setName(e.target.value)} />
        <input type="email" placeholder="이메일" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input
          type="tel"
          placeholder="휴대폰번호"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
        />
        <input type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)} />
        <select value={gender} onChange={(e) => setGender(e.target.value as "MALE" | "FEMALE")}>
          <option value="MALE">남성</option>
          <option value="FEMALE">여성</option>
        </select>
        {saveError && <p style={{ color: "red" }}>{saveError}</p>}
        {saveMessage && <p style={{ color: "green" }}>{saveMessage}</p>}
        <button type="submit" disabled={isSaving}>
          {isSaving ? "저장 중..." : "저장하기"}
        </button>
      </form>

      <hr style={{ margin: "32px 0" }} />

      <h2 style={{ fontSize: 16, color: "#c0392b" }}>회원 탈퇴</h2>
      {!showWithdrawConfirm ? (
        <button
          type="button"
          onClick={() => setShowWithdrawConfirm(true)}
          style={{ color: "#c0392b", background: "none", border: "1px solid #c0392b", padding: "8px", width: "100%" }}
        >
          회원 탈퇴하기
        </button>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <p style={{ fontSize: 13, color: "#888" }}>
            탈퇴 시 모든 정보가 즉시 삭제되며 복구할 수 없습니다. 이메일로 가입하셨다면 비밀번호를 입력해주세요
            (소셜 로그인 가입자는 비워두셔도 됩니다).
          </p>
          <input
            type="password"
            placeholder="비밀번호 (소셜 가입자는 비워두세요)"
            value={withdrawPassword}
            onChange={(e) => setWithdrawPassword(e.target.value)}
          />
          {withdrawError && <p style={{ color: "red" }}>{withdrawError}</p>}
          <button
            type="button"
            onClick={handleWithdraw}
            disabled={isWithdrawing}
            style={{ background: "#c0392b", color: "#fff", padding: "8px", border: "none" }}
          >
            {isWithdrawing ? "처리 중..." : "정말 탈퇴합니다"}
          </button>
          <button type="button" onClick={() => setShowWithdrawConfirm(false)}>
            취소
          </button>
        </div>
      )}
    </div>
  );
}
