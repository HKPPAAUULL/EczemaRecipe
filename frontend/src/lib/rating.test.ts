import { describe, expect, it } from "vitest";
import { RATING_META, ratingMeta } from "@/lib/rating";

describe("ratingMeta", () => {
  it("maps each rating to a distinct label, icon and colours", () => {
    const seen = new Set<string>();
    for (const r of ["suitable", "caution", "trigger", "unrated"] as const) {
      const meta = ratingMeta(r);
      expect(meta.label).toBeTruthy();
      expect(meta.bg).toBeTruthy();
      expect(meta.icon).toBeTruthy();
      seen.add(meta.label);
    }
    expect(seen.size).toBe(4);
    expect(ratingMeta("suitable").label).toBe("一般適合");
    expect(ratingMeta("caution").label).toBe("因人而異");
    expect(ratingMeta("trigger").label).toBe("常見誘發");
    expect(ratingMeta("unrated").label).toBe("資料不足");
  });

  it("falls back to unrated for unknown/empty ratings", () => {
    expect(ratingMeta("bogus")).toBe(RATING_META.unrated);
    expect(ratingMeta(null)).toBe(RATING_META.unrated);
    expect(ratingMeta(undefined)).toBe(RATING_META.unrated);
    expect(ratingMeta("")).toBe(RATING_META.unrated);
  });
});
