import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import SearchBox from "@/components/SearchBox";
import IngredientCard from "@/components/IngredientCard";
import WarningBanner from "@/components/WarningBanner";
import { ApiError, searchIngredients } from "@/lib/api";

export const metadata: Metadata = {
  title: "食材查詢",
  description: "搜尋食材的濕疹適合度評級、致敏原與營養成分。",
};

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
        找不到「{data.query}」相關食材，請試試其他關鍵字，或到
        <Link
          href="/categories"
          className="mx-1 font-medium text-primary hover:underline"
        >
          食材庫
        </Link>
        瀏覽。
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
      <div className="max-w-xl">
        <SearchBox initialValue={query} />
      </div>
      {query ? (
        <Results q={query} />
      ) : (
        <p className="rounded-xl bg-surface-alt px-4 py-6 text-ink-muted">
          輸入食材名稱（例如：雞蛋、番茄、牛奶）查詢其適合度評級；亦可到
          <Link
            href="/categories"
            className="mx-1 font-medium text-primary hover:underline"
          >
            食材庫
          </Link>
          按分類瀏覽。
        </p>
      )}
    </>
  );
}

export default function IngredientsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">食材查詢</h1>
      <Suspense
        fallback={<p className="py-8 text-center text-ink-muted">載入中…</p>}
      >
        <SearchArea searchParams={searchParams} />
      </Suspense>
    </div>
  );
}
