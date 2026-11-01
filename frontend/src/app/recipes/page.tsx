import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import RecipesClient from "@/components/RecipesClient";
import RecipeBrowseCard from "@/components/RecipeBrowseCard";
import WarningBanner from "@/components/WarningBanner";
import { ApiError, getAllergens, getRecipes } from "@/lib/api";
import { pageWindow } from "@/lib/navigation";

export const metadata: Metadata = {
  title: "食譜配對",
  description: "用你手上的食材配對食譜，或瀏覽全部食譜，按忌口自動排除並標示致敏原。",
};

const PAGE_SIZE = 12;

async function AllRecipes({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  const { offset } = await searchParams;
  const parsed = Number.parseInt(offset ?? "0", 10);
  const current = Number.isInteger(parsed) && parsed > 0 ? parsed : 0;
  let data;
  try {
    data = await getRecipes({ limit: PAGE_SIZE, offset: current });
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
  if (!data.recipes.length) {
    return (
      <p className="rounded-xl bg-surface-alt px-4 py-6 text-center text-sm text-ink-muted">
        未有食譜。
      </p>
    );
  }
  const w = pageWindow(data.total, data.limit, data.offset);
  return (
    <>
      <p className="text-sm text-ink-muted">
        共 {data.total} 道食譜（第 {w.page}/{w.pages} 頁）
      </p>
      <ul className="mt-3 grid gap-4 md:grid-cols-2">
        {data.recipes.map((r) => (
          <li key={r.id}>
            <RecipeBrowseCard r={r} />
          </li>
        ))}
      </ul>
      {data.total > data.limit && (
        <div className="mt-4 flex justify-center gap-3">
          {w.hasPrev ? (
            <Link
              href={`/recipes?offset=${w.prevOffset}`}
              className="inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm"
            >
              上一頁
            </Link>
          ) : (
            <span className="inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm opacity-40">
              上一頁
            </span>
          )}
          {w.hasNext ? (
            <Link
              href={`/recipes?offset=${w.nextOffset}`}
              className="inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm"
            >
              下一頁
            </Link>
          ) : (
            <span className="inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm opacity-40">
              下一頁
            </span>
          )}
        </div>
      )}
    </>
  );
}

export default async function RecipesPage({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string }>;
}) {
  let allergenNames: Record<number, string> = {};
  try {
    const allergens = await getAllergens();
    allergenNames = Object.fromEntries(
      allergens.map((a) => [a.id, a.name_zh])
    );
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <div className="space-y-5">
          <h1 className="text-2xl font-bold text-ink">食譜配對</h1>
          <WarningBanner title="暫時無法載入資料">
            {err.message}，請稍後再試。
          </WarningBanner>
        </div>
      );
    }
    throw err;
  }
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">食譜配對</h1>
      <p className="text-sm text-ink-muted">
        加入你手上的食材，我們會配對食譜並按你的
        <a
          href="/settings"
          className="mx-1 text-primary hover:underline"
        >
          忌口
        </a>
        自動排除；所有致敏標示來自資料庫。
      </p>
      <RecipesClient allergenNames={allergenNames} />
      <section aria-labelledby="all-recipes-h" className="space-y-3 pt-4">
        <h2 id="all-recipes-h" className="text-lg font-bold text-ink">
          所有食譜
        </h2>
        <Suspense
          fallback={<p className="py-8 text-center text-ink-muted">載入中…</p>}
        >
          <AllRecipes searchParams={searchParams} />
        </Suspense>
      </section>
    </div>
  );
}
