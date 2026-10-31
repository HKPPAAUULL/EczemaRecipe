/**
 * Shown on the ingredient detail page when eczema_rating === 'unrated':
 * the site does not guess when reliable data is lacking.
 */
export default function InsufficientDataNotice() {
  return (
    <section
      aria-labelledby="insufficient-h"
      className="rounded-2xl bg-surface-alt p-5 ring-1 ring-line"
    >
      <h2 id="insufficient-h" className="text-lg font-semibold text-ink">
        資料不足
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-ink-muted">
        目前尚無足夠可靠資料為此食材評級，本站不作推測；以下僅供參考。
      </p>
    </section>
  );
}
