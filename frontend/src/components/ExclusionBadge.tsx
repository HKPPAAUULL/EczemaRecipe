"use client";

import { ALLERGEN_KEY, useLocalStorage } from "@/lib/storage";

export default function ExclusionBadge() {
  const [ids] = useLocalStorage<number[]>(ALLERGEN_KEY, []);
  const n = Array.isArray(ids)
    ? ids.filter((x) => Number.isInteger(x) && x > 0).length
    : 0;
  if (!n) return null;
  return (
    <span
      className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-xs font-bold text-white"
      aria-label={`已設定 ${n} 項忌口`}
    >
      {n}
    </span>
  );
}
