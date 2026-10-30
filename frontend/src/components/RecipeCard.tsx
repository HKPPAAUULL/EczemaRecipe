"use client";

import Link from "next/link";
import AllergenTag from "@/components/AllergenTag";
import AddToShoppingListButton from "@/components/AddToShoppingListButton";
import { coverageText, type RecipeSuggestion } from "@/lib/recipes";

export default function RecipeCard({ r }: { r: RecipeSuggestion }) {
  return (
    <article className="rounded-2xl bg-surface p-4 shadow-card ring-1 ring-line md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-bold text-ink">
          <Link
            href={`/recipes/${r.id}`}
            className="hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {r.title}
          </Link>
          {r.draft && (
            <span className="ml-2 rounded bg-caution-bg px-1.5 py-0.5 text-xs font-normal text-caution">
              尚待人工審核
            </span>
          )}
        </h3>
        <span className="rounded-full bg-surface-alt px-2.5 py-1 text-xs text-ink-muted">
          {coverageText(r)}（{Math.round(r.coverage * 100)}%）
        </span>
      </div>
      {r.description && (
        <p className="mt-1.5 line-clamp-2 text-sm text-ink-muted">
          {r.description}
        </p>
      )}
      {(r.cook_time != null || r.servings != null) && (
        <p className="mt-1 text-xs text-ink-muted">
          {r.cook_time != null && `約 ${r.cook_time} 分鐘`}
          {r.cook_time != null && r.servings != null && "・"}
          {r.servings != null && `${r.servings} 人份`}
        </p>
      )}
      {r.allergen_warning && (
        <p className="mt-2 flex items-center gap-1.5 rounded-lg bg-trigger-bg px-3 py-2 text-xs font-medium text-trigger">
          <span aria-hidden="true">⚠</span> 含致敏相關成分或需注意食材
        </p>
      )}
      {r.allergens.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {r.allergens.map((a) => (
            <AllergenTag key={a} name={a} />
          ))}
        </div>
      )}
      {r.unknown_allergen_hints && r.unknown_allergen_hints.length > 0 && (
        <p className="mt-2 rounded-lg bg-caution-bg px-3 py-2 text-xs text-caution">
          致敏資訊可能不完整：{r.unknown_allergen_hints.join("、")}
        </p>
      )}
      {r.trigger_ingredients.length > 0 && (
        <p className="mt-2 text-xs font-medium text-trigger">
          含常見誘因食材：{r.trigger_ingredients.join("、")}
        </p>
      )}
      {r.unmatched_ingredients.length > 0 && (
        <p className="mt-2 text-xs text-ink-muted">
          含未能識別的食材：{r.unmatched_ingredients.join("、")}
          ，致敏資訊可能不完整
        </p>
      )}
      {r.missing.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-ink-muted">
            你還缺少的食材：
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {r.missing.map((m) => (
              <li key={m} className="inline-flex items-center gap-1">
                <span className="rounded bg-surface-alt px-1.5 py-0.5 text-xs text-ink">
                  {m}
                </span>
                <AddToShoppingListButton name={m} small />
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-3 text-xs text-ink-muted">
        來源：
        {r.source_url ? (
          <a
            href={r.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {r.source_name ?? r.source_url}
          </a>
        ) : (
          r.source_name ?? "—"
        )}
        {r.license && `（${r.license}）`}
      </p>
    </article>
  );
}
