import Link from "next/link";

export const NAV_ITEMS = [
  { href: "/", label: "首頁" },
  { href: "/ingredients", label: "食材查詢" },
  { href: "/categories", label: "食材庫" },
  { href: "/about", label: "關於" },
] as const;

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-4 md:px-6">
        <Link
          href="/"
          className="flex items-baseline gap-2 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <span className="text-xl font-bold text-primary">濕疹食堂</span>
          <span className="text-xs text-ink-muted">Eczema Kitchen</span>
        </Link>
        <nav aria-label="主導航" className="hidden md:block">
          <ul className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface-alt hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
