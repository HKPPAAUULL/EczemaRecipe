import type { Metadata } from "next";
import Link from "next/link";
import { Noto_Sans_TC } from "next/font/google";
import "./globals.css";
import SiteHeader from "@/components/SiteHeader";
import BottomNav from "@/components/BottomNav";
import Disclaimer from "@/components/Disclaimer";

const notoSansTC = Noto_Sans_TC({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-noto-sans-tc",
  display: "swap",
});

const SITE_URL = (
  process.env.SITE_URL ?? "http://localhost:3000"
).replace(/\/+$/, "");

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "濕疹食堂 Eczema Kitchen",
    template: "%s | 濕疹食堂",
  },
  description:
    "濕疹人士的食材查詢工具：查詢食材適合度評級、致敏原與營養成分，並提供分類食材庫。資訊僅供參考，不作診斷。",
  openGraph: {
    siteName: "濕疹食堂 Eczema Kitchen",
    locale: "zh_HK",
    type: "website",
  },
  twitter: { card: "summary" },
  alternates: { canonical: "/" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant" className={notoSansTC.variable}>
      <body className="flex min-h-dvh flex-col antialiased">
        <SiteHeader />
        <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 pt-6 md:px-6">
          {children}
        </main>
        <footer className="mx-auto w-full max-w-[1200px] px-4 pb-24 pt-8 md:px-6 md:pb-10">
          <Disclaimer />
          <p className="mt-3 text-xs text-ink-muted">
            濕疹食堂 Eczema Kitchen · 專為濕疹人士設計的食材參考工具 ·{" "}
            <Link href="/privacy" className="underline-offset-2 hover:underline">私隱政策</Link>
          </p>
        </footer>
        <BottomNav />
      </body>
    </html>
  );
}
