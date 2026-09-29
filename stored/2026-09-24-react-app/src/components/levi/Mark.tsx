export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <path fill="currentColor" d="M6 6h10v10h10v10H6z" />
    </svg>
  );
}
