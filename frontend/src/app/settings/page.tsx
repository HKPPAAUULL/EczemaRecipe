import type { Metadata } from "next";
import AllergenExclusionEditor from "@/components/AllergenExclusionEditor";
import WarningBanner from "@/components/WarningBanner";
import { ApiError, getAllergens } from "@/lib/api";

export const metadata: Metadata = {
  title: "我的忌口",
  description: "設定你的致敏原忌口，食譜配對時自動排除（只存於你的瀏覽器）。",
};

export default async function SettingsPage() {
  let allergens;
  try {
    allergens = await getAllergens();
  } catch (err) {
    if (err instanceof ApiError) {
      return (
        <div className="space-y-5">
          <h1 className="text-2xl font-bold text-ink">我的忌口</h1>
          <WarningBanner title="暫時無法載入過敏原清單">
            {err.message}，請稍後再試。
          </WarningBanner>
        </div>
      );
    }
    throw err;
  }
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">我的忌口</h1>
      <AllergenExclusionEditor allergens={allergens} />
    </div>
  );
}
