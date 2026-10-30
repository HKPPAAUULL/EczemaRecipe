import { describe, expect, it } from "vitest";
import { clientIp, createLimiter } from "./rateLimit";

describe("rateLimit", () => {
  it("allows up to the cap then 429s with retry-after", () => {
    let t = 0;
    const l = createLimiter(3, () => t);
    expect(l.check("1.2.3.4").allowed).toBe(true);
    expect(l.check("1.2.3.4").allowed).toBe(true);
    expect(l.check("1.2.3.4").allowed).toBe(true);
    const r = l.check("1.2.3.4");
    expect(r.allowed).toBe(false);
    expect(r.retryAfterSec).toBeGreaterThan(0);
    expect(l.check("5.6.7.8").allowed).toBe(true); // other ip unaffected
    t += 61_000;
    expect(l.check("1.2.3.4").allowed).toBe(true); // window resets
  });

  it("clientIp prefers cf then xff then fallback", () => {
    const mk = (h: Record<string, string>) =>
      new Request("http://x", { headers: h });
    expect(clientIp(mk({ "cf-connecting-ip": "9.9.9.9" }))).toBe("9.9.9.9");
    expect(clientIp(mk({ "x-forwarded-for": "1.1.1.1, 2.2.2.2" }))).toBe("1.1.1.1");
    expect(clientIp(mk({}))).toBe("unknown");
  });
});
