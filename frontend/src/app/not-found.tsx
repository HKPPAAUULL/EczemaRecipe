import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20 text-center">
      <p className="text-5xl font-bold text-ink-muted">404</p>
      <h1 className="mt-3 text-xl font-semibold text-ink">找不到此頁面</h1>
      <p className="mt-2 text-sm text-ink-muted">
        你查找的頁面或食材不存在，可能已被移除或網址有誤。
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        返回首頁
      </Link>
    </div>
  );
}
