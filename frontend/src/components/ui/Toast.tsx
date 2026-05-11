import { useState, useEffect } from 'react';
import './Toast.css';

interface ToastMessage {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

let toastCallback: ((message: string, type: 'success' | 'error' | 'info' | 'warning') => void) | null = null;

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
      const id = Date.now();
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