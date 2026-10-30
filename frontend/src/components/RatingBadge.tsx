import { ratingMeta } from "@/lib/rating";

const ICONS = {
  check: (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden="true">
      <path
        fill="currentColor"
        d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Zm3.3 5.3-4 4a.8.8 0 0 1-1.1 0l-1.7-1.7a.8.8 0 1 1 1-1l1.2 1.2 3.4-3.5a.8.8 0 0 1 1.2 1Z"
      />
    </svg>
  ),
  alert: (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden="true">
      <path
        fill="currentColor"
        d="M8.9 1.6 15 12.8A1 1 0 0 1 14.1 14H1.9A1 1 0 0 1 1 12.8L7.1 1.6a1 1 0 0 1 1.8 0ZM8 6a.8.8 0 0 0-.8.8v2.7a.8.8 0 0 0 1.6 0V6.8A.8.8 0 0 0 8 6Zm0 5.4a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8Z"
      />
    </svg>
  ),
  stop: (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden="true">
      <path
        fill="currentColor"
        d="M5.2 1h5.6L15 5.2v5.6L10.8 15H5.2L1 10.8V5.2L5.2 1Zm5.1 6.2a.8.8 0 0 0-1.1-1.1L8 7.3 6.9 6.1a.8.8 0 1 0-1.1 1.1L6.9 8.4l-1.1 1.1a.8.8 0 1 0 1.1 1.1L8 9.5l1.2 1.1a.8.8 0 1 0 1.1-1.1L9.2 8.4l1.1-1.2Z"
      />
    </svg>
  ),
  unknown: (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden="true">
      <path
        fill="currentColor"
        d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Zm0 4a2 2 0 0 1 .8 3.8c-.5.2-.8.5-.8 1v.4a.8.8 0 0 1-1.6 0v-.4A2.4 2.4 0 0 1 7.6 7.4a.5.5 0 1 0-.7-.7.8.8 0 1 1-1.3-.8A2 2 0 0 1 8 5Zm0 6.8a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8Z"
      />
    </svg>
  ),
};

export default function RatingBadge({
  rating,
  label,
  large = false,
}: {
  rating: string;
  label?: string;
  large?: boolean;
}) {
  const meta = ratingMeta(rating);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset ${meta.bg} ${meta.text} ${meta.ring} ${
        large ? "px-4 py-1.5 text-base" : "px-3 py-1 text-sm"
      }`}
    >
      {ICONS[meta.icon]}
      {label ?? meta.label}
    </span>
  );
}
