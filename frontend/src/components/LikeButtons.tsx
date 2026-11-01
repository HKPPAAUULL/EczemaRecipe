"use client";

import { useCallback, useEffect, useState } from "react";

const VOTER_KEY = "ek:v1:voter";

function voterKey(): string | null {
  try {
    let k = localStorage.getItem(VOTER_KEY);
    if (!k) {
      k =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : Array.from({ length: 4 }, () =>
              Math.random().toString(36).slice(2, 12)
            ).join("");
      localStorage.setItem(VOTER_KEY, k);
    }
    return k;
  } catch {
    return null;
  }
}

interface VoteState {
  likes: number;
  dislikes: number;
  my_vote: number;
}

export default function LikeButtons({
  recipeId,
  initialLikes,
  initialDislikes,
}: {
  recipeId: number;
  initialLikes: number;
  initialDislikes: number;
}) {
  const [state, setState] = useState<VoteState>({
    likes: initialLikes,
    dislikes: initialDislikes,
    my_vote: 0,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const k = voterKey();
    if (!k) return;
    fetch(
      `/api/recipes/${recipeId}/votes?voter=${encodeURIComponent(k)}`
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((d: VoteState | null) => {
        if (d && typeof d.likes === "number") setState(d);
      })
      .catch(() => {});
  }, [recipeId]);

  const cast = useCallback(
    (vote: number) => {
      const k = voterKey();
      if (!k || busy) return;
      setBusy(true);
      setError("");
      const next = state.my_vote === vote ? 0 : vote;
      fetch(`/api/recipes/${recipeId}/votes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voter_key: k, vote: next }),
      })
        .then(async (r) => {
          const d = (await r.json().catch(() => null)) as VoteState | null;
          if (r.ok && d && typeof d.likes === "number") {
            setState(d);
          } else {
            setError("投票失敗，請稍後再試。");
          }
        })
        .catch(() => setError("網絡錯誤，請稍後再試。"))
        .finally(() => setBusy(false));
    },
    [busy, recipeId, state.my_vote]
  );

  const btn = (active: boolean) =>
    `inline-flex min-h-[44px] items-center gap-1.5 rounded-full border px-4 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 ${
      active
        ? "border-primary bg-primary text-white"
        : "border-line bg-surface text-ink hover:bg-surface-alt"
    }`;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-sm text-ink-muted">這個食譜對你有用嗎？</p>
      <button
        type="button"
        onClick={() => cast(1)}
        disabled={busy}
        aria-pressed={state.my_vote === 1}
        className={btn(state.my_vote === 1)}
      >
        <span aria-hidden="true">👍</span> 有用{" "}
        <span className="text-xs opacity-80">{state.likes}</span>
      </button>
      <button
        type="button"
        onClick={() => cast(-1)}
        disabled={busy}
        aria-pressed={state.my_vote === -1}
        className={btn(state.my_vote === -1)}
      >
        <span aria-hidden="true">👎</span> 不適合{" "}
        <span className="text-xs opacity-80">{state.dislikes}</span>
      </button>
      {error && (
        <p role="alert" className="w-full text-xs text-trigger">
          {error}
        </p>
      )}
    </div>
  );
}
