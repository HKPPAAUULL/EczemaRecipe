import { BODY_LIMIT, validateSuggestBody } from "@/lib/bff";

const API_BASE = (
  process.env.API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const TIMEOUT_MS = 8000;

export async function POST(request: Request) {
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
  const v = validateSuggestBody(raw);
  if (!v.ok) return Response.json({ error: v.error }, { status: v.status });
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/recipes/suggest`, {
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
  if (res.status === 422 && body !== null) {
    // forward the semantic error (e.g. invalid_ingredient_ids) untouched
    return Response.json(body, { status: 422 });
  }
  if (!res.ok || body === null) {
    return Response.json({ error: "資料伺服器回應錯誤" }, { status: 502 });
  }
  return Response.json(body);
}
