export function LoadingState() {
  return (
    <div className="flex items-center gap-3 py-2 text-sm text-ink-muted" role="status" aria-live="polite">
      <span className="inline-flex items-center gap-1 text-crimson" aria-hidden="true">
        <span className="loading-dot" />
        <span className="loading-dot" />
        <span className="loading-dot" />
      </span>
      Searching the prospectus and preparing a grounded answer…
    </div>
  );
}
