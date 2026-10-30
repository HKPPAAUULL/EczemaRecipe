import { clientIp, createLimiter } from "@/lib/rateLimit";
import { validateSearchQuery } from "@/lib/bff";

const API_BASE = (
  process.env.API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const TIMEOUT_MS = 8000;
const limiter = createLimiter(60);

export async function GET(request: Request) {
  const lim = limiter.check(clientIp(request));
  if (!lim.allowed) {
    return Response.json(
      { error: "請求太頻密，請稍後再試" },
      { status: 429, headers: { "Retry-After": String(lim.retryAfterSec) } }
    );
  }
  const url = new URL(request.url);
  const v = validateSearchQuery(url.searchParams.get("q"));
  if (!v.ok) return Response.json({ error: v.error }, { status: v.status });
  let res: Response;
  try {
    res = await fetch(
      `${API_BASE}/api/ingredients/search?q=${encodeURIComponent(
        v.value as string
      )}&limit=20`,
      { signal: AbortSignal.timeout(TIMEOUT_MS), cache: "no-store" }
    );
  } catch {
    return Response.json({ error: "資料伺服器暫時無法連線" }, { status: 502 });
  }
  const body = await res.json().catch(() => null);
  if (!res.ok || body === null) {
    return Response.json({ error: "資料伺服器回應錯誤" }, { status: 502 });
  }
  return Response.json(body);
}
