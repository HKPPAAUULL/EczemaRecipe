/**
 * Pure validation for the BFF route handlers — unit tested without Next.
 * Never leak backend URLs or stacks to the browser.
 */

export type Validation =
  | { ok: true; value: unknown }
  | { ok: false; status: number; error: string };

export function validateSearchQuery(q: string | null): Validation {
  if (q === null) return { ok: false, status: 400, error: "缺少 q 參數" };
  const t = q.trim();
  if (t.length < 1 || t.length > 50) {
    return { ok: false, status: 400, error: "搜尋字須為 1–50 字" };
  }
  return { ok: true, value: t };
}

const MAX_BODY_BYTES = 8 * 1024;

export interface SuggestBody {
  ingredient_ids: number[];
  exclude_allergens: number[];
  limit: number;
  offset: number;
}

export function validateSuggestBody(raw: unknown): Validation {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return { ok: false, status: 400, error: "body 格式不正確" };
  }
  const b = raw as Record<string, unknown>;
  const ids = b.ingredient_ids;
  if (!Array.isArray(ids) || ids.length < 1 || ids.length > 30) {
    return { ok: false, status: 400, error: "ingredient_ids 須為 1–30 個" };
  }
  if (!ids.every((x) => Number.isInteger(x) && (x as number) > 0)) {
    return { ok: false, status: 400, error: "ingredient_ids 須為正整數" };
  }
  const excl = b.exclude_allergens ?? [];
  if (!Array.isArray(excl) || excl.length > 20) {
    return { ok: false, status: 400, error: "exclude_allergens 最多 20 個" };
  }
  if (!excl.every((x) => Number.isInteger(x) && (x as number) > 0)) {
    return { ok: false, status: 400, error: "exclude_allergens 須為正整數" };
  }
  const limit = b.limit ?? 12;
  const offset = b.offset ?? 0;
  if (!Number.isInteger(limit) || (limit as number) < 1 || (limit as number) > 30) {
    return { ok: false, status: 400, error: "limit 須為 1–30" };
  }
  if (!Number.isInteger(offset) || (offset as number) < 0) {
    return { ok: false, status: 400, error: "offset 須 ≥ 0" };
  }
  const value: SuggestBody = {
    ingredient_ids: ids as number[],
    exclude_allergens: excl as number[],
    limit: limit as number,
    offset: offset as number,
  };
  return { ok: true, value };
}

export const BODY_LIMIT = MAX_BODY_BYTES;
