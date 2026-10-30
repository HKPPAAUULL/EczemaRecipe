"use client";

import { useState } from "react";
import { SHOPPING_KEY, storageAvailable, useLocalStorage } from "@/lib/storage";
import { addItems, makeItem, type ShoppingItem } from "@/lib/shoppingList";

export default function AddAllToShoppingList({
  items,
}: {
  items: { ingredientId?: number; name: string; allergenIds?: number[] }[];
}) {
  const [list, setList] = useLocalStorage<ShoppingItem[]>(SHOPPING_KEY, []);
  const [msg, setMsg] = useState("");

  function addAll() {
    if (!storageAvailable()) {
      setMsg("瀏覽器不支援本機儲存");
      return;
    }
    const before = list.length;
    const next = addItems(list, items.map(makeItem));
    setList(next);
    setMsg(`已加入 ${next.length - before} 項`);
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={addAll}
        className="inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm text-ink-muted hover:border-primary hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        全部加入買餸清單
      </button>
      <span aria-live="polite" className="text-xs text-ink-muted">{msg}</span>
    </span>
  );
}
