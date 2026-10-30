import type { Metadata } from "next";
import RatingBadge from "@/components/RatingBadge";
import { RATING_META } from "@/lib/rating";

export const metadata: Metadata = {
  title: "關於本站",
  description:
    "濕疹食堂的使用說明、評級準則摘要、資料來源與免責聲明。",
};

const RATING_ORDER = ["suitable", "caution", "trigger", "unrated"] as const;

export default function AboutPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <header>
        <h1 className="text-2xl font-bold text-ink">關於濕疹食堂</h1>
        <p className="mt-2 leading-relaxed text-ink-muted">
          濕疹食堂為濕疹人士提供食材適合度參考：你可以查詢個別食材的評級、
          致敏原與營養成分，或按分類瀏覽食材庫。本站只提供參考資訊，
          不作診斷，亦不建議在未確診食物過敏的情況下盲目戒口。
        </p>
      </header>

      <section aria-labelledby="rating-h" className="space-y-3">
        <h2 id="rating-h" className="text-lg font-semibold text-ink">
          評級說明
        </h2>
        <p className="text-sm leading-relaxed text-ink-muted">
          食材評級共分四級，只反映「一般情況下的參考」；食物與濕疹的關係
          因人而異，評級不代表對所有人都適用。🟡／🔴 評級均附原因與來源；
          🔴 僅保留給有權威來源明確指出與濕疹發作有強關聯的情況。
        </p>
        <ul className="space-y-2">
          {RATING_ORDER.map((r) => (
            <li
              key={r}
              className="flex items-start gap-3 rounded-xl bg-surface p-3 ring-1 ring-line"
            >
              <RatingBadge rating={r} />
              <p className="pt-0.5 text-sm leading-relaxed text-ink-muted">
                {RATING_META[r].description}
              </p>
            </li>
          ))}
        </ul>
        <p className="text-sm text-ink-muted">
          完整準則見專案文件{" "}
          <a
            href="https://github.com/HKPPAAUULL/EczemaRecipe/blob/main/docs/RATING_CRITERIA.md"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            RATING_CRITERIA.md
          </a>
          。評級先以草稿形式建立，經人工審核後才對外發佈。
        </p>
      </section>

      <section aria-labelledby="source-h" className="space-y-3">
        <h2 id="source-h" className="text-lg font-semibold text-ink">
          資料來源與顯名聲明
        </h2>
        <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-ink-muted">
          <li>
            營養成分：
            <a
              href="https://data.gov.tw/dataset/8543"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-primary underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              衛生福利部食品藥物管理署「食品營養成分資料集」
            </a>
            ，依「政府資料開放授權條款-第1版」提供；此開放資料依該條款釋出，
            本站之使用不代表該機關對本站內容之認可或背書。
          </li>
          <li>
            食材評級、致敏原標記與同義詞表：由本站按評級準則整理，
            並經人工審核後發佈。
          </li>
        </ul>
      </section>

      <section aria-labelledby="disclaimer-h" className="space-y-3">
        <h2 id="disclaimer-h" className="text-lg font-semibold text-ink">
          免責聲明
        </h2>
        <div className="rounded-xl bg-surface-alt p-4 text-sm leading-relaxed text-ink-muted">
          <p>
            本站資訊僅供參考，不能取代醫生或營養師意見。濕疹的食物誘因
            因人而異；對沒有確診食物過敏的人，一般不建議盲目戒口，
            戒口可能導致營養不足。如濕疹嚴重、持續或懷疑食物過敏，
            請諮詢醫生或註冊營養師。
          </p>
          <p className="mt-2">
            本站不作診斷、不提供治療建議，亦不保證任何食材對個別人士
            絕對安全；引入新食材時建議一次只嘗試一種並留意身體反應。
          </p>
        </div>
      </section>
    </div>
  );
}
