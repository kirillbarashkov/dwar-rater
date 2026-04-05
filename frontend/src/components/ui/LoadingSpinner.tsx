import './LoadingSpinner.css';

export function LoadingSpinner() {
  return (
    <div className="loading-spinner">
      <div className="spinner"></div>
      <p>Загрузка...</p>
    </div>
  );
}
