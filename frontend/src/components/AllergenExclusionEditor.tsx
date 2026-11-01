"use client";

import { useMemo, useState } from "react";
import type { AllergenItem } from "@/lib/api";
import {
  ALLERGEN_KEY,
  readAllergenExclusions,
  storageAvailable,
  useLocalStorage,
} from "@/lib/storage";

const TYPE_META: Record<
  string,
  { label: string; desc: string; chip: string }
> = {
  major_allergen: {
    label: "九大過敏原",
    desc: "常見致敏食物類別（奶、蛋、花生、木本堅果、大豆、小麥、魚、甲殼類、芝麻）",
    chip: "bg-trigger-bg text-trigger",
  },
  histamine: {
    label: "組織胺",
    desc: "醃製、發酵等組織胺含量較高的食物類別",
    chip: "bg-caution-bg text-caution",
  },
  salicylate: {
    label: "水楊酸",
    desc: "天然水楊酸含量較高的食物類別",
    chip: "bg-surface-alt text-ink",
  },
  nickel: {
    label: "鎳",
    desc: "鎳含量較高的食物類別",
    chip: "bg-surface-alt text-ink",
  },
  other: {
    label: "其他",
    desc: "其他致敏相關類別",
    chip: "bg-surface-alt text-ink",
  },
};

const FALLBACK_META = {
  label: "其他",
  desc: "其他致敏相關類別",
  chip: "bg-surface-alt text-ink",
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
      const k = (TYPE_META[a.type] ?? FALLBACK_META).label;
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
      {[...groups.entries()].map(([label, items]) => {
        const meta =
          Object.values(TYPE_META).find((m) => m.label === label) ??
          FALLBACK_META;
        const picked = items.filter((a) => valid.includes(a.id)).length;
        return (
        <fieldset key={label} className="rounded-2xl bg-surface p-4 ring-1 ring-line">
          <legend className="sr-only">{label}</legend>
          <div className="mb-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 border-b border-line pb-3">
            <span
              className={`rounded-full px-3 py-1 text-sm font-bold ${meta.chip}`}
            >
              {label}
            </span>
            <span className="text-xs text-ink-muted">{meta.desc}</span>
            {picked > 0 && (
              <span className="ml-auto rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                已選 {picked}/{items.length}
              </span>
            )}
          </div>
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
        );
      })}
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
