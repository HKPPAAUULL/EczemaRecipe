import type { Metadata } from "next";
import ShoppingListView from "@/components/ShoppingListView";

export const metadata: Metadata = {
  title: "買餸清單",
  description: "你的買餸清單（只儲存於瀏覽器，可複製或列印）。",
};

export default function ShoppingPage() {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-ink">買餸清單</h1>
      <ShoppingListView />
    </div>
  );
}
