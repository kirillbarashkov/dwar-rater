import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, usePermission } from '../../hooks/useAuth';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { showToast } from '../../components/ui/Toast';
import './ProfilePage.css';

export function ProfilePage() {
  const { user, updateProfile } = useAuth();
  const navigate = useNavigate();
  const canWrite = usePermission('character', 'write') === 'full';

  const [characterUrl, setCharacterUrl] = useState(user?.character_url ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      await updateProfile(characterUrl.trim());
      showToast(characterUrl.trim() ? 'Персонаж привязан' : 'Персонаж отвязан', 'success');
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Ошибка сохранения';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  const handleUnbind = async () => {
    setError('');
    setSaving(true);
    try {
      await updateProfile('');
      setCharacterUrl('');
      showToast('Персонаж отвязан', 'info');
    } catch (err) {
      const message = (err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Ошибка';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return <LoadingSpinner />;
  }

  const isBound = !!user.character_nick;

  return (
    <div className="profile-page">
      <div className="profile-header">
        <button className="profile-back-btn" onClick={() => navigate(-1)} title="Назад">
          ← Назад
        </button>
        <h1 className="profile-title">Профиль</h1>
      </div>

      <div className="profile-card">
        <div className="profile-section">
          <h2 className="profile-section-title">Аккаунт</h2>
          <div className="profile-account-info">
            <div className="profile-info-row">
              <span className="profile-info-label">Логин</span>
              <span className="profile-info-value">{user.username}</span>
            </div>
            <div className="profile-info-row">
              <span className="profile-info-label">Роль</span>
              <span className={`role-badge role-${user.role}`}>{user.role}</span>
            </div>
            <div className="profile-info-row">
              <span className="profile-info-label">Последний вход</span>
              <span className="profile-info-value">
                {user.last_login_at ? new Date(user.last_login_at).toLocaleString('ru-RU') : '—'}
              </span>
            </div>
          </div>
        </div>

        <div className="profile-divider" />

        <div className="profile-section">
          <h2 className="profile-section-title">Мой персонаж</h2>
          <p className="profile-section-desc">
            Укажите ник или ссылку на страницу персонажа в dwar.ru. Это включит вкладку «Персонаж»
            с информацией о вашем герое, боевых характеристиках и клановых взносах.
          </p>

          {isBound && (
            <div className="profile-character-bound">
              <span className="profile-character-bound-icon">🧙</span>
              <div className="profile-character-bound-info">
                <span className="profile-character-bound-label">Привязанный персонаж</span>
                <span className="profile-character-bound-nick">{user.character_nick}</span>
              </div>
            </div>
          )}

          {canWrite ? (
            <form onSubmit={handleSave} className="profile-form">
              <Input
                label="Ник или URL персонажа"
                value={characterUrl}
                onChange={(e) => setCharacterUrl(e.target.value)}
                placeholder="Например: Мэрлин или https://w1.dwar.ru/user_info.php?nick=Мэрлин"
                spellCheck={false}
              />
              {error && <div className="profile-error">{error}</div>}
              <div className="profile-form-actions">
                <Button type="submit" variant="primary" disabled={saving}>
                  {saving ? 'Сохранение...' : 'Сохранить'}
                </Button>
                {isBound && (
                  <Button type="button" variant="ghost" onClick={handleUnbind} disabled={saving}>
                    Отвязать
                  </Button>
                )}
              </div>
            </form>
          ) : (
            <div className="profile-permission-note">
              Недостаточно прав для изменения привязки персонажа. Обратитесь к администратору.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
