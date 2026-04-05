import { useState } from 'react';
import './SearchBar.css';

interface SearchBarProps {
  onAnalyze: (url: string) => void;
  isLoading: boolean;
}

export function SearchBar({ onAnalyze, isLoading }: SearchBarProps) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  const ALLOWED_DOMAINS = ['w1.dwar.ru', 'w2.dwar.ru', 'w3.dwar.ru', 'w4.dwar.ru', 'dwar.ru'];

  const validateInput = (value: string): string | null => {
    if (!value.trim()) {
      return 'Введите ссылку на персонажа';
    }
    if (value.startsWith('http')) {
      try {
        const parsed = new URL(value);
        if (!ALLOWED_DOMAINS.includes(parsed.hostname)) {
          return 'Разрешены только ссылки на dwar.ru';
        }
      } catch {
        return 'Некорректный URL';
      }
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validateInput(url);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError('');
    onAnalyze(url.trim());
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value);
    if (error) setError('');
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <input
          type="text"
          className={`search-input ${error ? 'search-input-error' : ''}`}
          placeholder="https://w1.dwar.ru/user_info.php?nick=ИмяПерсонажа"
          value={url}
          onChange={handleChange}
          disabled={isLoading}
        />
        {error && <span className="search-error">{error}</span>}
      </div>
      <button type="submit" className="btn btn-primary" disabled={isLoading}>
        {isLoading ? 'Анализ...' : 'Анализировать'}
      </button>
    </form>
  );
}
