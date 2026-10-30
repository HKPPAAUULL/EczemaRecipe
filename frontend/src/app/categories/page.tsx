import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import WarningBanner from "@/components/WarningBanner";
import { ApiError, getCategories } from "@/lib/api";

export const metadata: Metadata = {
  title: "食材庫",
  description: "按食物分類瀏覽食材，可按濕疹適合度評級篩選。",
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

export default function CategoriesPage() {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">食材庫</h1>
      <p className="text-sm text-ink-muted">
        按食物種類瀏覽，買餸前快速查閱食材適合度。
      </p>
      <Suspense
        fallback={<p className="py-8 text-center text-ink-muted">載入中…</p>}
      >
        <CategoryGrid />
      </Suspense>
    </div>
  );
}
