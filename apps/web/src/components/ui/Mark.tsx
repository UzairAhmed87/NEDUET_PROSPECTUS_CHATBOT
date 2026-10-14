export function Mark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      aria-hidden="true"
      className={className}
    >
      <rect width="40" height="40" fill="#9B2032" />
      <rect x="2" y="2" width="36" height="36" fill="none" stroke="#F8F4EB" strokeWidth="1" />
      <text
        x="20"
        y="25"
        textAnchor="middle"
        fill="#F8F4EB"
        fontFamily="Georgia, serif"
        fontSize="13"
        fontWeight="700"
        letterSpacing="0.08em"
      >
        NED
      </text>
    </svg>
  );
}
