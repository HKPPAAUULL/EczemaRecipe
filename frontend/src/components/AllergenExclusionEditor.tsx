"use client";

import { useMemo, useState } from "react";
import type { AllergenItem } from "@/lib/api";
import {
  ALLERGEN_KEY,
  readAllergenExclusions,
  storageAvailable,
  useLocalStorage,
} from "@/lib/storage";

const TYPE_LABELS: Record<string, string> = {
  major_allergen: "九大過敏原",
  histamine: "組織胺",
  salicylate: "水楊酸",
  nickel: "鎳",
  other: "其他",
};

export default function AllergenExclusionEditor({
  allergens,
}: {
  allergens: AllergenItem[];
}) {
  const [ids, setIds] = useLocalStorage<number[]>(ALLERGEN_KEY, []);
  const [saved, setSaved] = useState(false);
  const valid = Array.isArray(ids)
    ? ids.filter((x) => Number.isInteger(x) && x > 0)
    : [];
  const validIds = allergens.map((a) => a.id);
  const staleCount = valid.filter((x) => !validIds.includes(x)).length;
  const groups = useMemo(() => {
    const g = new Map<string, AllergenItem[]>();
    for (const a of allergens) {
      const k = TYPE_LABELS[a.type] ?? "其他";
      g.set(k, [...(g.get(k) ?? []), a]);
    }
    return g;
  }, [allergens]);

  function toggle(id: number) {
    const next = valid.includes(id)
      ? valid.filter((x) => x !== id)
      : [...valid, id];
    setIds(next);
    setSaved(true);
  }

  if (!storageAvailable()) {
    return (
      <p className="rounded-xl bg-caution-bg px-4 py-3 text-sm text-caution">
        你的瀏覽器不支援本機儲存，無法保存忌口設定；頁面仍可瀏覽但結果不會
        套用排除。
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-ink-muted">
        已設定 <strong className="text-ink">{valid.length}</strong> 項忌口。
        設定只儲存於你的瀏覽器（localStorage），不會上傳；此功能不是診斷，
        嚴重過敏請諮詢醫生。
      </p>
      {staleCount > 0 && (
        <p className="rounded-lg bg-caution-bg px-3 py-2 text-xs text-caution">
          有 {staleCount} 項舊忌口已不在最新資料中，已自動忽略。
        </p>
      )}
      {[...groups.entries()].map(([label, items]) => (
        <fieldset key={label} className="rounded-2xl bg-surface p-4 ring-1 ring-line">
          <legend className="px-1 text-sm font-semibold text-ink">
            {label}
          </legend>
          <div className="grid gap-1.5 sm:grid-cols-2 md:grid-cols-3">
            {items.map((a) => (
              <label
                key={a.id}
                className="flex min-h-[44px] cursor-pointer items-center gap-2 rounded-lg px-2 text-sm text-ink hover:bg-surface-alt"
              >
                <input
                  type="checkbox"
                  checked={valid.includes(a.id)}
                  onChange={() => toggle(a.id)}
                  className="h-4 w-4 accent-primary"
                />
                {a.name_zh}
                {a.name_en && (
                  <span className="text-xs text-ink-muted">{a.name_en}</span>
                )}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            setIds([]);
            setSaved(true);
          }}
          className="min-h-[44px] rounded-full border border-line px-4 text-sm text-ink-muted hover:border-trigger hover:text-trigger focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          全部清除
        </button>
        <span aria-live="polite" className="text-xs text-suitable">
          {saved ? "已儲存" : ""}
        </span>
      </div>
    </div>
  );
}

export function useExclusionNames(allergens: AllergenItem[]) {
  const ids = readAllergenExclusions();
  return allergens.filter((a) => ids.includes(a.id)).map((a) => a.name_zh);
}
