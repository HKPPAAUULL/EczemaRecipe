/**
 * Types for the suggest/detail API (mirrors backend schemas) + pure
 * display helpers — unit tested.
 */

import type { IngredientAllergen } from "./api";

export interface SelectedIngredientItem {
  id: number;
  name_zh: string;
  eczema_rating: string;
  rating_label: string;
  allergens: IngredientAllergen[];
}

export interface SelectionWarning {
  ingredient_id: number;
  name_zh: string;
  eczema_rating: string;
  reasons: string[];
  allergens: { id: number; name_zh: string }[];
}

export interface RecipeSuggestion {
  id: number;
  title: string;
  description: string | null;
  cook_time: number | null;
  servings: number | null;
  source_url: string | null;
  source_name: string | null;
  license: string | null;
  tags: string[];
  coverage: number;
  matched: { ingredient_id: number; name_zh: string }[];
  missing: string[];
  allergens: string[];
  allergen_warning: boolean;
  trigger_ingredients: string[];
  unmatched_ingredients: string[];
  unknown_allergen_hints: string[] | null;
  rank_score: number;
  draft: boolean;
}

export interface SuggestResponse {
  selected: SelectedIngredientItem[];
  warnings: SelectionWarning[];
  excluded_by_allergen_count: number;
  total: number;
  limit: number;
  offset: number;
  recipes: RecipeSuggestion[];
  disclaimer: string;
}

export interface RecipeIngredientItem {
  ingredient_id: number;
  name_zh: string;
  eczema_rating: string;
  rating_label: string;
  raw_text: string;
  qty: number | null;
  unit: string | null;
  is_staple: boolean;
  allergens: IngredientAllergen[];
}

export interface RecipeDetail {
  id: number;
  title: string;
  description: string | null;
  cook_time: number | null;
  servings: number | null;
  source_url: string | null;
  source_name: string | null;
  license: string | null;
  tags: string[];
  ingredients: RecipeIngredientItem[];
  unmatched_ingredients: string[];
  unmatched_staples: string[];
  allergens: string[];
  allergen_warning: boolean;
  draft: boolean;
  disclaimer: string;
}

export function coverageText(r: RecipeSuggestion): string {
  return `已有 ${r.matched.length}/${r.matched.length + r.missing.length} 項食材`;
}

export function exclusionNotice(
  allergenNames: string[],
  excluded: number
): string {
  const names = allergenNames.join("、");
  return excluded > 0
    ? `已按你的忌口（${names}）排除 ${excluded} 道食譜`
    : `已啟用忌口（${names}），本次結果沒有因忌口被排除的食譜`;
}

export function emptyResultText(
  hasExclusions: boolean,
  excluded: number
): string {
  if (excluded > 0) {
    return `沒有符合的食譜——${excluded} 道已因你的忌口被排除。可試着加入其他食材，或調整忌口設定。`;
  }
  return hasExclusions
    ? "沒有符合的食譜（忌口已啟用但未有食譜因此被排除）。試着加入其他食材。"
    : "沒有符合的食譜，試着加入其他食材。";
}

export function invalidIngredientIds(detail: unknown): number[] {
  if (
    typeof detail === "object" &&
    detail !== null &&
    Array.isArray((detail as { invalid_ingredient_ids?: unknown }).invalid_ingredient_ids)
  ) {
    return (
      detail as { invalid_ingredient_ids: unknown[] }
    ).invalid_ingredient_ids.filter(
      (x): x is number => Number.isInteger(x)
    );
  }
  return [];
}
