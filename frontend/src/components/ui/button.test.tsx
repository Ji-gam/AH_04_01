import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("renders its label", () => {
    render(<Button>클릭</Button>);
    expect(screen.getByRole("button", { name: "클릭" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>클릭</Button>);

    await userEvent.click(screen.getByRole("button", { name: "클릭" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClick when disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        클릭
      </Button>,
    );

    await userEvent.click(screen.getByRole("button", { name: "클릭" }));

    expect(onClick).not.toHaveBeenCalled();
  });
});
