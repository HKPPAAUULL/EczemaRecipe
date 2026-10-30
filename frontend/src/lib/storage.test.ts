import { beforeEach, describe, expect, it } from "vitest";
import {
  ALLERGEN_KEY,
  readAllergenExclusions,
  readJson,
  storageAvailable,
  writeJson,
} from "./storage";

describe("storage", () => {
  beforeEach(() => window.localStorage.clear());

  it("round-trips and tolerates corrupt data", () => {
    expect(writeJson("k", { a: 1 })).toBe(true);
    expect(readJson("k", {})).toEqual({ a: 1 });
    window.localStorage.setItem("bad", "{not json");
    expect(readJson("bad", "fb")).toBe("fb");
    expect(readJson("missing", 42)).toBe(42);
  });

  it("uses versioned keys and filters stale/invalid ids", () => {
    expect(ALLERGEN_KEY).toMatch(/^ek:v1:/);
    window.localStorage.setItem(
      ALLERGEN_KEY,
      JSON.stringify([1, "x", -2, 3.5, 7])
    );
    expect(readAllergenExclusions()).toEqual([1, 7]);
    window.localStorage.setItem(ALLERGEN_KEY, "{corrupt");
    expect(readAllergenExclusions()).toEqual([]);
  });

  it("detects availability", () => {
    expect(storageAvailable()).toBe(true);
  });
});
