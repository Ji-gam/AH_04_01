// src/features/auth/SignupPage.tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useSignup } from "./useAuth";

export default function SignupPage() {
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const signup = useSignup();

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          signup.mutate({ ...form, role_type: "PATIENT" });
        }}
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
      >
        <h1 className="mb-6 text-2xl font-bold">회원가입</h1>

        <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>이름</label>
        <input required value={form.name} onChange={update("name")}
          className="mb-4 w-full rounded-lg border bg-transparent px-3 py-2 outline-none" style={{ borderColor: "var(--panel-border)" }} />

        <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>이메일</label>
        <input type="email" required value={form.email} onChange={update("email")}
          className="mb-4 w-full rounded-lg border bg-transparent px-3 py-2 outline-none" style={{ borderColor: "var(--panel-border)" }} />

        <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>비밀번호</label>
        <input type="password" required value={form.password} onChange={update("password")}
          className="mb-6 w-full rounded-lg border bg-transparent px-3 py-2 outline-none" style={{ borderColor: "var(--panel-border)" }} />

        {signup.isError && (
          <p className="mb-4 text-sm" style={{ color: "var(--accent-pink)" }}>이미 가입된 이메일이거나 입력값을 확인해주세요.</p>
        )}
        {signup.isSuccess && (
          <p className="mb-4 text-sm" style={{ color: "var(--accent-green)" }}>가입 완료! 로그인 페이지로 이동합니다.</p>
        )}

        <button type="submit" disabled={signup.isPending}
          className="w-full rounded-lg py-2 font-semibold text-black" style={{ background: "var(--accent-cyan)" }}>
          {signup.isPending ? "가입 중..." : "회원가입"}
        </button>

        <p className="mt-4 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          이미 계정이 있으신가요? <Link to="/login" className="underline">로그인</Link>
        </p>

        {/* TODO(조원 구현): role_type(PATIENT/GUARDIAN) 선택 UI, gender/birth_date 입력 필드 추가 */}
      </form>
    </div>
  );
}
