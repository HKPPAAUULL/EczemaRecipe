import type { ReactNode } from "react";

export default function WarningBanner({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-xl bg-caution-bg px-4 py-3 ring-1 ring-inset ring-caution/40"
    >
      <svg
        viewBox="0 0 20 20"
        className="mt-0.5 h-5 w-5 shrink-0 text-caution"
        aria-hidden="true"
      >
        <path
          fill="currentColor"
          d="M10 1a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm.9 5.1a.95.95 0 0 0-1.8 0l-.3 4.7a1.2 1.2 0 0 0 2.4 0l-.3-4.7ZM10 13.4a1.1 1.1 0 1 0 0 2.2 1.1 1.1 0 0 0 0-2.2Z"
        />
      </svg>
      <div>
        <p className="font-medium text-caution">{title}</p>
        {children ? <div className="mt-1 text-sm text-ink">{children}</div> : null}
      </div>
    </div>
  );
}
