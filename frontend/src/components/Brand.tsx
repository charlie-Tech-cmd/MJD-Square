interface BrandProps {
  compact?: boolean;
}

export function Brand({ compact = false }: BrandProps) {
  return (
    <div className="brand-lockup" aria-label="MJD Square">
      <svg className="brand-mark" viewBox="0 0 48 48" role="img" aria-label="MJD Square logo">
        <rect width="48" height="48" rx="13" fill="#14263d" />
        <path d="M9 13h6v22H9zm9 0h6l6 9 6-9h6v22h-6V23l-6 9h-1l-5-9v12h-6z" fill="white" />
        <circle cx="36" cy="36" r="4" fill="#38b89a" />
      </svg>
      {!compact && (
        <span className="brand-name">
          MJD <strong>Square</strong>
        </span>
      )}
    </div>
  );
}
