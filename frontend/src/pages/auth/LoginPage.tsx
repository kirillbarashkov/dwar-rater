import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import './LoginPage.css';

export function LoginPage() {
  const { login, login2fa, changePassword } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [requires2fa, setRequires2fa] = useState(false);
  const [userId2fa, setUserId2fa] = useState(0);
  const [code2fa, setCode2fa] = useState('');
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  // Store username for password change flow (Chrome needs it to update saved password)
  const [changePasswordUsername, setChangePasswordUsername] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await login(username, password);
      if (result.requires_2fa) {
        setRequires2fa(true);
        setUserId2fa(result.user_id || 0);
      } else if (result.must_change_password) {
        setChangePasswordUsername(username);
        setMustChangePassword(true);
      } else {
        navigate('/', { replace: true });
      }
    } catch {
      setError('Неверный логин или пароль');
    } finally {
      setLoading(false);
    }
  };

  const handle2fa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login2fa(userId2fa, code2fa);
      navigate('/', { replace: true });
    } catch {
      setError('Неверный код');
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (newPassword.length < 8) {
      setError('Пароль должен быть не менее 8 символов');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают');
      return;
    }
    setLoading(true);
    try {
      await changePassword(newPassword);
      navigate('/', { replace: true });
    } catch {
      setError('Ошибка смены пароля');
    } finally {
      setLoading(false);
    }
  };

  if (mustChangePassword) {
    return (
      <div className="login-section">
        <div className="login-card">
          <h2>Смена пароля</h2>
          <p className="login-subtitle">Необходимо сменить пароль при первом входе</p>
          <form onSubmit={handleChangePassword}>
            {/* Hidden username — Chrome needs this to update the saved password */}
            <input type="hidden" name="username" value={changePasswordUsername} />
            <input
              type="password"
              name="new-password"
              id="new-password"
              autoComplete="new-password"
              placeholder="Новый пароль (мин. 8 символов)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <input
              type="password"
              name="confirm-password"
              id="confirm-password"
              autoComplete="new-password"
              placeholder="Подтвердите пароль"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
            {error && <div className="login-error">{error}</div>}
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Сохранение...' : 'Сохранить'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (requires2fa) {
    return (
      <div className="login-section">
        <div className="login-card">
          <h2>2FA верификация</h2>
          <p className="login-subtitle">Введите код из Google Authenticator</p>
          <form onSubmit={handle2fa}>
            {/* Hidden username — Chrome knows which account this 2FA is for */}
            <input type="hidden" name="username" value={username} />
            <input
              type="text"
              name="code"
              id="2fa-code"
              autoComplete="one-time-code"
              placeholder="6-значный код"
              value={code2fa}
              onChange={(e) => setCode2fa(e.target.value)}
              maxLength={6}
              inputMode="numeric"
              pattern="[0-9]*"
            />
            {error && <div className="login-error">{error}</div>}
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Проверка...' : 'Войти'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="login-section">
      <div className="login-card">
        <h2>Dwar Rater</h2>
        <form onSubmit={handleLogin}>
          <input
            type="text"
            name="username"
            id="login-username"
            autoComplete="username"
            placeholder="Логин"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            spellCheck={false}
          />
          <input
            type="password"
            name="password"
            id="login-password"
            autoComplete="current-password"
            placeholder="Пароль"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <div className="login-error">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  );
}
