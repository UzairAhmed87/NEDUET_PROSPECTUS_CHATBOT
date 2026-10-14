export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className="border border-crimson/30 bg-crimson-soft px-3 py-2 text-sm text-crimson-dark"
      role="alert"
    >
      <p>{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="mt-2 underline underline-offset-2">
          Try again
        </button>
      ) : null}
    </div>
  );
}
