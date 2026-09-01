interface DrishtikLogoProps {
  size?: number;
  className?: string;
}

export function DrishtikLogo({ size = 28, className = '' }: DrishtikLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Drishtik logo"
    >
      {/* Outer lens arc */}
      <path
        d="M16 6C9.5 6 4.5 11 3 16c1.5 5 6.5 10 13 10s11.5-5 13-10c-1.5-5-6.5-10-13-10z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Inner iris ring */}
      <circle
        cx="16"
        cy="16"
        r="5.5"
        stroke="currentColor"
        strokeWidth="1.8"
        fill="none"
      />
      {/* Focal point */}
      <circle cx="16" cy="16" r="2" fill="currentColor" />
    </svg>
  );
}
