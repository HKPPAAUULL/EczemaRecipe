import Link from "next/link";

const ITEMS = [
  {
    href: "/",
    label: "首頁",
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
        <path
          fill="currentColor"
          d="M12 2.7 2.7 10a1 1 0 0 0-.3.7V20a1 1 0 0 0 1 1h5v-6h7.2v6h5a1 1 0 0 0 1-1v-9.3a1 1 0 0 0-.3-.7L12 2.7Z"
        />
      </svg>
    ),
  },
  {
    href: "/ingredients",
    label: "食材查詢",
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
        <path
          fill="currentColor"
          d="M10.5 3a7.5 7.5 0 1 0 4.6 13.4l4 4a.9.9 0 0 0 1.3-1.3l-4-4A7.5 7.5 0 0 0 10.5 3Zm0 1.8a5.7 5.7 0 1 1 0 11.4 5.7 5.7 0 0 1 0-11.4Z"
        />
      </svg>
    ),
  },
  {
    href: "/categories",
    label: "食材庫",
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
        <path
          fill="currentColor"
          d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z"
        />
      </svg>
    ),
  },
  {
    href: "/about",
    label: "關於",
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
        <path
          fill="currentColor"
          d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15.5h-2V10h2v7.5ZM12 8.8a1.3 1.3 0 1 1 0-2.6 1.3 1.3 0 0 1 0 2.6Z"
        />
      </svg>
    ),
  },
];

export default function BottomNav() {
  return (
    <nav
      aria-label="底部導航"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface md:hidden"
    >
      <ul className="grid grid-cols-4">
        {ITEMS.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="flex min-h-[56px] flex-col items-center justify-center gap-0.5 py-1.5 text-xs text-ink-muted transition-colors hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
            >
              {item.icon}
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
