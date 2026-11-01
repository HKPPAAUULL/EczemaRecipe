"use client";

import Link from "next/link";
import { buildSearchHref } from "@/lib/navigation";
import { normalizeRecent } from "@/lib/recentSearches";
import { RECENT_KEY, useLocalStorage } from "@/lib/storage";

export default function RecentSearches() {
  const [stored, setStored] = useLocalStorage<unknown>(RECENT_KEY, []);
  const items = normalizeRecent(stored);
  if (!items.length) return null;
  return (
    <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-sm">
      <span className="text-ink-muted">最近查詢：</span>
      {items.map((q) => (
        <Link
          key={q}
          href={buildSearchHref(q)}
          className="rounded-full bg-surface px-3.5 py-1.5 text-ink ring-1 ring-line transition-colors hover:bg-surface-alt focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {q}
        </Link>
      ))}
      <button
        type="button"
        onClick={() => setStored([])}
        className="px-1 py-1.5 text-xs text-ink-muted underline-offset-2 hover:text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        清除
      </button>
    </div>
  );
}
