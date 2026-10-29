# Google Stitch 提示詞草稿

使用方式：先貼「0. 全域設計規範」建立專案風格，再逐頁貼各頁提示詞；每頁分別生成 Mobile 與 Desktop 版本。提示詞以英文撰寫（Stitch 對英文效果較佳），介面文字要求使用繁體中文。

## 0. 全域設計規範（先貼這段）

```
Design a responsive web app called "濕疹食光" (Eczema Kitchen), a one-stop food and recipe guide for people with eczema in Hong Kong and Taiwan. All UI text must be in Traditional Chinese (繁體中文), using the Noto Sans TC font.

Style: calm, gentle, low-stimulation, trustworthy and health-oriented. Soft sage green primary (#6B9080), warm off-white background (#F8F5EF), soft charcoal text (#2F3A35), rounded corners (16px cards, pill-shaped chips), generous whitespace, subtle soft shadows, friendly simple line icons. Avoid harsh reds and clutter.

Food suitability rating system, always shown with color + icon + text (never color alone):
- 🟢 Green "一般適合" (check-circle icon)
- 🟡 Amber "因人而異" (alert-circle icon)
- 🔴 Soft red "常見誘發" (warning-triangle icon)

Allergen tags are small outlined pills (e.g. 蛋, 奶, 花生, 堅果, 大豆, 小麥, 魚, 甲殼類, 芝麻).

Layout: mobile-first. Mobile = single column, bottom navigation bar with 4 tabs (首頁, 查食材, 配食譜, 食材庫), tap targets at least 44px. Desktop = top navigation bar, multi-column grid, max content width 1200px.

Every page has a subtle footer disclaimer: "本站資訊僅供參考，不能取代醫生或營養師意見。"

Components to keep consistent: rating badge, ingredient chip (selectable, with × to remove), recipe card, allergen tag, nutrient table, warning banner, search bar.
```

## 1. 首頁

```
Home page. Hero section with the title "濕疹人士的一站式食材與食譜指南" and a large search bar with placeholder "搜尋食材，例如：雞蛋、三文魚、西蘭花". Below, three large action cards with icons: (1) "查食材 — 這種食材適合我嗎？" (2) "配食譜 — 用手上食材煮一餐" (3) "食材庫 — 按類別買餸參考". Then a "常見食材快速查詢" row of ingredient chips each with a small rating dot. Include a short friendly disclaimer card at the bottom. Provide both mobile and desktop versions.
```

## 2. 食材查詢結果與詳情頁

```
Ingredient detail page for "雞蛋" (egg). Top: ingredient name, small illustration placeholder, a large rating badge (🟡 因人而異). Section "為什麼？": 2-3 short bullet reasons (e.g. 常見食物過敏原之一; 部分兒童濕疹與蛋過敏相關; 如已確認無過敏可適量食用). Section "致敏原標籤": allergen tag pills. Section "營養成分 (每100克)": clean nutrient table plus a simple horizontal bar visualization for protein, fat, carbohydrate, and key nutrients (維他命D, 鋅, Omega-3). Section "參考資料": list of 2-3 source links with year. Section "相關建議食材": horizontal scroll of alternative ingredient cards with ratings. Sticky "加入買餸清單" button. Mobile and desktop versions (desktop: two-column, info left, nutrition right).
```

## 3. 食譜配對頁

```
Recipe matching page "用手上食材配食譜". Top: multi-select ingredient picker — a search input that adds ingredient chips (selected chips shown in a wrapping row, each with × to remove, and a small rating dot). Below: an expandable "我的忌口" filter section with allergen checkboxes (蛋, 奶, 花生, 堅果, 大豆, 小麥, 魚, 甲殼類, 芝麻). A prominent WarningBanner at the top of results when selected ingredients contain common eczema triggers: "⚠ 你選擇的「雞蛋」是常見濕疹誘發食材，請按個人情況留意。" Results: grid of recipe cards, each with image placeholder, title, cooking time, match percentage bar ("已有 4/5 項食材"), missing ingredients list, allergen tags, and an "eczema-friendly" leaf score. Mobile: single column cards. Desktop: 3-column grid with filter sidebar on the left.
```

## 4. 食材分類庫

```
Food category library page "食材庫" for grocery shopping. Top: horizontal scrollable category tabs with icons: 肉類, 海鮮, 蔬菜, 水果, 穀物主食, 蛋奶, 豆類豆製品, 調味料. Filter row: rating filter chips (全部 / 🟢 適合 / 🟡 因人而異 / 🔴 常見誘發) and a search box. Content: grid of ingredient tiles (small image placeholder, name, rating badge, a "+" button to add to shopping list). Floating shopping list button with item count badge. Mobile: 2-column grid; desktop: 5-column grid with a left category sidebar.
```

## 5. 食譜詳情頁

```
Recipe detail page. Title, hero image placeholder, meta row (烹飪時間, 份量, 難度), eczema-friendly score with leaf icons. Ingredients list where any common allergen ingredient is highlighted with a soft amber background and an allergen tag. A WarningBanner summarizing allergens in this recipe. Short description summary and a prominent "查看完整食譜 (原網站)" button linking to the source site, with source name and credit. Section "營養概覽". Section "可替代食材建議". Mobile single column; desktop two columns (ingredients left, details right).
```

## 6. 買餸清單頁

```
Shopping list page "買餸清單". Items grouped by food category with checkboxes, each item showing name and rating badge; swipe or tap to remove. Items rated 🔴 show a small caution note. Buttons: "複製清單" and "清空". Empty state with a friendly illustration and a link to 食材庫. Mobile and desktop versions.
```

## 7. 關於／資料來源／免責頁

```
About and disclaimer page. Sections: 網站簡介, 評級說明 (explain the three rating levels with badges), 資料來源 (list of data sources: USDA, 香港食安中心, 台灣食品營養成分資料庫, PubMed, recipe sites with credit), 免責聲明, 聯絡我們. Calm text-focused layout with comfortable line length. Mobile and desktop versions.
```

## 迭代與匯出提示

- 生成後可追加：`Make it feel warmer and more premium`、`Increase contrast for accessibility`、`Show the empty state / loading state / no results state`。
- 滿意後匯出 HTML/CSS 或 Figma，並抽取：顏色、字體、圓角、間距，供 `tailwind.config` 使用。
- 設計定稿後更新 `docs/PLAN.md` §9 階段 0 的狀態。
