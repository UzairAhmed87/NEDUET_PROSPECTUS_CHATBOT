import Link from "next/link";

import { Mark } from "@/components/ui/Mark";
import type { DocumentSummary } from "@/types/api";

export function Header({ document }: { document: DocumentSummary | null }) {
  const year = document?.academic_year;
  const verified = document?.authenticity_verified ?? false;

  return (
    <header className="border-b border-rule bg-paper-raised/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1120px] items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-3 text-ink">
          <Mark className="h-10 w-10 shrink-0" />
          <span className="min-w-0">
            <span className="block font-serif text-lg leading-tight tracking-tight">
              Prospectus Assistant
            </span>
            <span className="block text-[11px] uppercase tracking-[0.16em] text-ink-muted">
              NED University of Engineering &amp; Technology
            </span>
          </span>
        </Link>
        {document ? (
          <p className="hidden max-w-[16rem] truncate font-serif text-sm text-ink-muted sm:block">
            {document.title}
            {year && !document.title.includes(year) ? ` · ${year}` : ""}
            {verified ? "" : " · unverified"}
          </p>
        ) : null}
      </div>
    </header>
  );
}
