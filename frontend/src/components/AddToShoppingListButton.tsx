"use client";

import { useState } from "react";
import {
  SHOPPING_KEY,
  storageAvailable,
  useLocalStorage,
} from "@/lib/storage";
import {
  addItem,
  makeItem,
  type ShoppingItem,
} from "@/lib/shoppingList";

export default function AddToShoppingListButton({
  ingredientId,
  name,
  category,
  allergenIds = [],
  small = false,
}: {
  ingredientId?: number;
  name: string;
  category?: string;
  allergenIds?: number[];
  small?: boolean;
}) {
  const [list, setList] = useLocalStorage<ShoppingItem[]>(SHOPPING_KEY, []);
  const [msg, setMsg] = useState("");
  const added = ingredientId != null
    ? list.some((i) => i.id === `ing:${ingredientId}`)
    : list.some((i) => i.id === `txt:${name.trim().toLowerCase()}`);

  function add() {
    if (added) return;
    if (!storageAvailable()) {
      setMsg("瀏覽器不支援本機儲存");
      return;
    }
    const item = makeItem({ ingredientId, name, category, allergenIds });
    const next = addItem(list, item);
    if (next === list) {
      setMsg("清單已滿或已有此項");
      return;
    }
    setList(next);
    setMsg(`已加入「${item?.label}」`);
  }

  const cls = small
    ? "inline-flex min-h-[44px] items-center gap-1 rounded-full border border-line px-3 text-xs text-ink-muted hover:border-primary hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    : "inline-flex min-h-[44px] items-center gap-1.5 rounded-full border border-line bg-surface px-4 text-sm font-medium text-ink-muted hover:border-primary hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary";
  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={add}
        disabled={added}
        className={`${cls} ${added ? "border-suitable/40 bg-suitable-bg text-suitable" : ""}`}
      >
        {added ? "✓ 已在清單" : "+ 買餸清單"}
      </button>
      <span aria-live="polite" className="text-xs text-ink-muted">
        {msg}
      </span>
    </span>
  );
}
