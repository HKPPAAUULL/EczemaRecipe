import { clientIp, createLimiter } from "@/lib/rateLimit";
import {
  BODY_LIMIT,
  isValidVoterKey,
  validateVoteBody,
} from "@/lib/bff";

const API_BASE = (
  process.env.API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const TIMEOUT_MS = 8000;
const limiter = createLimiter(60);

function recipeId(raw: string): number | null {
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : null;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const lim = limiter.check(clientIp(request));
  if (!lim.allowed) {
    return Response.json(
      { error: "請求太頻密，請稍後再試" },
      { status: 429, headers: { "Retry-After": String(lim.retryAfterSec) } }
    );
  }
  const { id } = await params;
  const rid = recipeId(id);
  if (rid === null) {
    return Response.json({ error: "食譜編號不正確" }, { status: 400 });
  }
  const voter = new URL(request.url).searchParams.get("voter") ?? "";
  const qs = isValidVoterKey(voter)
    ? `?voter=${encodeURIComponent(voter)}`
    : "";
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/recipes/${rid}/votes${qs}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: "資料伺服器暫時無法連線" }, { status: 502 });
  }
  const body = await res.json().catch(() => null);
  if (!res.ok || body === null) {
    return Response.json(
      { error: "資料伺服器回應錯誤" },
      { status: res.status === 404 ? 404 : 502 }
    );
  }
  return Response.json(body);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const lim = limiter.check(clientIp(request));
  if (!lim.allowed) {
    return Response.json(
      { error: "請求太頻密，請稍後再試" },
      { status: 429, headers: { "Retry-After": String(lim.retryAfterSec) } }
    );
  }
  const { id } = await params;
  const rid = recipeId(id);
  if (rid === null) {
    return Response.json({ error: "食譜編號不正確" }, { status: 400 });
  }
  const len = Number(request.headers.get("content-length") ?? 0);
  if (len > BODY_LIMIT) {
    return Response.json({ error: "請求內容過大" }, { status: 413 });
  }
  let raw: unknown;
  try {
    const text = await request.text();
    if (text.length > BODY_LIMIT * 2) {
      return Response.json({ error: "請求內容過大" }, { status: 413 });
    }
    raw = JSON.parse(text);
  } catch {
    return Response.json({ error: "body 須為 JSON" }, { status: 400 });
  }
  const v = validateVoteBody(raw);
  if (!v.ok) return Response.json({ error: v.error }, { status: v.status });
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/recipes/${rid}/votes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.value),
      signal: AbortSignal.timeout(TIMEOUT_MS),
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: "資料伺服器暫時無法連線" }, { status: 502 });
  }
  const body = await res.json().catch(() => null);
  if (!res.ok || body === null) {
    return Response.json(
      { error: "資料伺服器回應錯誤" },
      { status: res.status === 404 ? 404 : 502 }
    );
  }
  return Response.json(body);
}
