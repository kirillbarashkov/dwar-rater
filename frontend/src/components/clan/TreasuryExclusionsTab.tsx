import { useCallback, useEffect, useState } from 'react';
import {
  applyExclusions,
  createExclusionGroup,
  deleteExclusionGroup,
  getExclusionGroups,
  updateExclusionGroup,
} from '../../api/treasuryExclusions';
import type { ExclusionGroup } from '../../types/treasuryExclusions';
import './TreasuryExclusionsTab.css';

const MODE_LABELS: Record<string, string> = {
  exclude: 'Исключить из отчётов',
  neutral: 'Нейтральные',
};

const MODE_HINTS: Record<string, string> = {
  exclude:
    'Операции с этими ресурсами не попадают ни в один отчёт казны: ни в налог, ни в ресурсы, ни в сводку.',
  neutral:
    'Операции не считаются сдачей, но остаются видимыми в журнале и истории — для справки.',
};

interface Props {
  clanId: number;
}

export function TreasuryExclusionsTab({ clanId }: Props) {
  const [groups, setGroups] = useState<ExclusionGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(
    null,
  );

  const [newName, setNewName] = useState('');
  const [newMode, setNewMode] = useState<'exclude' | 'neutral'>('exclude');
  const [newPrefixes, setNewPrefixes] = useState('');

  const [editing, setEditing] = useState<ExclusionGroup | null>(null);
  const [editName, setEditName] = useState('');
  const [editMode, setEditMode] = useState<'exclude' | 'neutral'>('exclude');
  const [editPrefixes, setEditPrefixes] = useState('');
  const [pendingDelete, setPendingDelete] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getExclusionGroups(clanId);
      setGroups(data.items);
    } catch {
      setMessage({ type: 'error', text: 'Не удалось загрузить группы исключений' });
    } finally {
      setLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    load();
  }, [load]);

  const parsePrefixes = (value: string) =>
    value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);

  const handleCreate = async () => {
    if (!newName.trim()) {
      setMessage({ type: 'error', text: 'Укажите название группы' });
      return;
    }
    try {
      await createExclusionGroup(clanId, {
        name: newName.trim(),
        mode: newMode,
        prefixes: parsePrefixes(newPrefixes),
      });
      setMessage({
        type: 'success',
        text: 'Группа создана. Нажмите «Применить правила», чтобы она подействовала на операции.',
      });
      setNewName('');
      setNewPrefixes('');
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось создать группу' });
    }
  };

  const openEdit = (group: ExclusionGroup) => {
    setEditing(group);
    setEditName(group.name);
    setEditMode(group.mode === 'neutral' ? 'neutral' : 'exclude');
    setEditPrefixes(group.rules.map((rule) => rule.prefix).join('\n'));
  };

  const handleUpdate = async () => {
    if (!editing) return;
    try {
      await updateExclusionGroup(clanId, editing.id, {
        name: editName.trim(),
        mode: editMode,
        prefixes: parsePrefixes(editPrefixes),
      });
      setMessage({
        type: 'success',
        text: 'Группа сохранена. Нажмите «Применить правила», чтобы изменения подействовали.',
      });
      setEditing(null);
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось сохранить группу' });
    }
  };

  const handleToggleActive = async (group: ExclusionGroup) => {
    try {
      await updateExclusionGroup(clanId, group.id, { is_active: !group.is_active });
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось переключить группу' });
    }
  };

  const handleDelete = async (group: ExclusionGroup) => {
    try {
      await deleteExclusionGroup(clanId, group.id);
      setMessage({ type: 'success', text: 'Группа удалена.' });
      setPendingDelete(null);
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось удалить группу' });
    }
  };

  const handleApply = async () => {
    try {
      const result = await applyExclusions(clanId);
      setMessage({
        type: 'success',
        text: `Правила применены: изменено операций — ${result.changed} из ${result.total}. Ручные решения казначея не затрагивались.`,
      });
      await load();
    } catch {
      setMessage({ type: 'error', text: 'Не удалось применить правила' });
    }
  };

  return (
    <div className="treasury-exclusions">
      <div className="treasury-header">
        <div className="treasury-header-top">
          <h2 className="treasury-title" title="Ресурсы, которые не участвуют в аналитике казны">
            Группы исключений
          </h2>
          <div className="treasury-header-actions">
            <button
              type="button"
              className="treasury-page-btn"
              title="Проставить классы операциям по правилам всех активных групп"
              onClick={handleApply}
            >
              Применить правила
            </button>
          </div>
        </div>
      </div>

      {message && (
        <div
          className={
            message.type === 'success'
              ? 'treasury-message treasury-message-success'
              : 'treasury-message treasury-message-error'
          }
        >
          {message.text}
        </div>
      )}

      <div className="treasury-note" title="Как это работает">
        Группа собирает типы ресурсов по началу названия: правило «Сущность» поймает
        и «Сущность кретса», и «Сущность корра». Режим «Исключить из отчётов» убирает
        операции из всех расчётов казны, «Нейтральные» — оставляет их видимыми,
        но не считает сдачей. Решения казначея по парам правила не перезаписывают.
      </div>

      <div className="ex-form">
        <h3 className="ex-form-title">Новая группа</h3>
        <div className="ta-filter-row">
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="ex-name" title="Название группы">
              Название
            </label>
            <input
              id="ex-name"
              className="ta-filter-input"
              value={newName}
              placeholder="например, Сущности"
              onChange={(event) => setNewName(event.target.value)}
            />
          </div>
          <div className="ta-filter-group">
            <label className="ta-filter-label" htmlFor="ex-mode" title="Что делать с ресурсами группы">
              Режим
            </label>
            <select
              id="ex-mode"
              className="ta-filter-input"
              value={newMode}
              onChange={(event) =>
                setNewMode(event.target.value === 'neutral' ? 'neutral' : 'exclude')
              }
            >
              <option value="exclude">Исключить из отчётов</option>
              <option value="neutral">Нейтральные</option>
            </select>
          </div>
          <div className="ta-filter-group ex-form-prefixes">
            <label
              className="ta-filter-label"
              htmlFor="ex-prefixes"
              title="По одному правилу в строке: сопоставление по началу названия ресурса"
            >
              Ресурсы (по одному в строке)
            </label>
            <textarea
              id="ex-prefixes"
              className="ta-filter-input ex-textarea"
              value={newPrefixes}
              placeholder={'Сущность\nДар'}
              onChange={(event) => setNewPrefixes(event.target.value)}
            />
          </div>
          <button type="button" className="treasury-page-btn" onClick={handleCreate}>
            Создать группу
          </button>
        </div>
      </div>

      {loading && <div className="treasury-empty">Загружаю группы…</div>}
      {!loading && groups.length === 0 && (
        <div className="treasury-empty">Групп пока нет. Создайте первую выше.</div>
      )}

      {!loading &&
        groups.map((group) => (
          <div key={group.id} className={group.is_active ? 'ex-card' : 'ex-card ex-card-off'}>
            <div className="ex-card-head">
              <span className="ex-name">{group.name}</span>
              <span className={`ex-mode ex-mode-${group.mode}`} title={MODE_HINTS[group.mode]}>
                {MODE_LABELS[group.mode] ?? group.mode}
              </span>
              {!group.is_active && <span className="ex-off">выключена</span>}
            </div>

            <div className="ex-rules">
              {group.rules.length === 0 ? (
                <span className="ex-empty">Правил нет — группа ничего не ловит.</span>
              ) : (
                group.rules.map((rule) => (
                  <span key={rule.id} className="ex-rule" title="Сопоставление по началу названия">
                    {rule.prefix}*
                  </span>
                ))
              )}
            </div>

            <div className="ex-actions">
              <button type="button" className="ex-btn-ghost" onClick={() => openEdit(group)}>
                Изменить
              </button>
              <button
                type="button"
                className="ex-btn-ghost"
                title="Выключенная группа не действует при применении правил"
                onClick={() => handleToggleActive(group)}
              >
                {group.is_active ? 'Выключить' : 'Включить'}
              </button>
              {pendingDelete === group.id ? (
                <>
                  <span className="ex-actions-label">Удалить группу?</span>
                  <button
                    type="button"
                    className="ex-btn-ghost"
                    onClick={() => handleDelete(group)}
                  >
                    Да, удалить
                  </button>
                  <button
                    type="button"
                    className="ex-btn-ghost"
                    onClick={() => setPendingDelete(null)}
                  >
                    Нет
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="ex-btn-ghost"
                  onClick={() => setPendingDelete(group.id)}
                >
                  Удалить
                </button>
              )}
            </div>
          </div>
        ))}

      {editing && (
        <div className="ex-modal-backdrop" onClick={() => setEditing(null)}>
          <div className="ex-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="ex-modal-title">Группа «{editing.name}»</h3>

            <div className="ex-modal-row">
              <label className="ex-modal-label" htmlFor="ex-edit-name">
                Название
              </label>
              <input
                id="ex-edit-name"
                className="ta-filter-input"
                value={editName}
                onChange={(event) => setEditName(event.target.value)}
              />
            </div>

            <div className="ex-modal-row">
              <label className="ex-modal-label" htmlFor="ex-edit-mode">
                Режим
              </label>
              <select
                id="ex-edit-mode"
                className="ta-filter-input"
                value={editMode}
                onChange={(event) =>
                  setEditMode(event.target.value === 'neutral' ? 'neutral' : 'exclude')
                }
              >
                <option value="exclude">Исключить из отчётов</option>
                <option value="neutral">Нейтральные</option>
              </select>
            </div>

            <div className="ex-modal-row">
              <label className="ex-modal-label" htmlFor="ex-edit-prefixes">
                Ресурсы (по одному в строке)
              </label>
              <textarea
                id="ex-edit-prefixes"
                className="ta-filter-input ex-textarea"
                value={editPrefixes}
                onChange={(event) => setEditPrefixes(event.target.value)}
              />
            </div>

            <div className="ex-modal-actions">
              <button type="button" className="treasury-page-btn" onClick={handleUpdate}>
                Сохранить
              </button>
              <button
                type="button"
                className="ex-btn-ghost"
                onClick={() => setEditing(null)}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
