// src/types/auth.ts
// [starter] 공유 구역(types/)입니다. 다른 도메인 타입은 이 폴더에 파일을 나눠서 추가하면 됩니다.

export type Gender = "MALE" | "FEMALE";

export interface SignupRequest {
  email: string;
  password: string;
  name: string;
  gender: Gender;
  birth_date: string; // YYYY-MM-DD
  phone_number: string; // 010-1234-5678 형식
  agreed_terms: boolean; // 백엔드가 false/누락 시 422로 거부합니다
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
}

export interface CurrentUser {
  id: number;
  email: string;
  name: string;
}

export type SocialProvider = "google" | "naver" | "kakao";
