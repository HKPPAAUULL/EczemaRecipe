import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import SearchBox from "@/components/SearchBox";
import IngredientCard from "@/components/IngredientCard";
import WarningBanner from "@/components/WarningBanner";
import { ApiError, getCategories, searchIngredients } from "@/lib/api";

export const metadata: Metadata = {
  title: "食材庫",
  description: "搜尋或按食物分類瀏覽食材的濕疹適合度評級、致敏原與營養成分。",
};

async function CategoryGrid() {
  let categories;
  try {
    categories = await getCategories();
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <WarningBanner title="暫時無法載入食材分類">
          {err.message}，請稍後再試。
        </WarningBanner>
      );
    }
    throw err;
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {categories.map((c) => (
        <li key={c.id}>
          <Link
            href={`/categories/${c.id}`}
            className="flex items-center justify-between rounded-xl bg-surface p-4 shadow-card ring-1 ring-line transition-shadow hover:shadow-lift focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="font-medium text-ink">{c.name_zh}</span>
            <span className="rounded-full bg-surface-alt px-3 py-1 text-sm text-ink-muted">
              {c.ingredient_count} 項
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

async function Results({ q }: { q: string }) {
  let data;
  try {
    data = await searchIngredients(q);
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <WarningBanner title="暫時無法載入搜尋結果">
          {err.message}，請稍後再試。
        </WarningBanner>
      );
    }
    throw err;
  }
  if (!data.items.length) {
    return (
      <p className="rounded-xl bg-surface-alt px-4 py-6 text-center text-ink-muted">
        找不到「{data.query}」相關食材，請試試其他關鍵字，或
        <Link
          href="/categories"
          className="mx-1 font-medium text-primary hover:underline"
        >
          按分類瀏覽
        </Link>
        。
      </p>
    );
  }
  return (
    <>
      <p className="text-sm text-ink-muted">
        「{data.query}」共 {data.count} 項結果
      </p>
      <ul className="mt-3 grid gap-3 md:grid-cols-2">
        {data.items.map((item) => (
          <IngredientCard key={item.id} item={item} />
        ))}
      </ul>
    </>
  );
}

async function SearchArea({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();
  return (
    <>
      <SearchBox initialValue={query} />
      {query ? <Results q={query} /> : <CategoryGrid />}
    </>
  );
}

export default function CategoriesPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">食材庫</h1>
      <p className="text-sm text-ink-muted">
        搜尋食材名稱，或按食物種類瀏覽，買餸前快速查閱食材適合度。
      </p>
      <Suspense
        fallback={<p className="py-8 text-center text-ink-muted">載入中…</p>}
      >
        <SearchArea searchParams={searchParams} />
      </Suspense>
    </div>
  );
}
