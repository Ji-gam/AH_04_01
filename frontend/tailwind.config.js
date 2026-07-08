/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  // Preflight(전역 CSS 리셋)은 끈다 — 이 리셋이 border-width 등 브라우저 기본값을 전체 화면에
  // 적용해버려서, 아직 Tailwind로 마이그레이션 안 된 기존 화면(로그인 등)의 테두리가 사라지는
  // 문제가 있었다. FRONTEND_UI_GUIDE_v1.0.md의 "화면 하나씩 마이그레이션" 방침과도 맞다 —
  // Tailwind 유틸리티 클래스(각 화면에서 명시적으로 쓰는 border/rounded 등)는 preflight 없이도
  // 정상 동작한다.
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
