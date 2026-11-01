import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SHOPPING_KEY } from "@/lib/storage";
import ShoppingListView from "./ShoppingListView";

describe("ShoppingListView", () => {
  afterEach(() => cleanup());

  it("renders stored items", () => {
    localStorage.setItem(
      SHOPPING_KEY,
      JSON.stringify([
        {
          id: "ing:1",
          label: "雞蛋",
          ingredientId: 1,
          allergenIds: [1],
          checked: false,
          freeText: false,
        },
      ])
    );
    render(<ShoppingListView />);
    expect(screen.getByText("雞蛋")).toBeTruthy();
  });

  it("does not crash on stored items missing allergenIds (old/corrupt)", () => {
    localStorage.setItem(
      SHOPPING_KEY,
      JSON.stringify([
        { id: "ing:2", label: "牛奶", checked: false, freeText: false },
      ])
    );
    render(<ShoppingListView />);
    expect(screen.getByText("牛奶")).toBeTruthy();
  });
});
