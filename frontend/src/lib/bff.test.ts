import { describe, expect, it } from "vitest";
import {
  invalidIngredientIds,
  emptyResultText,
  exclusionNotice,
  coverageText,
} from "./recipes";
import { validateSearchQuery, validateSuggestBody } from "./bff";

describe("bff validation", () => {
  it("search query bounds", () => {
    expect(validateSearchQuery("雞").ok).toBe(true);
    expect(validateSearchQuery(null).ok).toBe(false);
    expect(validateSearchQuery("".padEnd(51, "a")).ok).toBe(false);
  });

  it("suggest body: bad shapes rejected", () => {
    expect(validateSuggestBody(null).ok).toBe(false);
    expect(validateSuggestBody("x").ok).toBe(false);
    expect(validateSuggestBody({ ingredient_ids: [] }).ok).toBe(false);
    expect(
      validateSuggestBody({ ingredient_ids: Array(31).fill(1) }).ok
    ).toBe(false);
    expect(
      validateSuggestBody({ ingredient_ids: [1.5, -2, "3"] }).ok
    ).toBe(false);
    expect(
      validateSuggestBody({
        ingredient_ids: [1],
        exclude_allergens: Array(21).fill(1),
      }).ok
    ).toBe(false);
    expect(
      validateSuggestBody({ ingredient_ids: [1], limit: 0 }).ok
    ).toBe(false);
    expect(
      validateSuggestBody({ ingredient_ids: [1], offset: -1 }).ok
    ).toBe(false);
  });

  it("suggest body: valid payload normalized", () => {
    const v = validateSuggestBody({ ingredient_ids: [1, 2] });
    expect(v.ok).toBe(true);
    expect(v.ok && (v.value as { limit: number }).limit).toBe(12);
  });
});

describe("suggest response helpers", () => {
  it("invalid ingredient ids extraction", () => {
    expect(
      invalidIngredientIds({ invalid_ingredient_ids: [3, "x", 5] })
    ).toEqual([3, 5]);
    expect(invalidIngredientIds("nope")).toEqual([]);
    expect(invalidIngredientIds(null)).toEqual([]);
  });

  it("exclusion notice and empty result text", () => {
    expect(exclusionNotice(["蛋"], 3)).toContain("排除 3 道");
    expect(exclusionNotice(["蛋"], 0)).toContain("沒有因忌口被排除");
    expect(emptyResultText(true, 4)).toContain("忌口");
    expect(emptyResultText(false, 0)).toContain("加入其他食材");
  });

  it("coverage text uses api counts", () => {
    const r = {
      matched: [{ ingredient_id: 1, name_zh: "a" }],
      missing: ["b", "c"],
    } as never;
    expect(coverageText(r)).toBe("已有 1/3 項食材");
  });
});
