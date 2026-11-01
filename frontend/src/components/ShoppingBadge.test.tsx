import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SHOPPING_KEY } from "@/lib/storage";
import ShoppingBadge from "./ShoppingBadge";

const item = (id: string, checked: boolean) => ({
  id,
  label: id,
  allergenIds: [],
  checked,
  freeText: false,
});

describe("ShoppingBadge", () => {
  afterEach(() => cleanup());

  it("shows nothing when the list is empty", () => {
    const { container } = render(<ShoppingBadge />);
    expect(container.firstChild).toBeNull();
  });

  it("counts unchecked items only", () => {
    localStorage.setItem(
      SHOPPING_KEY,
      JSON.stringify([item("a", false), item("b", true), item("c", false)])
    );
    render(<ShoppingBadge />);
    const badge = screen.getByLabelText("買餸清單有 2 項未買");
    expect(badge.textContent).toBe("2");
  });

  it("does not crash on corrupt stored data", () => {
    localStorage.setItem(SHOPPING_KEY, '"not-an-array"');
    const { container } = render(<ShoppingBadge />);
    expect(container.firstChild).toBeNull();
  });
});
