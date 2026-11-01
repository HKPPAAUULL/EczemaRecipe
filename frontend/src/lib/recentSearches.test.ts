import { describe, expect, it } from "vitest";
import {
  MAX_RECENT,
  normalizeRecent,
  recordRecent,
} from "./recentSearches";

describe("normalizeRecent", () => {
  it("returns [] for non-arrays", () => {
    expect(normalizeRecent(null)).toEqual([]);
    expect(normalizeRecent("x")).toEqual([]);
  });

  it("trims, drops blanks and non-strings, dedupes, caps", () => {
    expect(
      normalizeRecent([" 蛋 ", "", "蛋", 1, "奶", null, "菜"])
    ).toEqual(["蛋", "奶", "菜"]);
    expect(normalizeRecent(Array(20).fill("x").map((_, i) => `q${i}`))).toHaveLength(
      MAX_RECENT
    );
  });
});

describe("recordRecent", () => {
  it("prepends and dedupes", () => {
    expect(recordRecent(["奶", "蛋"], "蛋")).toEqual(["蛋", "奶"]);
    expect(recordRecent([], " 牛肉 ")).toEqual(["牛肉"]);
  });

  it("ignores empty queries", () => {
    expect(recordRecent(["奶"], "  ")).toEqual(["奶"]);
  });
});
