/**
 * Simple per-IP in-memory rate limiter for BFF routes.
 * Prefers Cf-Connecting-Ip (Cloudflare), then first X-Forwarded-For entry,
 * else a fixed key. Pure + injectable clock for testing.
 */

const WINDOW_MS = 60_000;
const MAX_ENTRIES = 10_000;

export interface Limiter {
  check(ip: string): { allowed: boolean; retryAfterSec: number };
}

export function createLimiter(
  maxPerWindow: number,
  now: () => number = () => Date.now()
): Limiter {
  const hits = new Map<string, number[]>();
  let lastSweep = 0;

  function sweep(t: number) {
    if (t - lastSweep < WINDOW_MS) return;
    lastSweep = t;
    for (const [k, v] of hits) {
      const kept = v.filter((x) => t - x < WINDOW_MS);
      if (kept.length) hits.set(k, kept);
      else hits.delete(k);
    }
    if (hits.size > MAX_ENTRIES) {
      // hard cap: drop oldest keys arbitrarily rather than grow unbounded
      for (const k of hits.keys()) {
        hits.delete(k);
        if (hits.size <= MAX_ENTRIES / 2) break;
      }
    }
  }

  return {
    check(ip: string) {
      const t = now();
      sweep(t);
      const arr = (hits.get(ip) ?? []).filter((x) => t - x < WINDOW_MS);
      if (arr.length >= maxPerWindow) {
        const oldest = arr[0];
        return {
          allowed: false,
          retryAfterSec: Math.max(1, Math.ceil((WINDOW_MS - (t - oldest)) / 1000)),
        };
      }
      arr.push(t);
      hits.set(ip, arr);
      return { allowed: true, retryAfterSec: 0 };
    },
  };
}

export function clientIp(request: Request): string {
  const cf = request.headers.get("cf-connecting-ip");
  if (cf) return cf.trim();
  const xff = request.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return "unknown";
}
