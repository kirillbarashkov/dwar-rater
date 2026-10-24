import { useState, useEffect , useRef} from 'react';
import './SearchBar.css';

interface SearchBarProps {
  onAnalyze: (url: string) => void;
  isLoading: boolean;
  defaultUrl?: string;
  compact?: boolean;
  value?: string;
  onChange?: (value: string) => void;
}

export function SearchBar({ onAnalyze, isLoading, defaultUrl, compact, value: externalValue, onChange: externalOnChange }: SearchBarProps) {
  const [internalUrl, setInternalUrl] = useState('');
  const [error, setError] = useState('');
  
  const url = externalValue ?? internalUrl;
  const setUrl = externalOnChange ?? setInternalUrl;

  // A19: `setUrl` — это либо setState, либо колбэк родителя, и его идентичность
  // может меняться на каждом рендере. Положить его прямо в зависимости — риск
  // цикла «эффект → setState → новый колбэк → эффект». Держим актуальным через
  // ref: зависимости остаются значениями, а вызов идёт всегда со свежим сеттером.
  const setUrlRef = useRef(setUrl);
  useEffect(() => {
    setUrlRef.current = setUrl;
  }, [setUrl]);

  useEffect(() => {
    if (defaultUrl && !externalValue) {
      setUrlRef.current(defaultUrl);
    }
  }, [defaultUrl, externalValue]);

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
    <form className={`search-bar ${compact ? 'compact' : ''}`} onSubmit={handleSubmit}>
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
      {!externalOnChange && (
        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Анализ...' : 'Анализировать'}
        </button>
      )}
    </form>
  );
}
