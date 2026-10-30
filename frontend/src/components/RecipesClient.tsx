"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import RecipeCard from "@/components/RecipeCard";
import WarningBanner from "@/components/WarningBanner";
import type { IngredientListItem } from "@/lib/api";
import {
  emptyResultText,
  exclusionNotice,
  invalidIngredientIds,
  type SuggestResponse,
} from "@/lib/recipes";
import {
  ALLERGEN_KEY,
  storageAvailable,
  useLocalStorage,
} from "@/lib/storage";

const SEL_KEY = "ek:v1:recipe-selection";

interface Chip {
  id: number;
  name_zh: string;
}

export default function RecipesClient({
  allergenNames,
}: {
  allergenNames: Record<number, string>;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<IngredientListItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [chips, setChips] = useState<Chip[]>([]);
  const [result, setResult] = useState<SuggestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [exclusions] = useLocalStorage<number[]>(ALLERGEN_KEY, []);
  const [canStore] = useState(() => storageAvailable());
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // restore selection from sessionStorage (survives back-navigation only);
  // deferred to avoid sync setState inside the effect
  useEffect(() => {
    const id = setTimeout(() => {
      try {
        const raw = sessionStorage.getItem(SEL_KEY);
        if (raw) setChips(JSON.parse(raw));
      } catch {
        /* ignore */
      }
    }, 0);
    return () => clearTimeout(id);
  }, []);
  useEffect(() => {
    try {
      sessionStorage.setItem(SEL_KEY, JSON.stringify(chips));
    } catch {
      /* ignore */
    }
  }, [chips]);

  // debounced ingredient search via BFF
  useEffect(() => {
    const q = query.trim();
    if (!q) return;
    timer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(
          `/api/ingredients/search?q=${encodeURIComponent(q)}`
        );
        if (res.ok) {
          const d = await res.json();
          setHits(Array.isArray(d.items) ? d.items : []);
        }
      } catch {
        /* keep old hits */
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(timer.current);
  }, [query]);

  const visibleHits = query.trim() ? hits : [];

  const addChip = useCallback(
    (it: IngredientListItem) => {
      setChips((c) =>
        c.length >= 30 || c.some((x) => x.id === it.id)
          ? c
          : [...c, { id: it.id, name_zh: it.name_zh }]
      );
      setQuery("");
      setHits([]);
    },
    []
  );

  const exclIds = Array.isArray(exclusions)
    ? exclusions.filter((x) => Number.isInteger(x) && x > 0)
    : [];
  const exclNames = exclIds
    .map((id) => allergenNames[id])
    .filter((n): n is string => Boolean(n));

  async function suggest(newOffset = 0) {
    if (!chips.length || loading) return;
    setLoading(true);
    setError("");
    setOffset(newOffset);
    try {
      const res = await fetch("/api/recipes/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ingredient_ids: chips.map((c) => c.id),
          exclude_allergens: canStore ? exclIds : [],
          limit: 12,
          offset: newOffset,
        }),
      });
      const body = await res.json().catch(() => null);
      if (res.status === 422) {
        const invalid = invalidIngredientIds(body?.detail);
        if (invalid.length) {
          setChips((c) => c.filter((x) => !invalid.includes(x.id)));
          setError(
            `已移除無效食材：${chips
              .filter((x) => invalid.includes(x.id))
              .map((x) => x.name_zh)
              .join("、")}`
          );
          setResult(null);
          return;
        }
      }
      if (!res.ok || !body) {
        setError("食譜配對暫時無法使用，請稍後再試。");
        return;
      }
      setResult(body as SuggestResponse);
    } catch {
      setError("網絡錯誤，請稍後再試。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <section aria-labelledby="sel-h" className="space-y-3">
        <h2 id="sel-h" className="text-lg font-bold text-ink">
          你手上有什麼食材？
        </h2>
        <div className="relative max-w-xl">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜尋食材並加入（如：雞蛋、南瓜）"
            role="combobox"
            aria-controls="ing-hits"
            aria-autocomplete="list"
            aria-expanded={visibleHits.length > 0}
            aria-label="搜尋食材"
            className="min-h-[44px] w-full rounded-xl border border-line bg-surface px-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {visibleHits.length > 0 && (
            <ul
              id="ing-hits"
              className="absolute z-20 mt-1 w-full rounded-xl bg-surface shadow-card ring-1 ring-line"
            >
              {visibleHits.map((h) => (
                <li key={h.id}>
                  <button
                    type="button"
                    onClick={() => addChip(h)}
                    className="flex min-h-[44px] w-full items-center justify-between px-4 text-left text-sm hover:bg-surface-alt focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
                  >
                    <span>{h.name_zh}</span>
                    <span className="text-xs text-ink-muted">
                      {h.rating_label}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {searching && (
          <p className="text-xs text-ink-muted">搜尋中…</p>
        )}
        {chips.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="已選食材">
            {chips.map((c) => (
              <li
                key={c.id}
                className="inline-flex items-center gap-1 rounded-full bg-surface-alt px-3 py-1.5 text-sm text-ink"
              >
                {c.name_zh}
                <button
                  type="button"
                  onClick={() =>
                    setChips((x) => x.filter((y) => y.id !== c.id))
                  }
                  aria-label={`移除 ${c.name_zh}`}
                  className="min-h-[28px] min-w-[28px] text-ink-muted hover:text-trigger"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          onClick={() => suggest(0)}
          disabled={!chips.length || loading}
          className="min-h-[44px] rounded-full bg-primary px-6 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {loading ? "配對中…" : "找食譜"}
        </button>
      </section>

      {!canStore && (
        <WarningBanner title="無法儲存忌口設定">
          結果未排除任何過敏原，請自行留意各食譜的致敏原標示。
        </WarningBanner>
      )}
      {canStore && exclNames.length > 0 && (
        <p className="rounded-xl bg-surface-alt px-4 py-3 text-sm text-ink">
          {result ? (
            exclusionNotice(exclNames, result.excluded_by_allergen_count)
          ) : (
            <>已啟用忌口（{exclNames.join("、")}），配對時會自動排除。</>
          )}
          <Link
            href="/settings"
            className="ml-2 text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            修改忌口
          </Link>
        </p>
      )}

      {error && (
        <WarningBanner title="配對失敗">{error}</WarningBanner>
      )}
      {result?.warnings.length ? (
        <WarningBanner title="你選的食材需要注意">
          <ul className="mt-1 list-inside list-disc">
            {result.warnings.map((w) => (
              <li key={w.ingredient_id}>
                {w.name_zh}：
                {w.reasons.includes("rating_trigger") && "常見誘因"}
                {w.reasons.includes("has_allergen") &&
                  ` 含致敏原（${w.allergens
                    .map((a) => a.name_zh)
                    .join("、")}）`}
              </li>
            ))}
          </ul>
        </WarningBanner>
      ) : null}

      {result && (
        <section aria-live="polite">
          {result.recipes.length ? (
            <>
              <p className="text-sm text-ink-muted">
                共 {result.total} 道食譜（已按覆蓋率與濕疹友善度排序）
              </p>
              <ul className="mt-3 space-y-4">
                {result.recipes.map((r) => (
                  <li key={r.id}>
                    <RecipeCard r={r} />
                  </li>
                ))}
              </ul>
              {result.total > result.limit && (
                <div className="mt-4 flex justify-center gap-3">
                  <button
                    type="button"
                    disabled={offset === 0 || loading}
                    onClick={() => suggest(Math.max(0, offset - result.limit))}
                    className="min-h-[44px] rounded-full border border-line px-4 text-sm disabled:opacity-40"
                  >
                    上一頁
                  </button>
                  <button
                    type="button"
                    disabled={
                      offset + result.limit >= result.total || loading
                    }
                    onClick={() => suggest(offset + result.limit)}
                    className="min-h-[44px] rounded-full border border-line px-4 text-sm disabled:opacity-40"
                  >
                    下一頁
                  </button>
                </div>
              )}
            </>
          ) : (
            <p className="rounded-xl bg-surface-alt px-4 py-6 text-center text-sm text-ink-muted">
              {emptyResultText(
                canStore && exclNames.length > 0,
                result.excluded_by_allergen_count
              )}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
