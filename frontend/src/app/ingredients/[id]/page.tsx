import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import AllergenTag from "@/components/AllergenTag";
import InsufficientDataNotice from "@/components/InsufficientDataNotice";
import NutrientTable from "@/components/NutrientTable";
import RatingBadge from "@/components/RatingBadge";
import RecipeBrowseCard from "@/components/RecipeBrowseCard";
import TraditionNotes from "@/components/TraditionNotes";
import WarningBanner from "@/components/WarningBanner";
import AddToShoppingListButton from "@/components/AddToShoppingListButton";
import {
  ApiError,
  getIngredient,
  getRecipes,
  type IngredientDetail,
} from "@/lib/api";

async function fetchDetail(id: string) {
  const numeric = Number(id);
  if (!Number.isInteger(numeric) || numeric <= 0) return null;
  return getIngredient(numeric);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  let item: IngredientDetail | null = null;
  let errored = false;
  try {
    item = await fetchDetail(id);
  } catch {
    errored = true;
  }
  // notFound() here resolves before the body streams → real 404 status;
  // an unreachable API is not a 404
  if (!item && !errored) notFound();
  if (!item) return { title: "食材詳情" };
  return {
    title: `${item.name_zh} — ${item.rating_label}`,
    description: `${item.name_zh} 的濕疹適合度評級、致敏原與營養成分。`,
  };
}

async function RelatedRecipes({ ingredientId }: { ingredientId: number }) {
  let data;
  try {
    data = await getRecipes({
      ingredient: ingredientId,
      limit: 4,
      sort: "popular",
    });
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <WarningBanner title="暫時無法載入相關食譜">
          {err.message}，請稍後再試。
        </WarningBanner>
      );
    }
    throw err;
  }
  if (!data.recipes.length) {
    return (
      <p className="mt-3 rounded-xl bg-surface-alt px-4 py-6 text-center text-sm text-ink-muted">
        暫時未有使用此食材的食譜。
      </p>
    );
  }
  return (
    <>
      <ul className="mt-3 grid gap-4 md:grid-cols-2">
        {data.recipes.map((r) => (
          <li key={r.id}>
            <RecipeBrowseCard r={r} />
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm">
        <Link
          href={`/recipes?ingredient=${ingredientId}`}
          className="font-medium text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          瀏覽全部 {data.total} 道食譜 →
        </Link>
      </p>
    </>
  );
}

function DetailBody({ item }: { item: IngredientDetail }) {
  return (
    <div className="space-y-6">
      <header className="rounded-2xl bg-surface p-5 shadow-card ring-1 ring-line md:p-6">
        {item.category ? (
          <Link
            href={`/categories/${item.category.id}`}
            className="text-sm text-ink-muted hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            ← {item.category.name_zh}
          </Link>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-ink md:text-3xl">
            {item.name_zh}
          </h1>
          <RatingBadge rating={item.eczema_rating} label={item.rating_label} large />
        </div>
        {item.name_en ? (
          <p className="mt-1 text-ink-muted">{item.name_en}</p>
        ) : null}
        {item.aliases.length ? (
          <p className="mt-2 text-sm text-ink-muted">
            又稱：{item.aliases.join("、")}
          </p>
        ) : null}
        {item.rating_reason ? (
          <p className="mt-4 rounded-xl bg-surface-alt px-4 py-3 text-sm leading-relaxed text-ink">
            {item.rating_reason}
          </p>
        ) : null}
        <div className="mt-4">
          <AddToShoppingListButton
            ingredientId={item.id}
            name={item.name_zh}
            category={item.category?.name_zh}
            allergenIds={item.allergens.map((a) => a.id)}
          />
        </div>
      </header>

      {item.draft ? (
        <WarningBanner title="此資料尚待人工審核">
          以下內容為草稿，可能不完整或未經確認，僅供參考。
        </WarningBanner>
      ) : null}

      {item.eczema_rating === "unrated" ? <InsufficientDataNotice /> : null}

      <section aria-labelledby="allergen-h">
        <h2 id="allergen-h" className="text-lg font-semibold text-ink">
          致敏原
        </h2>
        {item.allergens.length ? (
          <ul className="mt-3 flex flex-wrap gap-2">
            {item.allergens.map((a) => (
              <li key={a.id}>
                <AllergenTag name={a.name_zh} severity={a.severity} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-ink-muted">未標記已知致敏原。</p>
        )}
      </section>

      <section aria-labelledby="nutrition-h">
        <h2 id="nutrition-h" className="text-lg font-semibold text-ink">
          營養成分
        </h2>
        <div className="mt-3">
          <NutrientTable nutrients={item.nutrients} />
        </div>
      </section>

      <TraditionNotes notes={item.tradition_notes} />

      <section aria-labelledby="recipes-h">
        <h2 id="recipes-h" className="text-lg font-semibold text-ink">
          相關食譜
        </h2>
        <Suspense
          fallback={
            <p className="mt-3 py-8 text-center text-ink-muted">載入中…</p>
          }
        >
          <RelatedRecipes ingredientId={item.id} />
        </Suspense>
      </section>

      {item.evidence.length ? (
        <section aria-labelledby="evidence-h">
          <h2 id="evidence-h" className="text-lg font-semibold text-ink">
            參考來源
          </h2>
          <ul className="mt-3 space-y-2">
            {item.evidence.map((e, i) => (
              <li key={i} className="text-sm">
                {e.url ? (
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    {e.title}
                  </a>
                ) : (
                  <span>{e.title}</span>
                )}
                <span className="ml-2 text-xs text-ink-muted">
                  {[e.source_type, e.year].filter(Boolean).join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="text-xs text-ink-muted">
        {item.needs_senior_review ? "此項目標記為需資深審核。" : null}
        {item.updated_at
          ? `最後更新：${new Date(item.updated_at).toLocaleDateString("zh-HK")}`
          : null}
      </p>
    </div>
  );
}

export default async function IngredientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let item: IngredientDetail | null;
  try {
    item = await fetchDetail(id);
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <WarningBanner title="暫時無法載入食材資料">
          {err.message}，請稍後再試。
        </WarningBanner>
      );
    }
    throw err;
  }
  if (!item) notFound();
  return <DetailBody item={item} />;
}
