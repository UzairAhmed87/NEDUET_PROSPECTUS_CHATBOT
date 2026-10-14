import type { DocumentSummary } from "@/types/api";

export function DocumentRail({
  documents,
  notice,
}: {
  documents: DocumentSummary[];
  notice: string;
}) {
  return (
    <aside className="hidden w-[260px] shrink-0 border-r border-rule lg:block">
      <div className="sticky top-0 p-5">
        <h2 className="font-serif text-xl text-ink">Source</h2>
        <ul className="mt-4 space-y-3">
          {documents.length === 0 ? (
            <li className="border border-dashed border-rule bg-paper-raised p-3 text-sm text-ink-muted">
              No prospectus is available yet.
            </li>
          ) : (
            documents.map((document) => (
              <li key={document.document_id} className="border border-rule bg-paper-raised p-3">
                <p className="font-serif text-[15px] leading-snug text-ink">{document.title}</p>
                <p className="mt-1 text-xs text-ink-muted">{document.page_count} pages</p>
                {document.authenticity_verified ? null : (
                  <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-crimson" title={notice}>
                    Not verified as latest official
                  </p>
                )}
              </li>
            ))
          )}
        </ul>
      </div>
    </aside>
  );
}
