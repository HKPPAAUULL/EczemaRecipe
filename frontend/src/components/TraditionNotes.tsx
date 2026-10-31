import type { TraditionNote } from "@/lib/api";

export const TRADITION_TAG_LABELS: Record<string, string> = {
  fawu: "發物",
  sticky: "黏滯難消化",
  warm_hot: "溫熱",
  cool: "寒涼",
  neutral: "平性",
  other: "其他",
};

const TAG_ORDER = Object.keys(TRADITION_TAG_LABELS);

/**
 * 傳統說法（中醫觀點）card — deliberately neutral styling (bg-surface-alt /
 * ring-line, never the suitable/caution/trigger colours) so it cannot be
 * mistaken for a rating.
 */
export default function TraditionNotes({ notes }: { notes: TraditionNote[] }) {
  if (!notes.length) return null;

  const groups = new Map<string, TraditionNote[]>();
  for (const n of notes) {
    const key = n.tag in TRADITION_TAG_LABELS ? n.tag : "other";
    groups.set(key, [...(groups.get(key) ?? []), n]);
  }
  const ordered = [...groups.entries()].sort(
    ([a], [b]) => TAG_ORDER.indexOf(a) - TAG_ORDER.indexOf(b)
  );

  return (
    <section
      aria-labelledby="tradition-h"
      className="rounded-2xl bg-surface-alt p-5 ring-1 ring-line md:p-6"
    >
      <h2 id="tradition-h" className="text-lg font-semibold text-ink">
        傳統說法（非實證）
      </h2>
      <p className="mt-2 text-xs leading-relaxed text-ink-muted">
        以下為傳統飲食觀點，未必有現代臨床研究支持，不影響本站評級，請勿取代醫生意見。
      </p>
      <div className="mt-4 space-y-4">
        {ordered.map(([tag, items]) => (
          <div key={tag}>
            <span className="inline-block rounded-full bg-surface px-3 py-1 text-xs font-medium text-ink-muted ring-1 ring-line">
              {TRADITION_TAG_LABELS[tag]}
            </span>
            <ul className="mt-2 space-y-2">
              {items.map((t, i) => (
                <li key={i} className="text-sm leading-relaxed text-ink">
                  {t.note}
                  {t.draft ? (
                    <span className="ml-2 inline-block rounded-full bg-surface px-2 py-0.5 text-xs text-ink-muted ring-1 ring-line">
                      待審核
                    </span>
                  ) : null}
                  {t.source_url ? (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 text-xs text-ink-muted underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      {t.source_title ?? "來源"}
                    </a>
                  ) : t.source_title ? (
                    <span className="ml-2 text-xs text-ink-muted">
                      {t.source_title}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
