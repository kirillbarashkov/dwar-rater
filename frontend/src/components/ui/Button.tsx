import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './Button.css';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'small' | 'medium' | 'large';
  children: ReactNode;
}

// A44: `type` по умолчанию `button`. HTML-дефолт для <button> внутри <form> —
// `submit`, поэтому любая кнопка, случайно оказавшаяся в форме, отправляла её.
// Кнопкам, которые обязаны отправлять форму, тип задаётся явно.
export function Button({ variant = 'primary', size = 'medium', className = '', type = 'button', children, ...props }: ButtonProps) {
  const sizeClass = size === 'small' ? 'btn-sm' : size === 'large' ? 'btn-lg' : '';
  return (
    <button type={type} className={`btn btn-${variant} ${sizeClass} ${className}`} {...props}>
      {children}
    </button>
  );
}
