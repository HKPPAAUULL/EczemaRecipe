import Link from "next/link";

const ITEMS = [
  {
    href: "/recipes",
    label: "食譜配對",
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
        <path
          fill="currentColor"
          d="M8.1 2a1 1 0 0 0-1 1v6.1a3 3 0 0 0 2 2.8V21a1 1 0 1 0 2 0v-9.1a3 3 0 0 0 2-2.8V3a1 1 0 1 0-2 0v6a1 1 0 1 1-2 0V3a1 1 0 0 0-1-1Zm8.9 0a4 4 0 0 0-4 4v4.6a1 1 0 0 0 1 1H16V21a1 1 0 1 0 2 0V3a1 1 0 0 0-1-1Z"
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
    href: "/shopping",
    label: "買餸清單",
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
        <path
          fill="currentColor"
          d="M7 4h10a1 1 0 0 1 1 1v15.2a.6.6 0 0 1-.92.5L12 17.8l-5.08 2.9a.6.6 0 0 1-.92-.5V5a1 1 0 0 1 1-1Zm1.5 4a.75.75 0 0 0 0 1.5h7a.75.75 0 0 0 0-1.5h-7Zm0 4a.75.75 0 0 0 0 1.5h7a.75.75 0 0 0 0-1.5h-7Z"
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
