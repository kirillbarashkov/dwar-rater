import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './Button.css';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'small' | 'medium' | 'large';
  children: ReactNode;
}

export function Button({ variant = 'primary', size = 'medium', className = '', children, ...props }: ButtonProps) {
  const sizeClass = size === 'small' ? 'btn-sm' : size === 'large' ? 'btn-lg' : '';
  return (
    <button className={`btn btn-${variant} ${sizeClass} ${className}`} {...props}>
      {children}
    </button>
  );
}
