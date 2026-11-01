import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RECENT_KEY } from "@/lib/storage";
import RecentSearches from "./RecentSearches";

describe("RecentSearches", () => {
  afterEach(() => cleanup());

  it("renders nothing with no history", () => {
    const { container } = render(<RecentSearches />);
    expect(container.firstChild).toBeNull();
  });

  it("renders stored queries as search links", () => {
    localStorage.setItem(RECENT_KEY, JSON.stringify(["雞蛋", "牛奶"]));
    render(<RecentSearches />);
    const link = screen.getByRole("link", { name: "雞蛋" });
    expect(link.getAttribute("href")).toBe(
      "/categories?q=" + encodeURIComponent("雞蛋")
    );
  });

  it("clear button empties the history", () => {
    localStorage.setItem(RECENT_KEY, JSON.stringify(["雞蛋"]));
    render(<RecentSearches />);
    fireEvent.click(screen.getByRole("button", { name: "清除" }));
    expect(JSON.parse(localStorage.getItem(RECENT_KEY)!)).toEqual([]);
  });
});
