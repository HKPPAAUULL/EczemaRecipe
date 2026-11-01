import Link from "next/link";
import { Suspense } from "react";
import SearchBox from "@/components/SearchBox";
import RatingBadge from "@/components/RatingBadge";
import RecipeBrowseCard from "@/components/RecipeBrowseCard";
import WarningBanner from "@/components/WarningBanner";
import RecentSearches from "@/components/RecentSearches";
import { ApiError, getRecipes } from "@/lib/api";
import { RATING_META } from "@/lib/rating";

const ENTRIES = [
  {
    href: "/recipes",
    title: "食譜配對",
    desc: "選擇手上食材，配對合適食譜並按你的忌口排除。",
  },
  {
    href: "/categories",
    title: "食材庫",
    desc: "搜尋或按分類瀏覽食材的濕疹適合度評級、致敏原與營養成分。",
  },
  {
    href: "/settings",
    title: "我的忌口",
    desc: "設定致敏原忌口，配對自動排除（只存於你的瀏覽器）。",
  },
  {
    href: "/shopping",
    title: "買餸清單",
    desc: "記低要買的食材，可複製或列印（只存於你的瀏覽器）。",
  },
];

async function RecommendedRecipes() {
  let data;
  try {
    data = await getRecipes({ limit: 6, sort: "random" });
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <WarningBanner title="暫時無法載入推薦食譜">
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
  return (
    <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {data.recipes.map((r) => (
        <li key={r.id}>
          <RecipeBrowseCard r={r} />
        </li>
      ))}
    </ul>
  );
}

export default function Home() {
  return (
    <div className="space-y-10">
      <section className="pt-6 text-center md:pt-14">
        <h1 className="text-3xl font-bold tracking-tight text-ink md:text-5xl">
          濕疹食堂
        </h1>
        <p className="mt-2 text-base text-ink-muted md:text-lg">
          查食材，安心煮 —— 濕疹人士的食材適合度參考
        </p>
        <div className="mx-auto mt-6 max-w-xl">
          <SearchBox large />
        </div>
        <RecentSearches />
      </section>

      <section
        aria-label="功能入口"
        className="grid gap-4 md:grid-cols-3 lg:grid-cols-5"
      >
        {ENTRIES.map((e) => (
          <Link
            key={e.href}
            href={e.href}
            className="rounded-2xl bg-surface p-5 shadow-card ring-1 ring-line transition-shadow hover:shadow-lift focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <h2 className="text-lg font-semibold text-primary">{e.title}</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
              {e.desc}
            </p>
            <span className="mt-3 inline-block text-sm font-medium text-primary">
              進入 →
            </span>
          </Link>
        ))}
      </section>

      <section aria-labelledby="rec-h">
        <div className="flex items-center justify-between gap-3">
          <h2 id="rec-h" className="text-lg font-semibold text-ink">
            推薦食譜
          </h2>
          <Link
            href="/recipes"
            className="inline-flex min-h-[36px] items-center rounded-full bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            食譜配對 →
          </Link>
        </div>
        <div className="mt-4">
          <Suspense
            fallback={
              <p className="py-8 text-center text-ink-muted">載入中…</p>
            }
          >
            <RecommendedRecipes />
          </Suspense>
        </div>
      </section>

      <section
        aria-label="評級說明"
        className="rounded-2xl bg-surface p-5 shadow-card ring-1 ring-line md:p-6"
      >
        <h2 className="text-lg font-semibold text-ink">評級怎樣看？</h2>
        <ul className="mt-4 grid gap-3 md:grid-cols-2">
          {(
            ["suitable", "caution", "trigger", "unrated"] as const
          ).map((r) => (
            <li key={r} className="flex items-start gap-3">
              <RatingBadge rating={r} />
              <p className="pt-0.5 text-sm leading-relaxed text-ink-muted">
                {RATING_META[r].description}
              </p>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm text-ink-muted">
          評級僅供參考且因人而異，詳見
          <Link
            href="/about"
            className="mx-1 font-medium text-primary underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            關於本站
          </Link>
          。
        </p>
      </section>
    </div>
  );
}
