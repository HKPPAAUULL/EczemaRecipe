"use client";

import { SHOPPING_KEY, useLocalStorage } from "@/lib/storage";
import type { ShoppingItem } from "@/lib/shoppingList";

// Badge showing the number of unchecked (still-to-buy) items.
// `className` is for positioning only (e.g. absolute overlay) — it is
// appended after the base classes so don't pass conflicting size classes.
export default function ShoppingBadge({ className = "" }: { className?: string }) {
  const [list] = useLocalStorage<ShoppingItem[]>(SHOPPING_KEY, []);
  const n = Array.isArray(list)
    ? list.filter((i) => i && !i.checked).length
    : 0;
  if (!n) return null;
  return (
    <span
      className={`inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-xs font-bold text-white ${className}`}
      aria-label={`買餸清單有 ${n} 項未買`}
    >
      {n}
    </span>
  );
}
