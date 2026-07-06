// src/features/auth/useAuth.ts
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "../../api/endpoints/auth";
import { useAuthStore } from "../../store/authStore";
import type { LoginRequest, SignupRequest } from "../../types/auth";

export function useLogin() {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const navigate = useNavigate();

  const login = async (data: LoginRequest) => {
    setIsPending(true);
    setError(null);
    try {
      const res = await authApi.login(data);
      setAccessToken(res.access_token);
      try {
        const me = await authApi.getMe();
        setUser(me);
      } catch {
        // /users/me가 아직 없거나 실패해도 로그인 자체는 성공 처리
      }
      navigate("/");
    } catch (err: any) {
      const detail = err?.response?.data?.message ?? err?.response?.data?.detail;
      setError(detail || "이메일 또는 비밀번호가 일치하지 않습니다.");
    } finally {
      setIsPending(false);
    }
  };

  return { login, isPending, error };
}

export function useSignup() {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const navigate = useNavigate();

  const signup = async (data: SignupRequest) => {
    setIsPending(true);
    setError(null);
    try {
      await authApi.signup(data);
      setIsSuccess(true);
      setTimeout(() => navigate("/login"), 1000);
    } catch (err: any) {
      const detail = err?.response?.data?.message ?? err?.response?.data?.detail;
      setError(
        Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join(", ")
          : detail || "가입 중 오류가 발생했습니다. 입력값을 확인해주세요."
      );
    } finally {
      setIsPending(false);
    }
  };

  return { signup, isPending, error, isSuccess };
}
