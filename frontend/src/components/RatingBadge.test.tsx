import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RatingBadge from "@/components/RatingBadge";

describe("RatingBadge", () => {
  it("renders label + icon + colour for each rating (triple expression)", () => {
    const cases: [string, string, string][] = [
      ["suitable", "一般適合", "text-suitable"],
      ["caution", "因人而異", "text-caution"],
      ["trigger", "常見誘發", "text-trigger"],
      ["unrated", "資料不足", "text-ink-muted"],
    ];
    for (const [rating, label, cls] of cases) {
      const { container, unmount } = render(<RatingBadge rating={rating} />);
      const badge = screen.getByText(label);
      expect(badge).toBeTruthy();
      expect(badge.className).toContain(cls);
      // icon present (svg) and colour is not the only signal — text exists
      expect(container.querySelector("svg")).toBeTruthy();
      unmount();
    }
  });

  it("never renders a Level number", () => {
    const { container } = render(<RatingBadge rating="suitable" />);
    expect(container.textContent).not.toMatch(/level/i);
  });
});
