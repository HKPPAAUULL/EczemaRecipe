import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import InsufficientDataNotice from "@/components/InsufficientDataNotice";

describe("InsufficientDataNotice", () => {
  it("renders the 資料不足 card with the fixed text", () => {
    render(<InsufficientDataNotice />);
    expect(screen.getByText("資料不足")).toBeTruthy();
    expect(
      screen.getByText(/目前尚無足夠可靠資料為此食材評級，本站不作推測/)
    ).toBeTruthy();
  });
});
