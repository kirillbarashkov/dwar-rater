import { useState, useEffect } from 'react';
import type { ClanHierarchyData } from '../../types/clanInfo';
import { getClanHierarchy, addClanHierarchy, updateClanHierarchy, deleteClanHierarchy } from '../../api/clanInfo';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Modal } from '../ui/Modal';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import './ClanHierarchy.css';

interface ClanHierarchyProps {
  clanId: number;
}

const ICONS = ['👑', '⚔️', '🛡️', '🛡️', '⚖️', '🔥', '❄️', '⚡', '🌙', '☀️', '💀', '🎭', '🎯', '💎', '🔮', '🩸', '🪓', '🏹', '🎮', ''];
const DEFAULT_COLORS = ['#ffd700', '#ff6b6b', '#4ecdc4', '#45b7d1', '#6c757d', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'];

export function ClanHierarchy({ clanId }: ClanHierarchyProps) {
  const [roles, setRoles] = useState<ClanHierarchyData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingRole, setEditingRole] = useState<ClanHierarchyData | null>(null);
  const [form, setForm] = useState({
    role_name: '', level: 1, color: '#00d4aa', icon: '', sort_order: 0,
    can_invite: false, can_kick: false, can_edit: false, can_analyze: true, min_level: 0,
  });

  useEffect(() => { loadRoles(); }, [clanId]);

  const loadRoles = async () => {
    try {
      const data = await getClanHierarchy(clanId);
      setRoles(data);
    } catch { /* ignore */ }
    finally { setIsLoading(false); }
  };

  const handleAdd = async () => {
    if (!form.role_name) return;
    try {
      await addClanHierarchy(clanId, form);
      await loadRoles();
      setShowModal(false);
      resetForm();
    } catch { /* ignore */ }
  };

  const handleEdit = async () => {
    if (!editingRole?.id) return;
    try {
      await updateClanHierarchy(clanId, editingRole.id, form);
      await loadRoles();
      setEditingRole(null);
      resetForm();
    } catch { /* ignore */ }
  };

  const handleDelete = async (role: ClanHierarchyData) => {
    if (!role.id) return;
    if (!confirm(`Удалить роль "${role.role_name}"?`)) return;
    try {
      await deleteClanHierarchy(clanId, role.id);
      await loadRoles();
    } catch { /* ignore */ }
  };

  const openEdit = (role: ClanHierarchyData) => {
    setEditingRole(role);
    setForm({
      role_name: role.role_name,
      level: role.level,
      color: role.color,
      icon: role.icon,
      sort_order: role.sort_order,
      can_invite: role.can_invite,
      can_kick: role.can_kick,
      can_edit: role.can_edit,
      can_analyze: role.can_analyze,
      min_level: role.min_level,
    });
  };

  const resetForm = () => {
    setForm({
      role_name: '', level: 1, color: '#00d4aa', icon: '', sort_order: roles.length + 1,
      can_invite: false, can_kick: false, can_edit: false, can_analyze: true, min_level: 0,
    });
  };

  if (isLoading) return <LoadingSpinner />;

  const formFields = (
    <>
      <Input label="Название роли" value={form.role_name} onChange={(e) => setForm({ ...form, role_name: e.target.value })} required />
      <div className="ch-form-grid">
        <Input label="Уровень" type="number" value={form.level} onChange={(e) => setForm({ ...form, level: parseInt(e.target.value) || 1 })} />
        <Input label="Сортировка" type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: parseInt(e.target.value) || 0 })} />
      </div>
      <div className="ch-form-grid">
        <div>
          <label className="ch-form-label">Цвет</label>
          <div className="ch-color-picker">
            {DEFAULT_COLORS.map((c) => (
              <button key={c} type="button" className={`ch-color-dot ${form.color === c ? 'active' : ''}`} style={{ background: c }} onClick={() => setForm({ ...form, color: c })} />
            ))}
            <input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} className="ch-color-input" />
          </div>
        </div>
        <div>
          <label className="ch-form-label">Иконка</label>
          <select className="ch-form-select" value={form.icon} onChange={(e) => setForm({ ...form, icon: e.target.value })}>
            <option value="">—</option>
            {ICONS.slice(0, -1).map((icon) => (<option key={icon} value={icon}>{icon}</option>))}
          </select>
        </div>
      </div>
      <div className="ch-form-label">Права доступа</div>
      <div className="ch-permissions">
        <label className="ch-checkbox"><input type="checkbox" checked={form.can_invite} onChange={(e) => setForm({ ...form, can_invite: e.target.checked })} /><span>Приглашать</span></label>
        <label className="ch-checkbox"><input type="checkbox" checked={form.can_kick} onChange={(e) => setForm({ ...form, can_kick: e.target.checked })} /><span>Исключать</span></label>
        <label className="ch-checkbox"><input type="checkbox" checked={form.can_edit} onChange={(e) => setForm({ ...form, can_edit: e.target.checked })} /><span>Редактировать</span></label>
        <label className="ch-checkbox"><input type="checkbox" checked={form.can_analyze} onChange={(e) => setForm({ ...form, can_analyze: e.target.checked })} /><span>Анализировать</span></label>
      </div>
    </>
  );

  return (
    <div className="clan-hierarchy">
      <div className="ch-toolbar">
        <h2 className="ch-title">Клановая иерархия</h2>
        <Button variant="primary" onClick={() => { resetForm(); setShowModal(true); }}>+ Добавить роль</Button>
      </div>
      <div className="ch-roles">
        {roles.map((role) => (
          <div key={role.id} className="ch-role-card" style={{ borderColor: role.color }}>
            <div className="ch-role-header">
              <span className="ch-role-icon">{role.icon}</span>
              <span className="ch-role-name" style={{ color: role.color }}>{role.role_name}</span>
              <span className="ch-role-level">Уровень {role.level}</span>
            </div>
            <div className="ch-role-perms">
              {role.can_invite && <span className="ch-perm">Приглашать</span>}
              {role.can_kick && <span className="ch-perm">Исключать</span>}
              {role.can_edit && <span className="ch-perm">Редактировать</span>}
              {role.can_analyze && <span className="ch-perm">Анализировать</span>}
            </div>
            <div className="ch-role-actions">
              <button className="ch-btn-edit" onClick={() => openEdit(role)}>✏️</button>
              <button className="ch-btn-del" onClick={() => handleDelete(role)}>🗑️</button>
            </div>
          </div>
        ))}
      </div>
      {roles.length === 0 && <p className="ch-empty">Роли не найдены</p>}
      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title="Добавить роль">
        {formFields}
        <div className="ch-modal-actions">
          <Button variant="ghost" onClick={() => setShowModal(false)}>Отмена</Button>
          <Button variant="primary" onClick={handleAdd}>Добавить</Button>
        </div>
      </Modal>
      <Modal isOpen={!!editingRole} onClose={() => setEditingRole(null)} title="Редактировать роль">
        {formFields}
        <div className="ch-modal-actions">
          <Button variant="ghost" onClick={() => setEditingRole(null)}>Отмена</Button>
          <Button variant="primary" onClick={handleEdit}>Сохранить</Button>
        </div>
      </Modal>
    </div>
  );
}