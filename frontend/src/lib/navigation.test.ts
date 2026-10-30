import { describe, expect, it } from "vitest";
import { buildSearchHref, pageWindow } from "@/lib/navigation";

describe("buildSearchHref", () => {
  it("builds an encoded ingredients query URL", () => {
    expect(buildSearchHref("雞蛋")).toBe(
      `/ingredients?q=${encodeURIComponent("雞蛋")}`
    );
    expect(buildSearchHref("牛奶")).toContain("/ingredients?q=");
    // CJK must be percent-encoded, not raw
    expect(buildSearchHref("雞蛋")).not.toContain("雞蛋");
  });

  it("trims whitespace and encodes reserved characters", () => {
    expect(buildSearchHref("  a&b ")).toBe("/ingredients?q=a%26b");
  });
});

describe("pageWindow", () => {
  it("computes pages and prev/next offsets", () => {
    const w = pageWindow(45, 20, 0);
    expect(w).toMatchObject({
      page: 1,
      pages: 3,
      hasPrev: false,
      hasNext: true,
      prevOffset: null,
      nextOffset: 20,
    });
    const w2 = pageWindow(45, 20, 20);
    expect(w2).toMatchObject({
      page: 2,
      hasPrev: true,
      hasNext: true,
      prevOffset: 0,
      nextOffset: 40,
    });
    const w3 = pageWindow(45, 20, 40);
    expect(w3).toMatchObject({
      page: 3,
      hasPrev: true,
      hasNext: false,
      prevOffset: 20,
      nextOffset: null,
    });
  });

  it("handles a single page and zero results", () => {
    const w = pageWindow(5, 20, 0);
    expect(w.pages).toBe(1);
    expect(w.hasNext).toBe(false);
    expect(pageWindow(0, 20, 0).pages).toBe(1);
  });
});
