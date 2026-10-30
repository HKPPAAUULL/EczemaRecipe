"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { buildSearchHref } from "@/lib/navigation";

export default function SearchBox({
  initialValue = "",
  large = false,
}: {
  initialValue?: string;
  large?: boolean;
}) {
  const [q, setQ] = useState(initialValue);
  const router = useRouter();

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = q.trim();
    if (trimmed) router.push(buildSearchHref(trimmed));
  }

  return (
    <form onSubmit={onSubmit} role="search" className="w-full">
      <div
        className={`flex items-center gap-2 rounded-full bg-surface shadow-card ring-1 ring-line focus-within:ring-2 focus-within:ring-primary ${
          large ? "px-5 py-3.5" : "px-4 py-2.5"
        }`}
      >
        <svg
          viewBox="0 0 20 20"
          className="h-5 w-5 shrink-0 text-ink-muted"
          aria-hidden="true"
        >
          <path
            fill="currentColor"
            d="M9 3a6 6 0 1 0 3.7 10.7l3.2 3.1a.75.75 0 1 0 1-1l-3.1-3.2A6 6 0 0 0 9 3Zm0 1.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Z"
          />
        </svg>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜尋食材，例如：雞蛋、番茄、牛奶"
          aria-label="搜尋食材"
          className={`w-full bg-transparent text-ink outline-none placeholder:text-ink-muted/70 ${
            large ? "text-lg" : "text-base"
          }`}
        />
        <button
          type="submit"
          className="shrink-0 rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          搜尋
        </button>
      </div>
    </form>
  );
}
