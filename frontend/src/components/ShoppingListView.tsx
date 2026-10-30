"use client";

import { useState } from "react";
import {
  ALLERGEN_KEY,
  SHOPPING_KEY,
  storageAvailable,
  useLocalStorage,
} from "@/lib/storage";
import {
  allergenHitIds,
  clearChecked,
  makeItem,
  removeItem,
  toPlainText,
  toggleItem,
  addItem,
  type ShoppingItem,
} from "@/lib/shoppingList";

export default function ShoppingListView() {
  const [list, setList] = useLocalStorage<ShoppingItem[]>(SHOPPING_KEY, []);
  const [exclusions] = useLocalStorage<number[]>(ALLERGEN_KEY, []);
  const [text, setText] = useState("");
  const [copied, setCopied] = useState(false);
  const items = Array.isArray(list) ? list : [];
  const excl = Array.isArray(exclusions) ? exclusions : [];

  function addFreeText() {
    const item = makeItem({ name: text });
    if (item) setList(addItem(items, item));
    setText("");
  }

  async function copyAll() {
    const t = toPlainText(items);
    try {
      await navigator.clipboard.writeText(t);
      setCopied(true);
      setText("");
    } catch {
      setText(t); // fallback: show text box
    }
  }

  if (!storageAvailable()) {
    return (
      <p className="rounded-xl bg-caution-bg px-4 py-3 text-sm text-caution">
        你的瀏覽器不支援本機儲存，無法使用買餸清單。
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 print:hidden">
        <button
          type="button"
          onClick={copyAll}
          className="min-h-[44px] rounded-full bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          複製為文字
        </button>
        <button
          type="button"
          onClick={() => setList(clearChecked(items))}
          className="min-h-[44px] rounded-full border border-line px-4 text-sm text-ink-muted hover:border-primary hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          清除已勾選
        </button>
        <button
          type="button"
          onClick={() => {
            if (window.confirm("確定清空整個買餸清單？")) setList([]);
          }}
          className="min-h-[44px] rounded-full border border-line px-4 text-sm text-ink-muted hover:border-trigger hover:text-trigger focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          清空
        </button>
        <button
          type="button"
          onClick={() => window.print()}
          className="min-h-[44px] rounded-full border border-line px-4 text-sm text-ink-muted hover:border-primary hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          列印
        </button>
      </div>
      {copied && (
        <p aria-live="polite" className="text-xs text-suitable print:hidden">
          已複製到剪貼簿
        </p>
      )}
      <div className="flex gap-2 print:hidden">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addFreeText()}
          placeholder="手動加入項目（如：秋葵）"
          maxLength={80}
          className="min-h-[44px] flex-1 rounded-xl border border-line bg-surface px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          type="button"
          onClick={addFreeText}
          className="min-h-[44px] rounded-full bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark"
        >
          加入
        </button>
      </div>
      {items.length === 0 ? (
        <p className="rounded-xl bg-surface-alt px-4 py-6 text-center text-sm text-ink-muted">
          清單是空的。到食譜配對或食材頁面按「+ 買餸清單」加入食材。
        </p>
      ) : (
        <ul className="divide-y divide-line rounded-2xl bg-surface ring-1 ring-line">
          {items.map((i) => {
            const hits = allergenHitIds(i, excl);
            return (
              <li key={i.id} className="flex items-center gap-3 px-4 py-3">
                <input
                  type="checkbox"
                  checked={i.checked}
                  onChange={() => setList(toggleItem(items, i.id))}
                  className="h-5 w-5 accent-primary print:hidden"
                  aria-label={`勾選 ${i.label}`}
                />
                <span
                  className={`flex-1 text-sm ${
                    i.checked ? "text-ink-muted line-through" : "text-ink"
                  }`}
                >
                  {i.label}
                  {i.category && (
                    <span className="ml-1 text-xs text-ink-muted">
                      （{i.category}）
                    </span>
                  )}
                </span>
                {hits.length > 0 && (
                  <span className="rounded bg-trigger-bg px-1.5 py-0.5 text-xs text-trigger">
                    致敏注意
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => setList(removeItem(items, i.id))}
                  aria-label={`刪除 ${i.label}`}
                  className="min-h-[44px] min-w-[44px] text-ink-muted hover:text-trigger focus:outline-none focus-visible:ring-2 focus-visible:ring-primary print:hidden"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-xs text-ink-muted print:hidden">
        清單只儲存於你的瀏覽器（localStorage），最多 200 項。
      </p>
    </div>
  );
}
