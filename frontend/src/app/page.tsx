import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import RatingBadge from "@/components/RatingBadge";
import { RATING_META } from "@/lib/rating";
import { buildSearchHref } from "@/lib/navigation";

const QUICK_LINKS = [
  { label: "奶", href: buildSearchHref("奶") },
  { label: "蛋", href: buildSearchHref("蛋") },
  { label: "蔬菜", href: "/categories" },
  { label: "水果", href: "/categories" },
];

const ENTRIES = [
  {
    href: "/ingredients",
    title: "食材查詢",
    desc: "搜尋食材的濕疹適合度評級、致敏原與營養成分。",
  },
  {
    href: "/categories",
    title: "食材庫",
    desc: "按分類瀏覽食材，可按評級篩選，買餸前快速查閱。",
  },
];

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
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-sm">
          <span className="text-ink-muted">常用查詢：</span>
          {QUICK_LINKS.map((l) => (
            <Link
              key={l.label}
              href={l.href}
              className="rounded-full bg-surface px-3.5 py-1.5 text-ink ring-1 ring-line transition-colors hover:bg-surface-alt focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {l.label}
            </Link>
          ))}
        </div>
      </section>

      <section
        aria-label="功能入口"
        className="grid gap-4 md:grid-cols-3"
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
        <div
          className="rounded-2xl bg-surface-alt p-5 ring-1 ring-line"
          aria-disabled="true"
        >
          <h2 className="text-lg font-semibold text-ink-muted">食譜配對</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
            選擇手上食材，配對合適食譜並提示致敏風險。
          </p>
          <span className="mt-3 inline-block rounded-full bg-surface px-3 py-1 text-sm text-ink-muted ring-1 ring-line">
            即將推出
          </span>
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
