import type { Rating } from "@/lib/api";

export interface RatingMeta {
  rating: Rating;
  label: string;
  /** triple-expression: color + icon + text (RATING_CRITERIA §2) */
  icon: "check" | "alert" | "stop" | "unknown";
  /** tailwind classes for the badge */
  text: string;
  bg: string;
  ring: string;
  description: string;
}

export const RATING_META: Record<Rating, RatingMeta> = {
  suitable: {
    rating: "suitable",
    label: "一般適合",
    icon: "check",
    text: "text-suitable",
    bg: "bg-suitable-bg",
    ring: "ring-suitable/30",
    description: "非九大過敏原，無已知與濕疹明顯相關的高致敏證據；可作日常食材。",
  },
  caution: {
    rating: "caution",
    label: "因人而異",
    icon: "alert",
    text: "text-caution",
    bg: "bg-caution-bg",
    ring: "ring-caution/30",
    description: "可能為常見過敏原或與組織胺等因素有關；已確診過敏者應避免。",
  },
  trigger: {
    rating: "trigger",
    label: "常見誘發",
    icon: "stop",
    text: "text-trigger",
    bg: "bg-trigger-bg",
    ring: "ring-trigger/30",
    description: "有權威來源指出與濕疹發作有較強關聯（針對已確診過敏人士）。",
  },
  unrated: {
    rating: "unrated",
    label: "資料不足",
    icon: "unknown",
    text: "text-ink-muted",
    bg: "bg-surface-alt",
    ring: "ring-line",
    description: "尚無足夠資料評級；本站不下結論，僅供參考營養資料。",
  },
};

export function ratingMeta(rating: string | null | undefined): RatingMeta {
  return (rating && RATING_META[rating as Rating]) || RATING_META.unrated;
}
