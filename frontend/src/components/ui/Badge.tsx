import './Badge.css';

interface BadgeProps {
  label: string;
  color?: string;
  variant?: 'default' | 'quality';
}

export function Badge({ label, color, variant = 'default' }: BadgeProps) {
  if (variant === 'quality' && color) {
    return (
      <span className="badge badge-quality" style={{ backgroundColor: color, color: '#fff' }}>
        {label}
      </span>
    );
  }

  return <span className="badge">{label}</span>;
}
