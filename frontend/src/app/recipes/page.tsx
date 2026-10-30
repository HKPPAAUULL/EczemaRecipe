import type { Metadata } from "next";
import RecipesClient from "@/components/RecipesClient";
import WarningBanner from "@/components/WarningBanner";
import { ApiError, getAllergens } from "@/lib/api";

export const metadata: Metadata = {
  title: "食譜配對",
  description: "用你手上的食材配對食譜，按忌口自動排除並標示致敏原。",
};

export default async function RecipesPage() {
  let allergenNames: Record<number, string> = {};
  try {
    const allergens = await getAllergens();
    allergenNames = Object.fromEntries(
      allergens.map((a) => [a.id, a.name_zh])
    );
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <div className="space-y-5">
          <h1 className="text-2xl font-bold text-ink">食譜配對</h1>
          <WarningBanner title="暫時無法載入資料">
            {err.message}，請稍後再試。
          </WarningBanner>
        </div>
      );
    }
    throw err;
  }
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">食譜配對</h1>
      <p className="text-sm text-ink-muted">
        加入你手上的食材，我們會配對食譜並按你的
        <a
          href="/settings"
          className="mx-1 text-primary hover:underline"
        >
          忌口
        </a>
        自動排除；所有致敏標示來自資料庫。
      </p>
      <RecipesClient allergenNames={allergenNames} />
    </div>
  );
}
