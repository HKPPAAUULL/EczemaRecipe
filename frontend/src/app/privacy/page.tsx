import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "私隱政策",
  description: "不設帳戶、不用追蹤 Cookie；忌口與買餸清單只存於你的瀏覽器。",
};

export default function PrivacyPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-ink">私隱政策</h1>
      <section className="space-y-3 text-sm leading-relaxed text-ink-muted">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>本站不設帳戶，不收集姓名、電郵或登入資料；不使用追蹤或分析 Cookie；沒有第三方廣告。</li>
          <li>你的「忌口」與「買餸清單」只儲存於你的瀏覽器 localStorage，不會上傳到伺服器。</li>
          <li>搜尋與食譜配對時，瀏覽器會把食材 id 與忌口過敏原 id 送到本站伺服器處理；這些數字不含個人識別資料。</li>
          <li>伺服器與 Cloudflare（如啟用）記錄標準存取日誌（IP、時間、請求路徑）作維運與防濫用。</li>
          <li>字體由本站自行提供（Next.js 自託管）。</li>
          <li>清除資料：「我的忌口」按「全部清除」；「買餸清單」按「清空」；或清除瀏覽器的本站資料。</li>
        </ul>
        <p>聯絡方式：（待站長填寫）</p>
        <p>另見 <Link href="/about" className="font-medium text-primary hover:underline">關於本站與免責聲明</Link>。</p>
      </section>
    </div>
  );
}
