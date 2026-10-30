/**
 * localStorage access with versioned keys and defensive reads.
 * - readJson never throws on corrupt data / wrong types / quota errors —
 *   it returns the fallback; `storageAvailable()` reports writability.
 * - Allergen exclusion ids that no longer exist server-side are filtered
 *   out by callers (settings page warns).
 */

"use client";

import { useCallback, useSyncExternalStore } from "react";

export const ALLERGEN_KEY = "ek:v1:allergen-exclusions";
export const SHOPPING_KEY = "ek:v1:shopping-list";

export function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): boolean {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function storageAvailable(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const k = "ek:probe";
    window.localStorage.setItem(k, "1");
    window.localStorage.removeItem(k);
    return true;
  } catch {
    return false;
  }
}

// useSyncExternalStore: SSR snapshot is always `fallback`; after hydration
// the real value streams in, and `storage` events sync across tabs.
function subscribe(key: string) {
  return (notify: () => void) => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || e.key === key) notify();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  };
}

export function useLocalStorage<T>(
  key: string,
  fallback: T
): [T, (v: T) => boolean] {
  const value = useSyncExternalStore(
    subscribe(key),
    () => readJson(key, fallback),
    () => fallback
  );
  const set = useCallback(
    (v: T) => {
      const ok = writeJson(key, v);
      if (ok) {
        // same-tab subscribers don't get a `storage` event — force refresh
        window.dispatchEvent(new StorageEvent("storage", { key }));
      }
      return ok;
    },
    [key]
  );
  return [value, set];
}

export function readAllergenExclusions(): number[] {
  const v = readJson<number[]>(ALLERGEN_KEY, []);
  return Array.isArray(v)
    ? v.filter((x): x is number => Number.isInteger(x) && x > 0)
    : [];
}
