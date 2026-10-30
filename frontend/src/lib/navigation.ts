export function buildSearchHref(q: string): string {
  return `/ingredients?q=${encodeURIComponent(q.trim())}`;
}

export interface PageWindow {
  page: number;
  pages: number;
  hasPrev: boolean;
  hasNext: boolean;
  prevOffset: number | null;
  nextOffset: number | null;
}

export function pageWindow(
  total: number,
  limit: number,
  offset: number
): PageWindow {
  const safeLimit = Math.max(1, limit);
  const pages = Math.max(1, Math.ceil(total / safeLimit));
  const page = Math.min(pages, Math.floor(offset / safeLimit) + 1);
  const hasPrev = offset > 0;
  const hasNext = offset + safeLimit < total;
  return {
    page,
    pages,
    hasPrev,
    hasNext,
    prevOffset: hasPrev ? Math.max(0, offset - safeLimit) : null,
    nextOffset: hasNext ? offset + safeLimit : null,
  };
}
