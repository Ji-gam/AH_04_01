import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import importPlugin from "eslint-plugin-import";
import prettierConfig from "eslint-config-prettier";
import globals from "globals";

// FRONTEND_ARCHITECTURE.md §7: Prettier + ESLint 강제, import 순서 자동 정렬.
export default tseslint.config(
  { ignores: ["dist"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      import: importPlugin,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "import/order": [
        "warn",
        {
          groups: ["builtin", "external", "internal", "parent", "sibling", "index"],
          "newlines-between": "always",
          alphabetize: { order: "asc", caseInsensitive: true },
        },
      ],
    },
  },
  {
    files: ["public/service-worker.js"],
    languageOptions: {
      ecmaVersion: 2020,
      // 서비스워커는 일반 브라우저 스크립트가 아니라 별도 전역 스코프(self가 브라우저의
      // window가 아니라 ServiceWorkerGlobalScope를 가리킴)에서 돈다 - globals 패키지의
      // 전용 프리셋을 써야 self/caches/clients 등을 ESLint가 정의된 전역으로 인식한다.
      globals: globals.serviceworker,
    },
  },
  prettierConfig,
);