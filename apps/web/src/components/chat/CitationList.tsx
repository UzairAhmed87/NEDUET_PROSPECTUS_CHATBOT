import { SourcePreview } from "@/components/chat/SourcePreview";
import type { Citation } from "@/types/api";

export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return null;
  }
  return (
    <section className="mt-4 border-t border-rule pt-3" aria-label="References">
      <h3 className="text-[11px] uppercase tracking-[0.16em] text-ink-faint">References</h3>
      <div className="mt-1">
        {citations.map((citation) => (
          <SourcePreview key={citation.chunk_id} citation={citation} />
        ))}
      </div>
    </section>
  );
}
