import Link from "next/link";
import AllergenTag from "@/components/AllergenTag";
import type { RecipeListItem } from "@/lib/recipes";

export default function RecipeBrowseCard({ r }: { r: RecipeListItem }) {
  return (
    <article className="relative flex h-full flex-col rounded-2xl bg-surface p-4 shadow-card ring-1 ring-line transition-shadow hover:shadow-lift md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-bold text-ink">
          <Link
            href={`/recipes/${r.id}`}
            className="after:absolute after:inset-0 after:rounded-2xl after:content-[''] hover:text-primary focus:outline-none focus-visible:after:ring-2 focus-visible:after:ring-primary"
          >
            {r.title}
            {r.is_original && (
              <span className="ml-1.5 align-middle rounded bg-surface-alt px-1.5 py-0.5 text-xs font-normal text-ink-muted">
                原創
              </span>
            )}
          </Link>
          {r.draft && (
            <span className="ml-2 rounded bg-caution-bg px-1.5 py-0.5 text-xs font-normal text-caution">
              尚待人工審核
            </span>
          )}
        </h3>
        {r.likes > 0 && (
          <span className="rounded-full bg-surface-alt px-2.5 py-1 text-xs text-ink-muted">
            👍 {r.likes}
          </span>
        )}
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
      {r.is_original ? (
        <p className="mt-auto pt-3 text-xs text-ink-muted">原創食譜（站方整理）</p>
      ) : (
        <p className="mt-auto pt-3 text-xs text-ink-muted">
          來源：
          {r.source_url ? (
            <a
              href={r.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="relative z-10 text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {r.source_name ?? r.source_url}
            </a>
          ) : (
            r.source_name ?? "—"
          )}
          {r.license && `（${r.license}）`}
        </p>
      )}
    </article>
  );
}
