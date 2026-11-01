import { permanentRedirect } from "next/navigation";
import { buildSearchHref } from "@/lib/navigation";

export default async function IngredientsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();
  permanentRedirect(query ? buildSearchHref(query) : "/categories");
}
