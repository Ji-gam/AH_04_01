// src/features/auth/useAuth.ts
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authApi } from "../../api/endpoints/auth";
import { useAuthStore } from "../../store/authStore";
import type { SignupRequest } from "../../types";

export function useLogin() {
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const navigate = useNavigate();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) => authApi.login(email, password),
    onSuccess: async (data) => {
      setAccessToken(data.access_token);
      const me = await authApi.getMe();
      setUser(me);
      navigate("/");
    },
  });
}

export function useSignup() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (data: SignupRequest) => authApi.signup(data),
    onSuccess: () => navigate("/login"),
  });
}
