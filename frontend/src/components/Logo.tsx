interface LogoProps {
  size?: number;
  className?: string;
}

export function Logo({ size = 24, className }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 280 280"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="openagent"
    >
      <line x1="140" y1="170" x2="140" y2="50" stroke="currentColor" strokeWidth="4" strokeLinecap="round" opacity="0.6" />
      <line x1="140" y1="170" x2="244" y2="230" stroke="currentColor" strokeWidth="4" strokeLinecap="round" opacity="0.6" />
      <line x1="140" y1="170" x2="36" y2="230" stroke="currentColor" strokeWidth="4" strokeLinecap="round" opacity="0.6" />
      <circle cx="140" cy="50" r="20" fill="currentColor" opacity="0.85" />
      <circle cx="244" cy="230" r="20" fill="currentColor" opacity="0.85" />
      <circle cx="36" cy="230" r="20" fill="currentColor" opacity="0.85" />
      <circle cx="140" cy="170" r="48" fill="currentColor" />
    </svg>
  );
}
