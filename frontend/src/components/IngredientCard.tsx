import Link from "next/link";
import type { IngredientListItem } from "@/lib/api";
import RatingBadge from "@/components/RatingBadge";
import AllergenTag from "@/components/AllergenTag";

const MAX_TAGS = 4;

export default function IngredientCard({
  item,
}: {
  item: IngredientListItem;
}) {
  const shown = item.allergens.slice(0, MAX_TAGS);
  const extra = item.allergens.length - shown.length;
  return (
    <li className="list-none">
      <Link
        href={`/ingredients/${item.id}`}
        className="block rounded-xl bg-surface p-4 shadow-card ring-1 ring-line transition-shadow hover:shadow-lift focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-ink">
              {item.name_zh}
              {item.name_en ? (
                <span className="ml-2 text-sm font-normal text-ink-muted">
                  {item.name_en}
                </span>
              ) : null}
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
      </Link>
    </li>
  );
}
