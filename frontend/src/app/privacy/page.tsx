import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "私隱政策",
  description:
    "濕疹食堂不設帳戶、不用追蹤 Cookie；忌口、買餸清單與查詢記錄只存於你的瀏覽器。",
};

const UPDATED = "2026 年 11 月 1 日";

const LOCAL_DATA = [
  {
    key: "ek:v1:allergen-exclusions",
    data: "已選擇的忌口致敏原編號",
    use: "食譜配對時自動排除相關食譜",
  },
  {
    key: "ek:v1:recipe-selection",
    data: "食譜配對頁已選的食材編號",
    use: "保留你上一次配對的選擇",
  },
  {
    key: "ek:v1:shopping-list",
    data: "買餸清單項目（名稱、分類、勾選狀態、致敏原快照）",
    use: "顯示與管理你的清單",
  },
  {
    key: "ek:v1:recent-searches",
    data: "最近搜尋過的食材關鍵字（最多 8 條）",
    use: "首頁「最近查詢」快速捷徑",
  },
  {
    key: "ek:v1:voter",
    data: "隨機產生的匿名投票識別碼",
    use: "防止重複投票（見第 4 節）",
  },
];

const h2 = "mt-8 text-lg font-semibold text-ink";
const p = "mt-3 text-sm leading-relaxed text-ink-muted";

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-ink">私隱政策</h1>
      <p className="mt-2 text-sm text-ink-muted">最後更新：{UPDATED}</p>

      <section>
        <h2 className={h2}>1. 概述</h2>
        <p className={p}>
          濕疹食堂（下稱「本站」）是為濕疹人士而設的食材與食譜參考工具。本站的設計原則是盡量不收集個人資料：不設帳戶、不要求登入、不使用追蹤或分析
          Cookie、沒有第三方廣告。你在本站使用的絕大部分個人化功能，資料只會儲存於你自己的瀏覽器。
        </p>
      </section>

      <section>
        <h2 className={h2}>2. 我們不收集的資料</h2>
        <ul className={`${p} list-disc space-y-1.5 pl-5`}>
          <li>姓名、電郵地址、電話號碼或任何登入資料（本站不設帳戶系統）</li>
          <li>健康或醫療資料（本站不會要求你申報病情）</li>
          <li>精確位置資料（GPS、地址）</li>
          <li>用於廣告或跨站追蹤的識別資料</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>3. 儲存於你瀏覽器的資料</h2>
        <p className={p}>
          以下資料經瀏覽器的 localStorage
          儲存於你的裝置上，<strong className="text-ink">不會上傳到本站伺服器</strong>：
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line text-ink">
                <th className="py-2 pr-4 font-semibold">儲存項目</th>
                <th className="py-2 pr-4 font-semibold">內容</th>
                <th className="py-2 font-semibold">用途</th>
              </tr>
            </thead>
            <tbody className="text-ink-muted">
              {LOCAL_DATA.map((r) => (
                <tr key={r.key} className="border-b border-line align-top">
                  <td className="py-2 pr-4 font-mono text-xs">{r.key}</td>
                  <td className="py-2 pr-4">{r.data}</td>
                  <td className="py-2">{r.use}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className={p}>
          你可以隨時刪除這些資料：「我的忌口」頁的「全部清除」、「買餸清單」頁的「清空」、首頁「最近查詢」旁的「清除」，或直接清除瀏覽器中本站的儲存資料。
        </p>
      </section>

      <section>
        <h2 className={h2}>4. 傳送至伺服器的資料</h2>
        <p className={p}>
          使用以下功能時，瀏覽器會把必要的資料傳送到本站伺服器處理：
        </p>
        <ul className={`${p} list-disc space-y-1.5 pl-5`}>
          <li>
            <strong className="text-ink">搜尋與食譜配對</strong>：
            你所選的食材編號與忌口致敏原編號。這些只是數字編號，不含個人識別資料，伺服器處理後不會長期保存。
          </li>
          <li>
            <strong className="text-ink">食譜讚好／不讚好</strong>：
            由你的瀏覽器隨機產生的匿名投票識別碼（不含個人資料）、食譜編號與投票選項，會儲存於伺服器資料庫，用途僅為防止重複投票及統計食譜受歡迎程度。
          </li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>5. Cookie 與第三方服務</h2>
        <p className={p}>
          本站不使用追蹤 Cookie、分析工具（如 Google
          Analytics）或第三方廣告。字體由本站自行託管，不會向字體供應商發出請求。
        </p>
      </section>

      <section>
        <h2 className={h2}>6. 伺服器日誌</h2>
        <p className={p}>
          與所有網站一樣，本站伺服器及（如已啟用的）Cloudflare Tunnel
          會記錄標準存取日誌，包括 IP 地址、存取時間、請求路徑與瀏覽器識別字串，僅用作系統維運、除錯及防止濫用，不會用於識別個人身份或出售予第三方。
        </p>
      </section>

      <section>
        <h2 className={h2}>7. 政策的變更</h2>
        <p className={p}>
          如本政策有任何修改，會更新本頁並註明最後更新日期。建議你不時查閱本頁以了解最新版本。
        </p>
      </section>

      <section>
        <h2 className={h2}>8. 相關文件</h2>
        <p className={p}>
          本站提供的評級與建議僅供參考，並非醫療意見；詳情請參閱
          <Link
            href="/about"
            className="mx-1 font-medium text-primary underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            關於本站與免責聲明
          </Link>
          。
        </p>
      </section>
    </div>
  );
}
