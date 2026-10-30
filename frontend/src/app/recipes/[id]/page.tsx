import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AllergenTag from "@/components/AllergenTag";
import RatingBadge from "@/components/RatingBadge";
import WarningBanner from "@/components/WarningBanner";
import AddAllToShoppingList from "@/components/AddAllToShoppingList";
import { ApiError, getRecipe } from "@/lib/api";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const item = await getRecipe(Number(id)).catch(() => null);
  if (!item) return { title: "食譜詳情" };
  return {
    title: item.title,
    description: item.description ?? `${item.title} 食譜詳情。`,
  };
}

export default async function RecipeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const num = Number(id);
  if (!Number.isInteger(num) || num <= 0) notFound();
  let item;
  try {
    item = await getRecipe(num);
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <WarningBanner title="暫時無法載入食譜">
          {err.message}，請稍後再試。
        </WarningBanner>
      );
    }
    throw err;
  }
  if (!item) notFound();

  return (
    <div className="space-y-6">
      <header className="rounded-2xl bg-surface p-5 shadow-card ring-1 ring-line md:p-6">
        <Link
          href="/recipes"
          className="text-sm text-ink-muted hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          ← 食譜配對
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-ink md:text-3xl">
          {item.title}
          {item.is_original && (
            <span className="ml-2 align-middle rounded bg-surface-alt px-2 py-1 text-xs font-normal text-ink-muted">
              原創食譜（站方整理）
            </span>
          )}
          {item.draft && (
            <span className="ml-2 align-middle rounded bg-caution-bg px-2 py-1 text-xs font-normal text-caution">
              此資料尚待人工審核
            </span>
          )}
        </h1>
        {item.description && (
          <p className="mt-2 text-sm text-ink-muted">{item.description}</p>
        )}
        {(item.cook_time != null || item.servings != null) && (
          <p className="mt-2 text-xs text-ink-muted">
            {item.cook_time != null && `烹調時間約 ${item.cook_time} 分鐘`}
            {item.cook_time != null && item.servings != null && "・"}
            {item.servings != null && `${item.servings} 人份`}
          </p>
        )}
        {item.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.tags.map((t) => (
              <span
                key={t}
                className="rounded bg-surface-alt px-1.5 py-0.5 text-xs text-ink-muted"
              >
                {t}
              </span>
            ))}
          </div>
        )}
      </header>

      {item.allergen_warning && (
        <WarningBanner title="致敏原警示">
          此食譜含致敏相關成分，請細閱下方標示。
        </WarningBanner>
      )}
      {item.allergens.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-ink">致敏原</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.allergens.map((a) => (
              <AllergenTag key={a} name={a} />
            ))}
          </div>
        </section>
      )}

      <section className="rounded-2xl bg-surface p-5 ring-1 ring-line">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">食材</h2>
          <AddAllToShoppingList
            items={item.ingredients
              .filter((i) => !i.is_staple)
              .map((i) => ({
                ingredientId: i.ingredient_id,
                name: i.name_zh,
                allergenIds: i.allergens.map((a) => a.id),
              }))}
          />
        </div>
        <ul className="mt-3 divide-y divide-line">
          {item.ingredients.map((i) => (
            <li
              key={`${i.ingredient_id}-${i.raw_text}`}
              className="flex flex-wrap items-center gap-2 py-2.5"
            >
              <Link
                href={`/ingredients/${i.ingredient_id}`}
                className="text-sm font-medium text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {i.name_zh}
              </Link>
              <RatingBadge rating={i.eczema_rating as never} />
              <span className="text-xs text-ink-muted">{i.raw_text}</span>
              {i.is_staple && (
                <span className="rounded bg-surface-alt px-1.5 py-0.5 text-xs text-ink-muted">
                  常備
                </span>
              )}
              {i.allergens.map((a) => (
                <AllergenTag key={a.id} name={a.name_zh} />
              ))}
            </li>
          ))}
        </ul>
        {item.unmatched_ingredients.length > 0 && (
          <p className="mt-3 text-xs text-ink-muted">
            未能識別的食材：{item.unmatched_ingredients.join("、")}
            （致敏資訊可能不完整）
          </p>
        )}
        {item.unmatched_staples.length > 0 && (
          <p className="mt-1 text-xs text-ink-muted">
            未能識別的常備料：{item.unmatched_staples.join("、")}
          </p>
        )}
      </section>

      {item.steps.length > 0 && (
        <section className="rounded-2xl bg-surface p-5 ring-1 ring-line">
          <h2 className="text-sm font-semibold text-ink">步驟</h2>
          <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-ink">
            {item.steps.map((st, i) => (
              <li key={i}>{st}</li>
            ))}
          </ol>
        </section>
      )}

      {item.notes && (
        <section className="rounded-2xl bg-surface p-5 ring-1 ring-line">
          <h2 className="text-sm font-semibold text-ink">備註</h2>
          <p className="mt-2 text-sm text-ink-muted">{item.notes}</p>
        </section>
      )}

      {item.is_original ? (
        <p className="text-xs text-ink-muted">原創食譜（站方整理）</p>
      ) : (
      <p className="text-xs text-ink-muted">
        來源：
        {item.source_url ? (
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {item.source_name ?? item.source_url}
          </a>
        ) : (
          item.source_name ?? "—"
        )}
        {item.license && `（${item.license}）`}
      </p>
      )}
    </div>
  );
}
