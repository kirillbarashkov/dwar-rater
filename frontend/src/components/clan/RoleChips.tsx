import { splitRoles } from '../../utils/clanRoleDisplay';

interface RoleChipsProps {
  raw: string;
  /** True when this role came from "Структура клана" (ui_structure_role). */
  structural?: boolean;
}

export function RoleChips({ raw, structural = false }: RoleChipsProps) {
  const roles = splitRoles(raw);
  if (roles.length === 0) return <span className="cm-role-empty">—</span>;
  const cls = structural ? 'cm-role-chip cm-role-chip-structural' : 'cm-role-chip';
  if (roles.length === 1) {
    return <span className={cls}>{roles[0]}</span>;
  }
  return (
    <div className="cm-role-chips">
      {roles.map((r, i) => (
        <span key={`${r}-${i}`} className={cls}>{r}</span>
      ))}
    </div>
  );
}
