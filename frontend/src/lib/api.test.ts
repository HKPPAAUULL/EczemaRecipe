import { describe, expect, it } from "vitest";
import { ApiError, isIngredientDetail, isIngredientListItem } from "@/lib/api";

describe("API type guards", () => {
  const listItem = {
    id: 1,
    name_zh: "雞蛋",
    name_en: "egg",
    category: { id: 1, name_zh: "蛋奶" },
    eczema_rating: "caution",
    rating_label: "因人而異",
    allergens: ["蛋"],
    draft: true,
  };

  it("accepts a well-formed list item", () => {
    expect(isIngredientListItem(listItem)).toBe(true);
  });

  it("rejects malformed list items", () => {
    expect(isIngredientListItem(null)).toBe(false);
    expect(isIngredientListItem({ ...listItem, id: "1" })).toBe(false);
    expect(isIngredientListItem({ ...listItem, allergens: "蛋" })).toBe(false);
    expect(isIngredientListItem({ ...listItem, name_zh: 5 })).toBe(false);
  });

  it("accepts a well-formed detail", () => {
    expect(
      isIngredientDetail({
        ...listItem,
        aliases: ["蛋"],
        rating_reason: "r",
        evidence: [],
        nutrients: [],
        needs_senior_review: true,
        disclaimer: "本站資訊僅供參考，不能取代醫生或營養師意見。",
        updated_at: null,
      })
    ).toBe(true);
  });

  it("rejects details missing required arrays", () => {
    expect(isIngredientDetail({ ...listItem })).toBe(false);
    expect(
      isIngredientDetail({
        ...listItem,
        aliases: [],
        evidence: [],
        nutrients: "x",
        disclaimer: "d",
      })
    ).toBe(false);
  });
});

describe("ApiError", () => {
  it("carries an optional HTTP status", () => {
    const err = new ApiError("伺服器回應錯誤（503）", 503);
    expect(err.status).toBe(503);
    expect(err).toBeInstanceOf(Error);
    expect(new ApiError("無法連線").status).toBeUndefined();
  });
});
