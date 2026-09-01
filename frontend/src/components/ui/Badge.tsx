type BadgeVariant = 'default' | 'active' | 'archived' | 'open' | 'closed' | 'admin' | 'investigator' | 'viewer';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-gray-100 text-gray-600',
  active: 'bg-emerald-50 text-emerald-700',
  archived: 'bg-gray-100 text-gray-500',
  open: 'bg-blue-50 text-blue-700',
  closed: 'bg-gray-100 text-gray-500',
  admin: 'bg-indigo-50 text-indigo-700',
  investigator: 'bg-amber-50 text-amber-700',
  viewer: 'bg-gray-100 text-gray-600',
};

export function Badge({ variant = 'default', children, icon, className = '' }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium
        ${variantClasses[variant]}
        ${className}
      `}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
}
