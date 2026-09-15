/**
 * Display helpers for clan members table role column.
 *
 * Two independent role concepts:
 *
 *  - ``clan_role``         — the in-game clan rank imported from dwar.ru
 *                            (Глава Ордена / Зам. Главы / Рыцарь Ордена / …)
 *  - ``ui_structure_role`` — the role the user assigned in the in-app
 *                            "Структура клана" editor. Lives on the member
 *                            from the server (derived from the saved
 *                            clan_structure) and is null for members who
 *                            are not part of the structure.
 *
 * The structural role always wins in the UI; when a member has none we
 * fall back to the imported clan role.
 */
import type { ClanMemberData } from '../types/clanInfo';

export function splitRoles(raw: string): string[] {
  // dwar.ru sometimes stores multiple roles separated by "\n" in a single
  // clan_role field (one member, several historical/active positions).
  return (raw || '')
    .split(/\r?\n/)
    .map((r) => r.trim())
    .filter(Boolean);
}

/** True when the user gave this member a role in "Структура клана". */
export function hasStructuralRole(
  m: Pick<ClanMemberData, 'ui_structure_role'>,
): boolean {
  return ((m.ui_structure_role ?? '').trim()).length > 0;
}

/** Structural role if the user assigned one, otherwise the imported one. */
export function effectiveRole(
  m: Pick<ClanMemberData, 'clan_role' | 'ui_structure_role'>,
): string {
  const structural = (m.ui_structure_role ?? '').trim();
  if (structural) return structural;
  return (m.clan_role ?? '').toString();
}
