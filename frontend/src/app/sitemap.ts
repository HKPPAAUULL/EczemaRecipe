import type { MetadataRoute } from "next";
import { getCategories, getCategoryIngredients } from "@/lib/api";

const SITE_URL = (
  process.env.SITE_URL ?? "http://localhost:3000"
).replace(/\/+$/, "");

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages = ["", "/ingredients", "/categories", "/recipes",
    "/about", "/privacy"].map((p) => ({
    url: `${SITE_URL}${p}`,
    lastModified: new Date(),
  }));
  try {
    const cats = await getCategories();
    const catUrls = cats.map((c) => ({
      url: `${SITE_URL}/categories/${c.id}`,
      lastModified: new Date(),
    }));
    const ingUrls: { url: string; lastModified: Date }[] = [];
    for (const c of cats) {
      let offset = 0;
      for (;;) {
        const page = await getCategoryIngredients(c.id, { limit: 100, offset });
        for (const it of page.items) {
          ingUrls.push({
            url: `${SITE_URL}/ingredients/${it.id}`,
            lastModified: new Date(),
          });
        }
        offset += page.items.length;
        if (offset >= page.total || page.items.length === 0) break;
      }
    }
    return [...staticPages, ...catUrls, ...ingUrls];
  } catch {
    return staticPages; // backend down → static part only
  }
}
