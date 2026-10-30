/**
 * API client for the FastAPI backend. Server-side only — API_BASE_URL is not
 * exposed to the browser (server components fetch directly).
 */

const API_BASE = (
  process.env.API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---- response types (mirrors backend/app/schemas.py) ----

export type Rating = "suitable" | "caution" | "trigger" | "unrated";

export interface CategoryRef {
  id: number;
  name_zh: string;
}

export interface IngredientListItem {
  id: number;
  name_zh: string;
  name_en: string | null;
  category: CategoryRef | null;
  eczema_rating: Rating;
  rating_label: string;
  allergens: string[];
  draft: boolean;
}

export interface SearchResponse {
  query: string;
  count: number;
  items: IngredientListItem[];
}

export interface IngredientAllergen {
  id: number;
  name_zh: string;
  type: string;
  severity: string | null;
}

export interface EvidenceItem {
  title: string;
  url: string | null;
  source_type: string;
  year: number | null;
}

export interface NutrientItem {
  name: string;
  unit: string;
  amount_per_100g: number;
  source: string | null;
}

export interface IngredientDetail {
  id: number;
  name_zh: string;
  name_en: string | null;
  aliases: string[];
  category: CategoryRef | null;
  eczema_rating: Rating;
  rating_label: string;
  rating_reason: string | null;
  allergens: IngredientAllergen[];
  evidence: EvidenceItem[];
  nutrients: NutrientItem[];
  needs_senior_review: boolean | null;
  draft: boolean;
  disclaimer: string;
  updated_at: string | null;
}

export interface CategoryItem {
  id: number;
  name_zh: string;
  sort_order: number;
  ingredient_count: number;
}

export interface CategoryIngredientsResponse {
  category: CategoryRef;
  total: number;
  limit: number;
  offset: number;
  items: IngredientListItem[];
}

export interface AllergenItem {
  id: number;
  name_zh: string;
  name_en: string | null;
  type: string;
}

// ---- fetch helpers ----

async function apiGet<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  } catch {
    throw new ApiError("無法連線至資料伺服器");
  }
  if (!res.ok) {
    throw new ApiError(`伺服器回應錯誤（${res.status}）`, res.status);
  }
  return (await res.json()) as T;
}

export function isIngredientListItem(v: unknown): v is IngredientListItem {
  const o = v as IngredientListItem;
  return (
    typeof o === "object" &&
    o !== null &&
    typeof o.id === "number" &&
    typeof o.name_zh === "string" &&
    typeof o.eczema_rating === "string" &&
    Array.isArray(o.allergens)
  );
}

export function isIngredientDetail(v: unknown): v is IngredientDetail {
  const o = v as IngredientDetail;
  return (
    isIngredientListItem(o) &&
    Array.isArray(o.aliases) &&
    Array.isArray(o.nutrients) &&
    Array.isArray(o.evidence) &&
    typeof o.disclaimer === "string"
  );
}

export function searchIngredients(q: string, limit = 20) {
  return apiGet<SearchResponse>(
    `/api/ingredients/search?q=${encodeURIComponent(q)}&limit=${limit}`
  );
}

export async function getIngredient(id: number): Promise<IngredientDetail | null> {
  try {
    const data = await apiGet<unknown>(`/api/ingredients/${id}`);
    if (!isIngredientDetail(data)) {
      throw new ApiError("伺服器回應格式不正確");
    }
    return data;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function getCategories() {
  return apiGet<CategoryItem[]>("/api/categories");
}

export function getCategoryIngredients(
  id: number,
  opts: { rating?: string; limit?: number; offset?: number } = {}
) {
  const params = new URLSearchParams();
  if (opts.rating) params.set("rating", opts.rating);
  params.set("limit", String(opts.limit ?? 20));
  params.set("offset", String(opts.offset ?? 0));
  return apiGet<CategoryIngredientsResponse>(
    `/api/categories/${id}/ingredients?${params}`
  );
}

export function getAllergens() {
  return apiGet<AllergenItem[]>("/api/allergens");
}

export async function getRecipe(id: number): Promise<import("./recipes").RecipeDetail | null> {
  try {
    const data = await apiGet<import("./recipes").RecipeDetail>(
      `/api/recipes/${id}`
    );
    return data;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
