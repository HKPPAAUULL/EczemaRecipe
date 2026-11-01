import Link from "next/link";
import type { IngredientListItem } from "@/lib/api";
import RatingBadge from "@/components/RatingBadge";
import AllergenTag from "@/components/AllergenTag";
import AddToShoppingListButton from "@/components/AddToShoppingListButton";

const MAX_TAGS = 4;

export default function IngredientCard({
  item,
}: {
  item: IngredientListItem;
}) {
  const shown = item.allergens.slice(0, MAX_TAGS);
  const extra = item.allergens.length - shown.length;
  return (
    <li className="relative list-none rounded-xl bg-surface shadow-card ring-1 ring-line transition-shadow hover:shadow-lift">
      <div className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-ink">
              <Link
                href={`/ingredients/${item.id}`}
                className="after:absolute after:inset-0 after:rounded-xl after:content-[''] hover:text-primary focus:outline-none focus-visible:after:ring-2 focus-visible:after:ring-primary"
              >
                {item.name_zh}
                {item.name_en ? (
                  <span className="ml-2 text-sm font-normal text-ink-muted">
                    {item.name_en}
                  </span>
                ) : null}
              </Link>
            </h3>
            {item.category ? (
              <p className="mt-0.5 text-sm text-ink-muted">
                {item.category.name_zh}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {item.draft ? (
              <span className="rounded-full bg-surface-alt px-2.5 py-0.5 text-xs text-ink-muted ring-1 ring-inset ring-line">
                待審核
              </span>
            ) : null}
            <RatingBadge
              rating={item.eczema_rating}
              label={item.rating_label}
            />
          </div>
        </div>
        {shown.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {shown.map((a) => (
              <AllergenTag key={a} name={a} />
            ))}
            {extra > 0 ? (
              <span className="px-1 py-1 text-xs text-ink-muted">
                +{extra}
              </span>
            ) : null}
          </div>
        ) : null}
        <div className="relative z-10 mt-3">
          <AddToShoppingListButton
            ingredientId={item.id}
            name={item.name_zh}
            category={item.category?.name_zh}
            small
          />
        </div>
      </div>
    </li>
  );
}
