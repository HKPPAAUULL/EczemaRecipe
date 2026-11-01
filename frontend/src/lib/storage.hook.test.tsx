import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { useLocalStorage } from "./storage";

function Probe({ k }: { k: string }) {
  const [v, setV] = useLocalStorage<number[]>(k, []);
  const [n, setN] = useState(0);
  return (
    <button
      onClick={() => {
        setV([...v, v.length]);
        setN(n + 1); // extra re-render: pre-fix this re-read looped forever
      }}
    >
      {v.length}/{n}
    </button>
  );
}

describe("useLocalStorage", () => {
  afterEach(() => cleanup());
  it("snapshot stays stable across re-renders — no update loop", () => {
    localStorage.setItem("ek:test:snap1", "[1,2]");
    render(<Probe k="ek:test:snap1" />);
    const btn = screen.getByRole("button");
    expect(btn.textContent).toBe("2/0");
    fireEvent.click(btn);
    expect(btn.textContent).toBe("3/1");
    fireEvent.click(btn);
    expect(btn.textContent).toBe("4/2");
    expect(localStorage.getItem("ek:test:snap1")).toBe("[1,2,2,3]");
  });

  it("re-render without writes does not loop on stored data", () => {
    localStorage.setItem("ek:test:snap2", "[9]");
    render(<Probe k="ek:test:snap2" />);
    const btn = screen.getByRole("button");
    expect(btn.textContent).toBe("1/0"); // stored array length, not value
  });
});
