"use client";

import { useState } from "react";

import type { Citation } from "@/types/api";

export function SourcePreview({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-rule/80 py-2 first:border-t-0">
      <button
        type="button"
        className="flex w-full items-baseline justify-between gap-3 text-left"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="text-sm text-ink">
          <span className="font-medium">{citation.document_title}</span>
          <span className="text-ink-muted">, p. {citation.page_number}</span>
        </span>
        <span className="text-[11px] uppercase tracking-[0.12em] text-ink-faint">
          {open ? "Hide excerpt" : "Show excerpt"}
        </span>
      </button>
      {open ? (
        <blockquote className="mt-2 border-l-2 border-crimson pl-3 text-[13px] leading-relaxed text-ink-muted">
          {citation.excerpt}
        </blockquote>
      ) : null}
    </div>
  );
}
