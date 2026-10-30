import { describe, expect, it } from "vitest";
import {
  addItem,
  addItems,
  allergenHitIds,
  clearChecked,
  makeItem,
  MAX_ITEMS,
  removeItem,
  toPlainText,
  toggleItem,
} from "./shoppingList";

describe("shoppingList reducer", () => {
  const egg = makeItem({
    ingredientId: 116,
    name: "雞蛋",
    allergenIds: [1],
  })!;

  it("adds, dedupes and enforces the cap", () => {
    const list = addItem([], egg);
    expect(list).toHaveLength(1);
    expect(addItem(list, egg)).toHaveLength(1); // dup ignored
    const full = Array.from({ length: MAX_ITEMS }, (_, i) =>
      makeItem({ name: `item${i}` })!
    );
    expect(addItem(full, egg)).toHaveLength(MAX_ITEMS);
    expect(makeItem({ name: "   " })).toBeNull();
  });

  it("toggle / remove / clearChecked", () => {
    let list = addItems([], [egg, makeItem({ name: "秋葵" })]);
    list = toggleItem(list, egg.id);
    expect(list[0].checked).toBe(true);
    expect(clearChecked(list)).toHaveLength(1);
    list = removeItem(list, egg.id);
    expect(list).toHaveLength(1);
  });

  it("allergen intersection + plain text", () => {
    expect(allergenHitIds(egg, [1, 2])).toEqual([1]);
    expect(allergenHitIds(egg, [9])).toEqual([]);
    expect(toPlainText([{ ...egg, checked: true }])).toBe("[x] 雞蛋");
  });
});
