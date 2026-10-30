const SEVERITY_LABEL: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
};

export default function AllergenTag({
  name,
  severity,
}: {
  name: string;
  severity?: string | null;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-caution-bg px-3 py-1 text-sm font-medium text-caution ring-1 ring-inset ring-caution/30">
      <svg viewBox="0 0 16 16" className="h-3 w-3" aria-hidden="true">
        <path
          fill="currentColor"
          d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0Zm.7 4.2a.75.75 0 0 0-1.5 0v4a.75.75 0 0 0 1.5 0v-4ZM8 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z"
        />
      </svg>
      {name}
      {severity && SEVERITY_LABEL[severity] ? (
        <span className="text-xs font-normal">
          （{SEVERITY_LABEL[severity]}）
        </span>
      ) : null}
    </span>
  );
}
