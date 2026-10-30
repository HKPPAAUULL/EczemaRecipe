"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="py-20 text-center">
      <h1 className="text-xl font-semibold text-ink">出了點問題</h1>
      <p className="mt-2 text-sm text-ink-muted">
        頁面暫時無法顯示，請稍後再試。
      </p>
      <button
        onClick={reset}
        className="mt-6 rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        重試
      </button>
    </div>
  );
}
