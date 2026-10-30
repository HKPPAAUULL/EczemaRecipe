/**
 * Shopping list model + pure reducer (no React) — unit tested.
 * Item = ingredient reference (with allergen snapshot) or free text
 * (e.g. a recipe's missing/unmatched ingredient).
 */

export interface ShoppingItem {
  id: string; // "ing:<id>" or "txt:<normalized-name>"
  label: string;
  category?: string;
  ingredientId?: number;
  allergenIds: number[];
  checked: boolean;
  freeText: boolean;
}

export const MAX_ITEMS = 200;
export const MAX_LABEL = 80;

export function makeItem(input: {
  ingredientId?: number;
  name: string;
  category?: string;
  allergenIds?: number[];
}): ShoppingItem | null {
  const name = input.name.trim().slice(0, MAX_LABEL);
  if (!name) return null;
  return {
    id:
      input.ingredientId != null
        ? `ing:${input.ingredientId}`
        : `txt:${name.toLowerCase()}`,
    label: name,
    category: input.category,
    ingredientId: input.ingredientId,
    allergenIds: input.allergenIds ?? [],
    checked: false,
    freeText: input.ingredientId == null,
  };
}

export function addItem(
  list: ShoppingItem[],
  item: ShoppingItem | null
): ShoppingItem[] {
  if (!item || list.some((i) => i.id === item.id)) return list;
  if (list.length >= MAX_ITEMS) return list;
  return [...list, item];
}

export function addItems(
  list: ShoppingItem[],
  items: (ShoppingItem | null)[]
): ShoppingItem[] {
  return items.reduce(addItem, list);
}

export function toggleItem(
  list: ShoppingItem[],
  id: string
): ShoppingItem[] {
  return list.map((i) => (i.id === id ? { ...i, checked: !i.checked } : i));
}

export function removeItem(list: ShoppingItem[], id: string): ShoppingItem[] {
  return list.filter((i) => i.id !== id);
}

export function clearChecked(list: ShoppingItem[]): ShoppingItem[] {
  return list.filter((i) => !i.checked);
}

export function allergenHitIds(
  item: ShoppingItem,
  exclusions: number[]
): number[] {
  return item.allergenIds.filter((id) => exclusions.includes(id));
}

export function toPlainText(list: ShoppingItem[]): string {
  return list
    .map((i) => `${i.checked ? "[x]" : "[ ]"} ${i.label}`)
    .join("\n");
}
