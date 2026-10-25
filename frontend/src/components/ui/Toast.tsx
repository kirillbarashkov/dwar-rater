import { useState, useEffect } from 'react';
import './Toast.css';

interface ToastMessage {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

let toastCallback: ((message: string, type: 'success' | 'error' | 'info' | 'warning') => void) | null = null;

// A42: идентификатор тоста — счётчик, а не `Date.now()`. Два уведомления,
// поднятые в одну миллисекунду, получали ОДИН id: таймер первого удалял оба
// (`filter(t => t.id !== id)`), и тост исчезал, не успев показаться. Плюс
// совпадали React-ключи.
let nextToastId = 0;

// eslint-disable-next-line react-refresh/only-export-components
export function showToast(message: string, type: 'success' | 'error' | 'info' | 'warning' = 'info') {
  if (toastCallback) {
    toastCallback(message, type);
  }
}

export function ToastProvider() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    toastCallback = (message: string, type: 'success' | 'error' | 'info' | 'warning') => {
      const id = ++nextToastId;
      setToasts(prev => [...prev, { id, message, type }]);
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 3000);
    };
    return () => { toastCallback = null; };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      ))}
    </div>
  );
}