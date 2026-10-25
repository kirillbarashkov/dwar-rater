import { useId } from 'react';
import type { InputHTMLAttributes } from 'react';
import './Input.css';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = '', id, ...props }: InputProps) {
  // A57: подпись обязана быть связана с полем. Без `htmlFor`/`id` клик по подписи
  // не фокусировал поле, а скринридер читал <input> без имени.
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;

  return (
    <div className={`input-group ${className}`}>
      {label && (
        <label className="input-label" htmlFor={inputId}>
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`input ${error ? 'input-error' : ''}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...props}
      />
      {error && (
        <span className="input-error-text" id={errorId} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
