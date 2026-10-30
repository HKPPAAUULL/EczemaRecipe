import Link from "next/link";
import { pageWindow } from "@/lib/navigation";

export default function Pagination({
  total,
  limit,
  offset,
  makeHref,
}: {
  total: number;
  limit: number;
  offset: number;
  makeHref: (offset: number) => string;
}) {
  const w = pageWindow(total, limit, offset);
  if (w.pages <= 1) return null;

  const btn =
    "inline-flex min-h-[44px] items-center rounded-lg px-4 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary";
  return (
    <nav
      aria-label="分頁"
      className="mt-6 flex items-center justify-between gap-2"
    >
      {w.hasPrev && w.prevOffset !== null ? (
        <Link
          href={makeHref(w.prevOffset)}
          className={`${btn} bg-surface text-ink ring-1 ring-line hover:bg-surface-alt`}
        >
          ← 上一頁
        </Link>
      ) : (
        <span />
      )}
      <span className="text-sm text-ink-muted">
        第 {w.page} / {w.pages} 頁 · 共 {total} 項
      </span>
      {w.hasNext && w.nextOffset !== null ? (
        <Link
          href={makeHref(w.nextOffset)}
          className={`${btn} bg-surface text-ink ring-1 ring-line hover:bg-surface-alt`}
        >
          下一頁 →
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
