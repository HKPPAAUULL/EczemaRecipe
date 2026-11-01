"use client";

import type { InputHTMLAttributes, ReactNode } from "react";

export function SearchIcon({
  className = "h-5 w-5 shrink-0 text-ink-muted",
}: {
  className?: string;
}) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
      <path
        fill="currentColor"
        d="M9 3a6 6 0 1 0 3.7 10.7l3.2 3.1a.75.75 0 1 0 1-1l-3.1-3.2A6 6 0 0 0 9 3Zm0 1.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Z"
      />
    </svg>
  );
}

export function PlusIcon({
  className = "h-5 w-5 shrink-0 text-ink-muted",
}: {
  className?: string;
}) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
      <path
        fill="currentColor"
        d="M10 4a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 10 4Z"
      />
    </svg>
  );
}

export const pillActionClass =
  "shrink-0 rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2";

export default function SearchField({
  icon,
  trailing,
  large = false,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  icon?: ReactNode;
  trailing?: ReactNode;
  large?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 rounded-full bg-surface shadow-card ring-1 ring-line focus-within:ring-2 focus-within:ring-primary ${
        large ? "px-5 py-3.5" : "px-4 py-2.5"
      }`}
    >
      {icon}
      <input
        {...props}
        className={`w-full bg-transparent text-ink outline-none placeholder:text-ink-muted/70 ${
          large ? "text-lg" : "text-base"
        }`}
      />
      {trailing}
    </div>
  );
}
