/**
 * Recent ingredient-search history stored in localStorage.
 * Pure helpers are unit tested; pushRecentSearch is the client-side writer.
 */

import { readJson, RECENT_KEY, writeJson } from "@/lib/storage";

export const MAX_RECENT = 8;

/** Keep only usable strings, trim, dedupe (first wins), cap the list. */
export function normalizeRecent(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of v) {
    if (typeof x !== "string") continue;
    const q = x.trim();
    if (!q || seen.has(q)) continue;
    seen.add(q);
    out.push(q);
    if (out.length >= MAX_RECENT) break;
  }
  return out;
}

/** Prepend q (trimmed) to the history; existing entry moves to the front. */
export function recordRecent(list: unknown, q: string): string[] {
  const t = q.trim();
  if (!t) return normalizeRecent(list);
  return normalizeRecent([t, ...(Array.isArray(list) ? list : [])]);
}

/** Record a search from anywhere in the app (no React hook needed). */
export function pushRecentSearch(q: string): void {
  if (typeof window === "undefined") return;
  const next = recordRecent(readJson(RECENT_KEY, []), q);
  if (writeJson(RECENT_KEY, next)) {
    // same-tab subscribers don't get a `storage` event — force refresh
    window.dispatchEvent(new StorageEvent("storage", { key: RECENT_KEY }));
  }
}
