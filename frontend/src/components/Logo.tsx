export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 280 280" fill="none">
      <line x1="140" y1="140" x2="140" y2="80" stroke="currentColor" strokeWidth="10" strokeLinecap="round" opacity="0.6"/>
      <line x1="140" y1="140" x2="192" y2="170" stroke="currentColor" strokeWidth="10" strokeLinecap="round" opacity="0.6"/>
      <line x1="140" y1="140" x2="88" y2="170" stroke="currentColor" strokeWidth="10" strokeLinecap="round" opacity="0.6"/>
      <circle cx="140" cy="80" r="18" fill="currentColor" opacity="0.85"/>
      <circle cx="192" cy="170" r="18" fill="currentColor" opacity="0.85"/>
      <circle cx="88" cy="170" r="18" fill="currentColor" opacity="0.85"/>
      <circle cx="140" cy="140" r="30" fill="currentColor"/>
    </svg>
  );
}
