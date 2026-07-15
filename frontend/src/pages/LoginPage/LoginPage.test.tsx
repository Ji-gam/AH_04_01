import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import LoginPage, { sanitizeCredential } from "./LoginPage";

// useAuth의 login을 스파이로 교체해서, 실제로 어떤 값이 넘어가는지 검증한다.
const loginMock = vi.fn().mockResolvedValue(undefined);
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({ login: loginMock }),
}));

// authApi.signup도 마찬가지로 스파이 처리.
const signupMock = vi.fn().mockResolvedValue({ detail: "ok" });
vi.mock("../../api/authApi", () => ({
  authApi: { signup: (...args: unknown[]) => signupMock(...args) },
  socialLoginUrl: () => "https://example.com/social",
}));

describe("sanitizeCredential", () => {
  it("트림: 앞뒤 공백/줄바꿈을 제거한다", () => {
    expect(sanitizeCredential("  abcd1234!  ")).toBe("abcd1234!");
    expect(sanitizeCredential("abcd1234!\n")).toBe("abcd1234!");
  });

  it("zero-width 문자(복붙 시 자주 섞이는 문자)를 제거한다", () => {
    // \u200B = zero-width space, 카톡/메모앱에서 복사할 때 흔히 섞여 들어온다.
    expect(sanitizeCredential("abcd1234!\u200B")).toBe("abcd1234!");
    expect(sanitizeCredential("\uFEFFabcd1234!")).toBe("abcd1234!");
  });

  it("실제 버그 시나리오: 타이핑한 값과 복붙(줄바꿈 포함)한 값이 sanitize 후 같아진다", () => {
    const typed = "MyPassw0rd!";
    const pastedFromNotes = "MyPassw0rd!\n"; // 메모앱에서 복사하면 흔히 붙는 trailing newline
    expect(sanitizeCredential(typed)).toBe(sanitizeCredential(pastedFromNotes));
  });

  it("비밀번호 내부의 의도적인 공백은 보존한다 (trim만, 전체 공백 제거가 아님)", () => {
    expect(sanitizeCredential("  my pass word!  ")).toBe("my pass word!");
  });
});

describe("LoginPage - 로그인 폼 제출 시 sanitize 적용", () => {
  it("이메일/비밀번호 앞뒤에 공백이 섞여 있어도 정리된 값으로 login()이 호출된다", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await user.type(screen.getByPlaceholderText("이메일"), "  test3@example.com  ");
    await user.type(screen.getByPlaceholderText("비밀번호"), "abcd1234!\n");
    // "로그인"이라는 텍스트가 탭 버튼에도 있어 이름으로는 모호하므로 submit 버튼을 직접 지정한다.
    const submitButton = container.querySelector('button[type="submit"]') as HTMLButtonElement;
    await user.click(submitButton);

    expect(loginMock).toHaveBeenCalledWith("test3@example.com", "abcd1234!");
  });
});

describe("LoginPage - 가입 폼 제출 시 sanitize 적용", () => {
  it("가입 이메일/비밀번호도 정리된 값으로 signup()과 이어지는 login()이 호출된다", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "가입" }));
    await user.type(screen.getByPlaceholderText("닉네임"), "테스트닉네임\u200B");
    await user.type(screen.getByPlaceholderText("이메일"), "new@example.com");
    await user.type(
      screen.getByPlaceholderText("비밀번호 (소문자·숫자·특수문자 포함 8자 이상)"),
      "  abcd1234!  ",
    );
    await user.click(screen.getByRole("button", { name: "가입하기" }));

    expect(signupMock).toHaveBeenCalledWith({
      name: "테스트닉네임\u200B",
      email: "new@example.com",
      password: "abcd1234!",
    });
    expect(loginMock).toHaveBeenCalledWith("new@example.com", "abcd1234!");
  });
});
