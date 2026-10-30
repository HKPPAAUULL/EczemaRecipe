import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import IngredientCard from "@/components/IngredientCard";
import Pagination from "@/components/Pagination";
import WarningBanner from "@/components/WarningBanner";
import {
  ApiError,
  getCategoryIngredients,
  type CategoryIngredientsResponse,
  type Rating,
} from "@/lib/api";

const PAGE_SIZE = 20;
const RATING_FILTERS: { value: Rating | ""; label: string }[] = [
  { value: "", label: "全部" },
  { value: "suitable", label: "一般適合" },
  { value: "caution", label: "因人而異" },
  { value: "trigger", label: "常見誘發" },
  { value: "unrated", label: "資料不足" },
];

function parseId(id: string): number | null {
  const n = Number(id);
  return Number.isInteger(n) && n > 0 ? n : null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const cid = parseId(id);
  if (cid === null) return { title: "食材庫" };
  try {
    const data = await getCategoryIngredients(cid, { limit: 1 });
    return { title: `${data.category.name_zh} — 食材庫` };
  } catch {
    return { title: "食材庫" };
  }
}

function categoryHref(id: number, rating: string, offset = 0) {
  const p = new URLSearchParams();
  if (rating) p.set("rating", rating);
  p.set("limit", String(PAGE_SIZE));
  if (offset > 0) p.set("offset", String(offset));
  const qs = p.toString();
  return `/categories/${id}${qs ? `?${qs}` : ""}`;
}

function CategoryBody({
  cid,
  rating,
  data,
}: {
  cid: number;
  rating: string;
  data: CategoryIngredientsResponse;
}) {
  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/categories"
          className="text-sm text-ink-muted hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          ← 所有分類
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-ink">
          {data.category.name_zh}
        </h1>
      </div>

      <nav aria-label="按評級篩選">
        <ul className="flex flex-wrap gap-2">
          {RATING_FILTERS.map((f) => {
            const active = rating === f.value;
            return (
              <li key={f.value || "all"}>
                <Link
                  href={categoryHref(cid, f.value)}
                  aria-current={active ? "true" : undefined}
                  className={`inline-flex min-h-[36px] items-center rounded-full px-3.5 py-1.5 text-sm ring-1 ring-inset transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    active
                      ? "bg-primary font-medium text-white ring-primary"
                      : "bg-surface text-ink ring-line hover:bg-surface-alt"
                  }`}
                >
                  {f.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {data.items.length ? (
        <ul className="grid gap-3 md:grid-cols-2">
          {data.items.map((item) => (
            <IngredientCard key={item.id} item={item} />
          ))}
        </ul>
      ) : (
        <p className="rounded-xl bg-surface-alt px-4 py-6 text-center text-ink-muted">
          此分類暫無符合篩選條件的食材。
        </p>
      )}

      <Pagination
        total={data.total}
        limit={data.limit}
        offset={data.offset}
        makeHref={(o) => categoryHref(cid, rating, o)}
      />
    </div>
  );
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ rating?: string; offset?: string }>;
}) {
  const { id } = await params;
  const { rating = "", offset = "0" } = await searchParams;
  const cid = parseId(id);
  if (cid === null) notFound();
  if (rating && !RATING_FILTERS.some((f) => f.value === rating)) notFound();
  const offsetNum = Math.max(0, Number.parseInt(offset, 10) || 0);

  let data: CategoryIngredientsResponse;
  try {
    data = await getCategoryIngredients(cid, {
      rating: rating || undefined,
      limit: PAGE_SIZE,
      offset: offsetNum,
    });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 404) notFound();
      return (
        <WarningBanner title="暫時無法載入分類資料">
          {err.message}，請稍後再試。
        </WarningBanner>
      );
    }
    throw err;
  }
  return <CategoryBody cid={cid} rating={rating} data={data} />;
}
