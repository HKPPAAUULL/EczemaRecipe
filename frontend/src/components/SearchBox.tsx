"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { buildSearchHref } from "@/lib/navigation";
import { pushRecentSearch } from "@/lib/recentSearches";
import SearchField, {
  pillActionClass,
  SearchIcon,
} from "@/components/SearchField";

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
    if (trimmed) {
      pushRecentSearch(trimmed);
      router.push(buildSearchHref(trimmed));
    }
  }

  return (
    <form onSubmit={onSubmit} role="search" className="w-full">
      <SearchField
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="搜尋食材，例如：雞蛋、番茄、牛奶"
        aria-label="搜尋食材"
        large={large}
        icon={<SearchIcon />}
        trailing={
          <button type="submit" className={pillActionClass}>
            搜尋
          </button>
        }
      />
    </form>
  );
}
