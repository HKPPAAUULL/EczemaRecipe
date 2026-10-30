import type { NutrientItem } from "@/lib/api";

function formatAmount(v: number): string {
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
}

export default function NutrientTable({
  nutrients,
}: {
  nutrients: NutrientItem[];
}) {
  if (!nutrients.length) {
    return (
      <p className="rounded-xl bg-surface-alt px-4 py-3 text-sm text-ink-muted">
        暫無營養資料。
      </p>
    );
  }
  const sources = [...new Set(nutrients.map((n) => n.source).filter(Boolean))];
  return (
    <div className="overflow-hidden rounded-xl ring-1 ring-line">
      <table className="w-full text-sm">
        <caption className="bg-surface-alt px-4 py-2 text-left text-xs text-ink-muted">
          每 100 克含量
          {sources.length ? `（來源：${sources.join("、")}）` : ""}
        </caption>
        <thead>
          <tr className="border-b border-line bg-surface text-left">
            <th scope="col" className="px-4 py-2 font-medium text-ink-muted">
              營養素
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium text-ink-muted">
              含量
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium text-ink-muted">
              單位
            </th>
          </tr>
        </thead>
        <tbody className="bg-surface">
          {nutrients.map((n) => (
            <tr key={`${n.name}-${n.unit}`} className="border-b border-line/60 last:border-0">
              <td className="px-4 py-2">{n.name}</td>
              <td className="px-4 py-2 text-right tabular-nums">
                {formatAmount(n.amount_per_100g)}
              </td>
              <td className="px-4 py-2 text-right text-ink-muted">{n.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
