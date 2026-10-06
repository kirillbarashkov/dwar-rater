from flask import Blueprint, request, jsonify, g
from datetime import datetime, date
import json
import requests
from shared.services.clan_parser import (
    fetch_clan_page,
    parse_clan_info,
    fetch_clan_treasury_report,
    parse_clan_treasury_operations,
    fetch_all_pages_until_date,
    fetch_all_pages_streaming,
    is_login_redirect,
    fetch_clan_management_page,
    parse_clan_members_from_management,
    fetch_clan_history_page,
    parse_clan_history_events,
    fetch_all_history_pages_streaming,
    parse_level_change_events,
    fetch_level_events_streaming,
    estimate_pages_in_range,
    _date_str_to_comparable,
    _op_date_day,
    _op_in_range,
)
from shared.services.data_logger import data_logger
from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TreasuryOperation,
    TaxCarryover,
    ClanCookie,
    ClanMembershipEvent,
    ClanLevelChangeEvent,
    TreasurySourceWindow,
)
from shared.services.tax_engine import (
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    STATUS_PENDING,
    compute_carryovers,
    compute_member_ledger,
    is_month_closed,
    prev_ym,
)
from shared.rbac import require_permission, feature, Permission as PermDef, get_user_permission


clan_info_bp = Blueprint("clan_info", __name__)

from shared.rbac import register_feature

register_feature(
    "clan_info",
    [
        PermDef("read", "Просмотр инфо/состава/казны", "GET /api/clan/*"),
        PermDef(
            "write",
            "Редактирование участников",
            "POST/PUT/DELETE /api/clan/*/members/*",
        ),
        PermDef(
            "admin",
            "Импорт/экспорт казны, бэкапы",
            "Treasury import/export/backup admin",
        ),
    ],
)

# Treasury management is its own permission surface: a «Казначей» must be able to
# correct operations and approve carry-overs without gaining clan-member import
# rights (which stay under clan_info:admin).
register_feature(
    "treasury",
    [
        PermDef(
            "read",
            "Просмотр журнала казны",
            "GET /api/clan/*/treasury/journal",
        ),
        PermDef(
            "write",
            "Корректировка операций казны",
            "PUT /api/clan/*/treasury/<id>, POST /api/clan/*/treasury/compensation",
        ),
        PermDef(
            "approve",
            "Подтверждение переносов/корректировок",
            "tax-carryover confirm/cancel/bulk",
        ),
        PermDef(
            "admin",
            "Импорт/бэкап казны, cookies, авто-сбор",
            "treasury import/restore/auto-fetch/cookies/estimate",
        ),
    ],
)


LEADER_ROLE = "Глава Ордена"
DEPUTY_ROLE = "Зам. Главы"
COUNCIL_ROLE = "Совесть"
COMMANDER_ROLE = "Воевода"

DEFAULT_COUNCIL_SLOTS = 4
CLAN_MAX_PLAYERS = 70


def _clip(value, limit, default=""):
    """Coerce to str, strip and truncate to a DB column limit.

    Scraped/imported values can exceed column widths (e.g. a long clan role),
    which used to raise DataError (StringDataRightTruncation) at commit time and
    surface as an opaque HTTP 500.
    """
    if value is None:
        return default
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text[:limit] if text else default


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _audit(action, target_type=None, target_id=None, old=None, new=None, clan_id=None, reason=None):
    """Write an audit entry for a clan/treasury mutation.

    Treasury corrections are manual reviewer decisions, so they must be
    attributable — mirror the helper used by features/admin/routes.py.
    ``clan_id`` links the entry to a clan so the treasury journal can list it;
    ``reason`` is a reason code from TREASURY_REASON_CODES, stored inside the
    new value.
    """
    import json

    from flask import g

    from shared.rbac.models import AuditLog

    def _dump(value):
        if value is None:
            return None
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    if reason:
        payload = dict(new) if isinstance(new, dict) else {"value": new}
        payload["reason"] = reason
        new = payload

    user = getattr(g, "current_user", None)
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        clan_id=clan_id,
        old_value=_dump(old),
        new_value=_dump(new),
        ip_address=request.remote_addr,
    )
    db.session.add(entry)


def _build_ui_structure_role_map(structure):
    """Build a {lowercased nick -> role_label} map from clan_structure.

    The result is served to the UI as the separate ``ui_structure_role``
    attribute of a member. Structural roles are assigned in the
    "Структура клана" editor and take priority over the imported
    ``clan_role`` (which mirrors the in-game rank from dwar.ru).

    Returned keys are lowercased because nicks are stored in mixed case.
    """
    if not structure:
        return {}
    mapping = {}
    leader = structure.get("leader") or {}
    if leader.get("nick"):
        mapping[leader["nick"].strip().lower()] = (
            leader.get("description") or "Глава Ордена"
        ).strip()
    for entry in structure.get("deputies") or []:
        nick = (entry.get("nick") or "").strip()
        if nick:
            mapping[nick.lower()] = (entry.get("description") or "Зам. Главы").strip()
    for entry in structure.get("council") or []:
        nick = (entry.get("nick") or "").strip()
        if nick:
            mapping[nick.lower()] = (entry.get("description") or "Совет ордена").strip()
    commander = structure.get("commander") or {}
    if commander.get("nick"):
        mapping[commander["nick"].strip().lower()] = (
            commander.get("description") or "Воевода"
        ).strip()
    return mapping


def _day_to_display(day_comparable):
    """'YYYYMMDD…' -> 'DD.MM.YYYY' (best effort)."""
    d = (day_comparable or "").strip()
    if len(d) < 8 or not d[:8].isdigit():
        return ""
    return f"{d[6:8]}.{d[4:6]}.{d[0:4]}"


def get_source_window(clan_id):
    """Learned boundary of the treasury history dwar still serves."""
    return TreasurySourceWindow.query.filter_by(clan_id=clan_id).first()


def remember_source_window(clan_id, oldest_date, total_pages=0):
    """Persist the oldest operation date the source actually returned.

    dwar purges operations after roughly six months without saying so; the app
    learns the boundary from real attempts (no probing). Only SATURATED
    observations reach here — the caller checks that the request was older than
    everything the report holds — so the value is the true end of the history
    and is written through in either direction.

    It must be able to move back: a too-new boundary (learned by a bug, as
    happened with single-day estimates) otherwise froze every older period for
    good, because the boundary is what the UI freezes periods against.
    """
    if not oldest_date:
        return None
    new_day = _date_str_to_comparable(oldest_date)
    if not new_day:
        return None
    row = TreasurySourceWindow.query.filter_by(clan_id=clan_id).first()
    if row is None:
        row = TreasurySourceWindow(
            clan_id=clan_id, oldest_date=oldest_date, total_pages=total_pages or 0
        )
        db.session.add(row)
    else:
        if _date_str_to_comparable(row.oldest_date) == new_day and not total_pages:
            return row
        row.oldest_date = oldest_date
        if total_pages:
            row.total_pages = total_pages
    try:
        db.session.commit()
        data_logger.info(
            f"[TREASURY] Source window for clan {clan_id}: data available from {oldest_date}"
        )
    except Exception:
        db.session.rollback()
        data_logger.warning("[TREASURY] Could not persist source window")
    return row


def _source_unavailable(boundary):
    """Standard payload for a range that predates the source's history."""
    tail = (
        f" — доступны операции начиная с {boundary}."
        if boundary
        else "."
    )
    return (
        {
            "success": False,
            "error": "range_unavailable",
            "oldest_available_date": boundary or None,
            "message": (
                "В источнике (dwar) нет данных за этот период: он хранит только"
                f" последние ~6 месяцев{tail}"
            ),
        }
    )


def build_clan_structure_from_members(clan_id, existing_structure=None):
    """Compute the canonical clan structure.

    NOTE: deputies/council/commander come from ``existing_structure``
    (the JSON blob the user saved in the editor), NOT from
    ``clan_member_info.clan_role``. A member's in-game role
    ("Зам. Главы", "Совет ордена") is independent from whether they
    are picked into the clan structure. The leader is the only role
    that stays sourced from the roster (there must be exactly one
    Глава Ордена, validated here).
    """
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).all()

    leaders = [m for m in members if m.clan_role == LEADER_ROLE]

    if len(leaders) > 1:
        leader_nicks = [m.nick for m in leaders]
        return (
            None,
            f"Несколько глав клана: {', '.join(leader_nicks)}. Оставьте одного.",
        )

    structure = {}

    if leaders:
        structure["leader"] = {
            "nick": leaders[0].nick,
            "description": leaders[0].clan_role,
        }

    # Start with whatever the user has saved in the structure JSON.
    saved_deputies = []
    saved_council = []
    saved_commander = None
    if existing_structure:
        saved_deputies = list(existing_structure.get("deputies") or [])
        saved_council = list(existing_structure.get("council") or [])
        saved_commander = existing_structure.get("commander")

    # Filter saved entries against the current roster (drop people who left).
    active_nicks = {m.nick for m in members}

    if saved_deputies:
        structure["deputies"] = [
            {"nick": d.get("nick", ""), "description": d.get("description", "Зам. Главы")}
            for d in saved_deputies
            if d.get("nick") in active_nicks
        ]
        if not structure["deputies"]:
            structure.pop("deputies", None)

    if saved_council:
        structure["council"] = [
            {"nick": c.get("nick", ""), "description": c.get("description", "Совет ордена")}
            for c in saved_council
            if c.get("nick") in active_nicks
        ]
        if not structure["council"]:
            structure.pop("council", None)

    if saved_commander and saved_commander.get("nick") in active_nicks:
        structure["commander"] = {
            "nick": saved_commander["nick"],
            "description": saved_commander.get("description", ""),
        }

    other_count = len(
        [
            m
            for m in members
            if m.clan_role
            not in (LEADER_ROLE, DEPUTY_ROLE, COUNCIL_ROLE, COMMANDER_ROLE)
        ]
    )
    structure["has_members"] = other_count > 0

    if existing_structure and "council_slots" in existing_structure:
        structure["council_slots"] = existing_structure["council_slots"]
    if "council_slots" not in structure:
        structure["council_slots"] = DEFAULT_COUNCIL_SLOTS

    return structure, None


@clan_info_bp.route("/api/clan/<int:clan_id>/info", methods=["GET"])
@require_permission("clan_info", "read")
def get_clan_info(clan_id):
    cached = ClanInfo.query.filter_by(clan_id=clan_id).first()

    structure_warning = None
    structure_error = None
    try:
        html, _ = fetch_clan_page(clan_id, mode="news")
        data = parse_clan_info(html, clan_id)

        actual_member_count = ClanMemberInfo.query.filter_by(
            clan_id=clan_id, is_deleted=False
        ).count()

        existing_structure = cached.get_clan_structure() if cached else None
        structure, structure_error = build_clan_structure_from_members(
            clan_id, existing_structure
        )

        if cached:
            cached.name = data["name"]
            if not cached.logo_big and data.get("logo_url"):
                cached.logo_url = data.get("logo_url", "")
                cached.logo_big = data.get("logo_big", "")
                cached.logo_small = data.get("logo_small", "")
            cached.description = data.get("description", "")
            cached.leader_nick = data.get("leader_nick", "")
            cached.leader_rank = data.get("leader_rank", "")
            cached.clan_rank = data.get("clan_rank", "")
            cached.clan_level = data.get("clan_level", 0)
            cached.step = data.get("step", 0)
            cached.talents = data.get("talents", 0)
            cached.current_players = actual_member_count
            cached.total_players = CLAN_MAX_PLAYERS

            if structure is not None:
                cached.set_clan_structure(structure)
        else:
            cached = ClanInfo(
                clan_id=clan_id,
                name=data["name"],
                logo_url=data.get("logo_url", ""),
                logo_big=data.get("logo_big", ""),
                logo_small=data.get("logo_small", ""),
                description=data.get("description", ""),
                leader_nick=data.get("leader_nick", ""),
                leader_rank=data.get("leader_rank", ""),
                clan_rank=data.get("clan_rank", ""),
                clan_level=data.get("clan_level", 0),
                step=data.get("step", 0),
                talents=data.get("talents", 0),
                current_players=actual_member_count,
                total_players=CLAN_MAX_PLAYERS,
            )
            if structure is not None:
                cached.set_clan_structure(structure)
            db.session.add(cached)
        db.session.commit()
    except Exception as e:
        if cached:
            pass
        else:
            return jsonify({"error": str(e)}), 500

    if structure_error:
        structure_warning = structure_error

    return jsonify(
        {
            "clan_id": cached.clan_id,
            "name": cached.name,
            "logo_url": cached.logo_url,
            "logo_big": cached.logo_big,
            "logo_small": cached.logo_small,
            "description": cached.description,
            "leader_nick": cached.leader_nick,
            "leader_rank": cached.leader_rank,
            "clan_rank": cached.clan_rank,
            "clan_level": cached.clan_level,
            "step": cached.step,
            "talents": cached.talents,
            "total_players": cached.total_players,
            "current_players": cached.current_players,
            "council": cached.get_council(),
            "clan_structure": cached.get_clan_structure(),
            "structure_warning": structure_warning,
            "updated_at": cached.updated_at.isoformat() if cached.updated_at else "",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/info", methods=["PUT"])
@require_permission("clan_info", "write")
def update_clan_info(clan_id):
    cached = ClanInfo.query.filter_by(clan_id=clan_id).first()
    if not cached:
        return jsonify({"error": "Клан не найден"}), 404

    data = request.json

    if "name" in data:
        cached.name = data["name"]
    if "logo_url" in data:
        cached.logo_url = data["logo_url"]
    if "logo_big" in data:
        cached.logo_big = data["logo_big"]
    if "logo_small" in data:
        cached.logo_small = data["logo_small"]
    if "description" in data:
        cached.description = data["description"]
    if "leader_nick" in data:
        cached.leader_nick = data["leader_nick"]
    if "leader_rank" in data:
        cached.leader_rank = data["leader_rank"]
    if "clan_rank" in data:
        cached.clan_rank = data["clan_rank"]
    if "clan_level" in data:
        cached.clan_level = data["clan_level"]
    if "step" in data:
        cached.step = data["step"]
    if "talents" in data:
        cached.talents = data["talents"]
    if "total_players" in data:
        cached.total_players = data["total_players"]
    if "current_players" in data:
        cached.current_players = data["current_players"]
    if "council" in data:
        cached.set_council(data["council"])
    if "clan_structure" in data:
        cached.set_clan_structure(data["clan_structure"])

    db.session.commit()

    return jsonify(
        {
            "clan_id": cached.clan_id,
            "name": cached.name,
            "logo_url": cached.logo_url,
            "logo_big": cached.logo_big,
            "logo_small": cached.logo_small,
            "description": cached.description,
            "leader_nick": cached.leader_nick,
            "leader_rank": cached.leader_rank,
            "clan_rank": cached.clan_rank,
            "clan_level": cached.clan_level,
            "step": cached.step,
            "talents": cached.talents,
            "total_players": cached.total_players,
            "current_players": cached.current_players,
            "council": cached.get_council(),
            "clan_structure": cached.get_clan_structure(),
            "updated_at": cached.updated_at.isoformat() if cached.updated_at else "",
        }
    )


# Import/reset endpoints removed - all member management now via UI


@clan_info_bp.route("/api/clan/<int:clan_id>/members", methods=["GET"])
@require_permission("clan_info", "read")
def get_clan_members(clan_id):
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).all()

    # ui_structure_role: role the user assigned in "Структура клана".
    # It is a separate, app-side attribute (ui_ prefix) and takes priority
    # over clan_role in the UI. None for members outside the structure.
    cached = ClanInfo.query.filter_by(clan_id=clan_id).first()
    structure = cached.get_clan_structure() if cached else None
    ui_roles = _build_ui_structure_role_map(structure)

    return jsonify(
        [
            {
                "id": m.id,
                "nick": m.nick,
                "icon": m.icon,
                "game_rank": m.game_rank,
                "level": m.level,
                "profession": m.profession,
                "profession_level": m.profession_level,
                "clan_role": m.clan_role,
                "ui_structure_role": ui_roles.get((m.nick or "").strip().lower()),
                "join_date": m.join_date,
                "trial_until": m.trial_until,
            }
            for m in members
        ]
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/members/left", methods=["GET"])
@require_permission("clan_info", "read")
def get_left_members(clan_id):
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=True).all()
    return jsonify(
        [
            {
                "id": m.id,
                "nick": m.nick,
                "icon": m.icon,
                "game_rank": m.game_rank,
                "level": m.level,
                "profession": m.profession,
                "profession_level": m.profession_level,
                "clan_role": m.clan_role,
                "join_date": m.join_date,
                "left_date": m.left_date,
                "leave_reason": m.leave_reason,
            }
            for m in members
        ]
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/members", methods=["POST"])
@require_permission("clan_info", "write")
def add_clan_member(clan_id):
    data = request.json
    required = ["nick", "level", "clan_role"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} обязателен"}), 400

    member = ClanMemberInfo(
        clan_id=clan_id,
        nick=data["nick"],
        icon=data.get("icon", ""),
        game_rank=data.get("game_rank", ""),
        level=data["level"],
        profession=data.get("profession", ""),
        profession_level=data.get("profession_level", 0),
        clan_role=data["clan_role"],
        join_date=data.get("join_date", ""),
        trial_until=data.get("trial_until", ""),
    )
    db.session.add(member)
    db.session.commit()

    return jsonify(
        {
            "id": member.id,
            "nick": member.nick,
            "icon": member.icon,
            "game_rank": member.game_rank,
            "level": member.level,
            "profession": member.profession,
            "profession_level": member.profession_level,
            "clan_role": member.clan_role,
            "join_date": member.join_date,
            "trial_until": member.trial_until,
        }
    ), 201


@clan_info_bp.route("/api/clan/<int:clan_id>/members/import", methods=["POST"])
@require_permission("clan_info", "admin")
def import_clan_members(clan_id):
    # Access is enforced by @require_permission("clan_info", "admin") — the old
    # hardcoded role check bypassed RBAC and made the role unassignable.
    from flask import g

    data = request.json
    members_data = data.get("members", [])
    clan_info_data = data.get("clanInfo")
    overwrite = data.get("overwrite", False)

    data_logger.info(
        f"[IMPORT] Starting import for clan {clan_id}, members count: {len(members_data)}, overwrite: {overwrite}, hasClanInfo: {clan_info_data is not None}"
    )

    if not isinstance(members_data, list):
        data_logger.warning(f"[IMPORT] Invalid data format for clan {clan_id}")
        return jsonify({"error": "members должен быть массивом"}), 400

    if clan_info_data:
        clan = ClanInfo.query.filter_by(clan_id=clan_id).first()
        if not clan:
            clan = ClanInfo(clan_id=clan_id, name="Орден Чести")
            db.session.add(clan)

        if clan_info_data.get("logo_big"):
            clan.logo_big = clan_info_data["logo_big"]
        if clan_info_data.get("logo_small"):
            clan.logo_small = clan_info_data["logo_small"]
        if clan_info_data.get("clan_rank"):
            clan.clan_rank = clan_info_data["clan_rank"]
        if clan_info_data.get("clan_level"):
            clan.clan_level = clan_info_data["clan_level"]
        if clan_info_data.get("step"):
            clan.step = clan_info_data["step"]
        if clan_info_data.get("talents"):
            clan.talents = clan_info_data["talents"]
        if clan_info_data.get("total_players"):
            clan.total_players = clan_info_data["total_players"]
        if clan_info_data.get("current_players"):
            clan.current_players = clan_info_data["current_players"]
        if clan_info_data.get("clan_structure"):
            data_logger.info(f"[IMPORT] Setting clan structure")
            clan.set_clan_structure(clan_info_data["clan_structure"])
        else:
            data_logger.warning(
                f"[IMPORT] No clan_structure in clanInfo: {list(clan_info_data.keys())}"
            )

        data_logger.info(f"[IMPORT] Updated clan info for clan {clan_id}")

    if overwrite:
        old_count = ClanMemberInfo.query.filter_by(
            clan_id=clan_id, is_deleted=False
        ).count()
        ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).update(
            {"is_deleted": True}
        )
        data_logger.info(
            f"[IMPORT] Soft-deleted {old_count} existing members for clan {clan_id}"
        )

    success = 0
    failed = 0
    errors = []
    skipped = 0

    # Same single-leader invariant as in /diff-import: pre-scan the batch
    # for "Глава Ордена" and refuse if the union with DB active leaders
    # would have more than one distinct nick. (See lines around 1912.)
    HEAD_ROLE = "Глава Ордена"
    batch_leaders: set[str] = set()
    for m in members_data:
        if (m.get("clan_role") or "").strip() == HEAD_ROLE:
            n = (m.get("nick") or "").strip()
            if n:
                batch_leaders.add(n.lower())
    if batch_leaders:
        existing_leaders = (
            ClanMemberInfo.query.filter_by(
                clan_id=clan_id, is_deleted=False, clan_role=HEAD_ROLE
            ).with_entities(ClanMemberInfo.nick).all()
        )
        db_leaders = {n[0].lower() for n in existing_leaders if n[0]}
        all_leaders = db_leaders | batch_leaders
        if len(all_leaders) > 1:
            return jsonify(
                {
                    "success": 0,
                    "skipped": 0,
                    "failed": 0,
                    "errors": [
                        "Несколько глав клана: "
                        + ", ".join(sorted(all_leaders))
                        + ". Оставьте одного."
                    ],
                }
            ), 400

    for i, member_data in enumerate(members_data):
        try:
            nick = member_data.get("nick", "").strip()
            if not nick:
                errors.append(f"Строка {i + 1}: пустой ник")
                failed += 1
                continue

            level = member_data.get("level", 1)
            if isinstance(level, str):
                try:
                    level = int(level)
                except ValueError:
                    level = 1

            clan_role = member_data.get("clan_role", "Рыцарь Ордена")

            existing = ClanMemberInfo.query.filter_by(
                clan_id=clan_id, nick=nick, is_deleted=False
            ).first()

            if existing:
                if overwrite:
                    existing.is_deleted = False
                    existing.game_rank = member_data.get("game_rank", "")
                    existing.level = level
                    existing.profession = member_data.get("profession", "")
                    existing.profession_level = member_data.get("profession_level", 0)
                    existing.clan_role = clan_role
                    existing.join_date = member_data.get("join_date", "")
                    existing.trial_until = member_data.get("trial_until", "")
                    success += 1
                    data_logger.debug(
                        f"[IMPORT] Updated member: {nick} (level {level})"
                    )
                else:
                    skipped += 1
            else:
                member = ClanMemberInfo(
                    clan_id=clan_id,
                    nick=nick,
                    icon=member_data.get("icon", ""),
                    game_rank=member_data.get("game_rank", ""),
                    level=level,
                    profession=member_data.get("profession", ""),
                    profession_level=member_data.get("profession_level", 0),
                    clan_role=clan_role,
                    join_date=member_data.get("join_date", ""),
                    trial_until=member_data.get("trial_until", ""),
                )
                db.session.add(member)
                success += 1
                data_logger.debug(f"[IMPORT] Added new member: {nick} (level {level})")
        except Exception as e:
            errors.append(f"Строка {i + 1}: {str(e)}")
            failed += 1
            data_logger.error(f"[IMPORT] Error on member {i + 1}: {str(e)}")

    db.session.commit()

    final_count = ClanMemberInfo.query.filter_by(
        clan_id=clan_id, is_deleted=False
    ).count()
    data_logger.info(
        f"[IMPORT] Completed for clan {clan_id}: success={success}, skipped={skipped}, failed={failed}, final_count={final_count}"
    )

    return jsonify(
        {
            "success": success,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
        }
    )


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/members/<int:member_id>", methods=["DELETE"]
)
@require_permission("clan_info", "write")
def delete_clan_member(clan_id, member_id):
    member = ClanMemberInfo.query.filter_by(id=member_id, clan_id=clan_id).first()
    if not member:
        data_logger.warning(f"[DELETE] Member {member_id} not found in clan {clan_id}")
        return jsonify({"error": "Участник не найден"}), 404

    data = request.json or {}
    member_nick = member.nick
    member.is_deleted = True
    member.left_date = data.get("left_date", "")
    member.leave_reason = data.get("leave_reason", "")
    db.session.commit()
    data_logger.info(
        f"[DELETE] Soft-deleted member {member_nick} (id={member_id}) from clan {clan_id}, reason={member.leave_reason}"
    )
    return jsonify({"status": "deleted"})


@clan_info_bp.route("/api/clan/<int:clan_id>/members/<int:member_id>", methods=["PUT"])
@require_permission("clan_info", "write")
def update_clan_member(clan_id, member_id):
    member = ClanMemberInfo.query.filter_by(id=member_id, clan_id=clan_id).first()
    if not member:
        return jsonify({"error": "Участник не найден"}), 404

    data = request.json
    if "nick" in data:
        member.nick = data["nick"]
    if "icon" in data:
        member.icon = data["icon"]
    if "game_rank" in data:
        member.game_rank = data["game_rank"]
    if "level" in data:
        member.level = data["level"]
    if "profession" in data:
        member.profession = data["profession"]
    if "profession_level" in data:
        member.profession_level = data["profession_level"]
    if "clan_role" in data:
        member.clan_role = data["clan_role"]
    if "join_date" in data:
        member.join_date = data["join_date"]
    if "trial_until" in data:
        member.trial_until = data["trial_until"]

    db.session.commit()
    return jsonify(
        {
            "id": member.id,
            "nick": member.nick,
            "icon": member.icon,
            "game_rank": member.game_rank,
            "level": member.level,
            "profession": member.profession,
            "profession_level": member.profession_level,
            "clan_role": member.clan_role,
            "join_date": member.join_date,
            "trial_until": member.trial_until,
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/export", methods=["GET"])
@require_permission("clan_info", "read")
def export_treasury_operations(clan_id):
    operations = (
        TreasuryOperation.query.filter_by(clan_id=clan_id)
        .order_by(TreasuryOperation.id.desc())
        .all()
    )

    export_data = {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat(),
        "clan_id": clan_id,
        "operations_count": len(operations),
        "operations": [
            {
                "id": op.id,
                "date": op.date,
                "nick": op.nick,
                "operation_type": op.operation_type,
                "object_name": op.object_name,
                "quantity": op.quantity,
                "compensation_flag": op.compensation_flag,
                "compensation_comment": op.compensation_comment,
                "created_at": op.created_at.isoformat() if op.created_at else None,
            }
            for op in operations
        ],
    }

    data_logger.info(
        f"[TREASURY] Exported {len(operations)} operations for clan {clan_id}"
    )

    return jsonify(export_data)


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/backup", methods=["POST"])
@require_permission("clan_info", "write")
def save_treasury_backup(clan_id):
    import os
    from flask import current_app

    operations = (
        TreasuryOperation.query.filter_by(clan_id=clan_id)
        .order_by(TreasuryOperation.id.desc())
        .all()
    )

    export_data = {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat(),
        "clan_id": clan_id,
        "operations_count": len(operations),
        "operations": [
            {
                "id": op.id,
                "date": op.date,
                "nick": op.nick,
                "operation_type": op.operation_type,
                "object_name": op.object_name,
                "quantity": op.quantity,
                "compensation_flag": op.compensation_flag,
                "compensation_comment": op.compensation_comment,
                "created_at": op.created_at.isoformat() if op.created_at else None,
            }
            for op in operations
        ],
    }

    backup_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backup"
    )
    os.makedirs(backup_dir, exist_ok=True)

    filename = f"treasury-{clan_id}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    filepath = os.path.join(backup_dir, filename)

    import json

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    data_logger.info(f"[TREASURY] Backup saved to {filepath}")

    return jsonify(
        {
            "success": True,
            "filename": filename,
            "operations_count": len(operations),
            "message": f"Бэкап сохранён: {filename}",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/backups", methods=["GET"])
@require_permission("clan_info", "read")
def list_treasury_backups(clan_id):
    import os
    import glob

    backup_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backup"
    )
    pattern = os.path.join(backup_dir, f"treasury-{clan_id}-*.json")
    files = glob.glob(pattern)

    backups = []
    for filepath in sorted(files, key=os.path.getmtime, reverse=True):
        filename = os.path.basename(filepath)
        stat = os.stat(filepath)
        backups.append(
            {
                "filename": filename,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    return jsonify({"backups": backups})


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/backup/<filename>", methods=["GET"]
)
@require_permission("clan_info", "read")
def get_treasury_backup(clan_id, filename):
    import os
    import re

    if not re.match(r"^treasury-\d+-\d{8}-\d{6}\.json$", filename):
        return jsonify({"error": "Invalid filename"}), 400

    backup_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backup"
    )
    filepath = os.path.join(backup_dir, filename)

    if not os.path.exists(filepath):
        return jsonify({"error": "Backup not found"}), 404

    import json

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return jsonify(data)


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/backup/restore", methods=["POST"])
@require_permission("treasury", "admin")
def restore_treasury_backup(clan_id):
    data = request.json
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Filename required"}), 400

    import os
    import re

    if not re.match(r"^treasury-\d+-\d{8}-\d{6}\.json$", filename):
        return jsonify({"error": "Invalid filename"}), 400

    backup_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backup"
    )
    filepath = os.path.join(backup_dir, filename)

    if not os.path.exists(filepath):
        return jsonify({"error": "Backup not found"}), 404

    import json

    with open(filepath, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    TreasuryOperation.query.filter_by(clan_id=clan_id).delete()

    imported = 0
    for op in backup_data.get("operations", []):
        treasury_op = TreasuryOperation(
            clan_id=clan_id,
            date=op.get("date", ""),
            nick=op.get("nick", ""),
            operation_type=op.get("operation_type", ""),
            object_name=op.get("object_name", ""),
            quantity=op.get("quantity", 0),
            compensation_flag=op.get("compensation_flag", False),
            compensation_comment=op.get("compensation_comment", ""),
        )
        db.session.add(treasury_op)
        imported += 1

    _audit(
        "treasury_backup_restore",
        target_type="clan_treasury",
        target_id=clan_id,
        clan_id=clan_id,
        new={"filename": filename, "imported": imported},
    )

    db.session.commit()

    data_logger.info(f"[TREASURY] Restored {imported} operations from {filename}")

    return jsonify(
        {
            "success": True,
            "imported": imported,
            "message": f"Восстановлено {imported} операций из {filename}",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury", methods=["GET"])
@require_permission("clan_info", "read")
def get_treasury_operations(clan_id):
    operations = (
        TreasuryOperation.query.filter_by(clan_id=clan_id)
        .order_by(TreasuryOperation.id.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": op.id,
                "date": op.date,
                "nick": op.nick,
                "operation_type": op.operation_type,
                "object_name": op.object_name,
                "quantity": op.quantity,
                "compensation_flag": op.compensation_flag,
                "compensation_comment": op.compensation_comment,
            }
            for op in operations
        ]
    )


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/<int:operation_id>", methods=["PUT"]
)
@require_permission("treasury", "write")
def update_treasury_operation(clan_id, operation_id):
    operation = TreasuryOperation.query.filter_by(
        id=operation_id, clan_id=clan_id
    ).first()
    if not operation:
        return jsonify({"error": "Операция не найдена"}), 404

    data = request.json

    reason = _clip(data.get("reason"), 60)

    identity = {
        "nick": operation.nick,
        "date": operation.date,
        "operation_type": operation.operation_type,
        "object_name": operation.object_name,
    }

    old_state = {
        **identity,
        "quantity": operation.quantity,
        "compensation_flag": operation.compensation_flag,
        "compensation_comment": operation.compensation_comment,
    }

    if "quantity" in data:
        operation.quantity = int(data["quantity"])
    if "compensation_flag" in data:
        operation.compensation_flag = bool(data["compensation_flag"])
    if "compensation_comment" in data:
        operation.compensation_comment = _clip(data["compensation_comment"], 500)

    new_state = {
        **identity,
        "quantity": operation.quantity,
        "compensation_flag": operation.compensation_flag,
        "compensation_comment": operation.compensation_comment,
    }
    if new_state != old_state:
        _audit(
            "treasury_operation_update",
            target_type="treasury_operation",
            target_id=operation.id,
            old=old_state,
            new=new_state,
            clan_id=clan_id,
            reason=reason,
        )

    db.session.commit()

    data_logger.info(
        f"[TREASURY] Updated operation {operation_id}: qty={operation.quantity}, comp={operation.compensation_flag}, comment={operation.compensation_comment}"
    )

    return jsonify(
        {
            "id": operation.id,
            "date": operation.date,
            "nick": operation.nick,
            "operation_type": operation.operation_type,
            "object_name": operation.object_name,
            "quantity": operation.quantity,
            "compensation_flag": operation.compensation_flag,
            "compensation_comment": operation.compensation_comment,
        }
    )


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/<int:operation_id>/reassign", methods=["POST"]
)
@require_permission("treasury", "write")
def reassign_treasury_operation(clan_id, operation_id):
    """Re-attribute a payment: the money stays, its owner changes.

    The treasurer's «перераспределение». Only the nick moves — date, type,
    object and quantity are untouched, so the row keeps the identity the journal
    revert relies on and the tax engine simply sees the payment under another
    member. The reason is required and lives in the audit entry (never in the
    row's comment), because "why" belongs to the correction, not to the data.
    """
    operation = TreasuryOperation.query.filter_by(
        id=operation_id, clan_id=clan_id
    ).first()
    if not operation:
        return jsonify({"error": "Операция не найдена"}), 404

    data = request.json or {}
    to_nick = _clip(data.get("to_nick"), 100)
    reason = _clip(data.get("reason"), 60)

    if not to_nick:
        return jsonify({"error": "Укажите ник, которому принадлежит платёж"}), 400
    if reason not in {code["code"] for code in TREASURY_REASON_CODES}:
        return jsonify({"error": "Укажите причину перераспределения"}), 400
    if to_nick.lower() == (operation.nick or "").lower():
        return jsonify({"error": "Платёж уже зачислен этому участнику"}), 400
    if operation.compensation_flag:
        return jsonify({"error": "«Зачёт» — не деньги, перераспределять нечего"}), 400
    if _as_int(operation.quantity, 0) <= 0:
        return jsonify({"error": "В операции нет суммы"}), 400

    # Case-insensitive on purpose: the treasurer retypes the nick, and the stored
    # spelling must win — otherwise «beta» would sit next to «Beta» forever.
    member = (
        ClanMemberInfo.query.filter(
            ClanMemberInfo.clan_id == clan_id,
            db.func.lower(ClanMemberInfo.nick) == to_nick.lower(),
        ).first()
    )
    if not member:
        # Paying a nick the clan never had is a different mistake than a wrong
        # attribution — refuse instead of inventing a member.
        return jsonify({"error": f"{to_nick} нет в составе клана"}), 400

    from_nick = operation.nick
    # Store the canonical spelling from the roster, not what was typed, so the
    # engine's per-nick keys cannot drift on case or a typo.
    operation.nick = member.nick

    _audit(
        "treasury_operation_reassign",
        target_type="treasury_operation",
        target_id=operation.id,
        old={"nick": from_nick},
        new={"nick": operation.nick},
        clan_id=clan_id,
        reason=reason,
    )
    db.session.commit()

    data_logger.info(
        f"[TREASURY] Reassigned operation {operation_id}: {from_nick} -> {operation.nick}"
    )

    return jsonify(
        {
            "id": operation.id,
            "date": operation.date,
            "nick": operation.nick,
            "from_nick": from_nick,
            "operation_type": operation.operation_type,
            "object_name": operation.object_name,
            "quantity": operation.quantity,
            "compensation_flag": operation.compensation_flag,
            "member_status": "left" if member.is_deleted else "active",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/compensation", methods=["POST"])
@require_permission("treasury", "write")
def create_treasury_compensation(clan_id):
    data = request.json
    nick = data.get("nick")
    norm_amount = data.get("norm_amount", 0)
    comment = data.get("comment", "")
    months = data.get("months", [])
    year = data.get("year", datetime.now().year)

    if not nick:
        return jsonify({"error": "nick обязателен"}), 400

    if not months:
        return jsonify({"error": "months обязателен"}), 400

    created = []
    for month in months:
        date_str = f"15.{month:02d}.{year} 00:00"

        treasury_op = TreasuryOperation(
            clan_id=clan_id,
            date=date_str,
            nick=nick,
            operation_type="Деньги",
            object_name="Монеты",
            quantity=norm_amount,
            compensation_flag=True,
            compensation_comment=comment,
        )
        db.session.add(treasury_op)
        created.append(treasury_op)

    _audit(
        "treasury_compensation_create",
        target_type="treasury_operation",
        target_id=created[0].id if created else None,
        clan_id=clan_id,
        new={
            "nick": nick,
            "norm_amount": norm_amount,
            "months": months,
            "year": year,
            "comment": comment,
            "count": len(created),
        },
    )

    db.session.commit()

    data_logger.info(
        f"[TREASURY] Created {len(created)} compensations for {nick}: amount={norm_amount}, months={months}, comment={comment}"
    )

    return jsonify(
        {
            "created": len(created),
            "operations": [
                {
                    "id": op.id,
                    "date": op.date,
                    "nick": op.nick,
                    "quantity": op.quantity,
                    "compensation_flag": op.compensation_flag,
                    "compensation_comment": op.compensation_comment,
                }
                for op in created
            ],
        }
    ), 201


# --------------------------------------------------------------------------- #
# Tax overpayment carry-over («перенос переплаты на следующий месяц»)
# --------------------------------------------------------------------------- #


def _tax_carryover_decisions(clan_id):
    """{(nick_lower, month, year): {'status', 'amount'}} for already reviewed rows.

    These are the engine's fixed inputs: a confirmed amount is reused as-is and
    a cancelled month carries nothing — recomputation must never resurrect a
    proposal the treasurer rejected.
    """
    reviewed = (
        TaxCarryover.query.filter(
            TaxCarryover.clan_id == clan_id,
            TaxCarryover.status.in_((STATUS_CONFIRMED, STATUS_CANCELLED)),
        )
        .all()
    )
    return {
        (row.nick.lower(), row.source_month, row.source_year): {
            "status": row.status,
            "amount": row.amount,
        }
        for row in reviewed
    }


def _tax_engine_inputs(clan_id):
    """Load the engine inputs from the DB as plain dicts (engine stays pure)."""
    operations = [
        {
            "date": op.date,
            "nick": op.nick,
            "operation_type": op.operation_type,
            "object_name": op.object_name,
            "quantity": op.quantity,
            "compensation_flag": op.compensation_flag,
        }
        for op in TreasuryOperation.query.filter_by(clan_id=clan_id).all()
    ]
    members = [
        {
            "nick": m.nick,
            "level": m.level,
            "join_date": m.join_date,
            "trial_until": m.trial_until,
            "is_deleted": m.is_deleted,
        }
        for m in ClanMemberInfo.query.filter_by(clan_id=clan_id).all()
    ]
    level_events = {}
    for event in ClanLevelChangeEvent.query.filter_by(clan_id=clan_id).all():
        level_events.setdefault(event.nick.lower(), []).append(
            {"date": event.event_date, "new_level": event.new_level}
        )
    return operations, members, level_events


def _compute_tax_carryovers(clan_id, month, year, today=None):
    operations, members, level_events = _tax_engine_inputs(clan_id)
    return compute_carryovers(
        operations,
        members,
        level_events,
        _tax_carryover_decisions(clan_id),
        month,
        year,
        today=today,
    )


def _compute_tax_ledger(clan_id, from_month, from_year, to_month, to_year, today=None):
    operations, members, level_events = _tax_engine_inputs(clan_id)
    return compute_member_ledger(
        operations,
        members,
        level_events,
        _tax_carryover_decisions(clan_id),
        from_month,
        from_year,
        to_month,
        to_year,
        today=today,
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/tax-ledger", methods=["GET"])
@require_permission("clan_info", "read")
def get_tax_ledger(clan_id):
    """Лицевой счёт: per-member account over a window, plus the window totals.

    A read-only view over the SAME chain the carry-over proposals use, so the
    credit shown for a member is exactly what the engine proposes for that
    month — the two screens can never disagree. Defaults to the current year.
    """
    today = date.today()
    to_month = _as_int(request.args.get("to_month"), today.month)
    to_year = _as_int(request.args.get("to_year"), today.year)
    from_month = _as_int(request.args.get("from_month"), 1)
    from_year = _as_int(request.args.get("from_year"), to_year)
    if (
        not (1 <= from_month <= 12)
        or not (1 <= to_month <= 12)
        or from_year < 2000
        or to_year < 2000
    ):
        return jsonify({"error": "Некорректный месяц/год"}), 400
    if (from_year, from_month) > (to_year, to_month):
        return jsonify({"error": "Начало периода позже его конца"}), 400

    result = _compute_tax_ledger(
        clan_id, from_month, from_year, to_month, to_year, today
    )
    result.update(
        {
            "clan_id": clan_id,
            "from_month": from_month,
            "from_year": from_year,
            "to_month": to_month,
            "to_year": to_year,
            "is_closed": is_month_closed(to_month, to_year, today),
        }
    )
    return jsonify(result)


@clan_info_bp.route("/api/clan/<int:clan_id>/tax-carryover", methods=["GET"])
@require_permission("clan_info", "read")
def get_tax_carryovers(clan_id):
    """Carry-over proposals arising FROM a month, plus credits flowing INTO it.

    ``preview`` is computed but never stored: the running month is not final, so
    it can only be shown, not approved.
    """
    today = date.today()
    month = _as_int(request.args.get("month"), today.month)
    year = _as_int(request.args.get("year"), today.year)
    if not (1 <= month <= 12) or year < 2000:
        return jsonify({"error": "Некорректный месяц/год"}), 400

    closed = is_month_closed(month, year, today)
    rows = (
        TaxCarryover.query.filter_by(
            clan_id=clan_id, source_month=month, source_year=year
        )
        .order_by(TaxCarryover.nick)
        .all()
    )
    prev_month, prev_year = prev_ym(month, year)
    incoming = (
        TaxCarryover.query.filter_by(
            clan_id=clan_id,
            source_month=prev_month,
            source_year=prev_year,
            status=STATUS_CONFIRMED,
        )
        .order_by(TaxCarryover.nick)
        .all()
    )
    preview = []
    if not closed:
        preview = [
            p.as_dict() for p in _compute_tax_carryovers(clan_id, month, year, today)
        ]

    pending = [r for r in rows if r.status == STATUS_PENDING]
    return jsonify(
        {
            "month": month,
            "year": year,
            "is_closed": closed,
            "carryovers": [r.to_dict() for r in rows],
            "incoming": [
                {
                    "nick": r.nick,
                    "amount": r.amount,
                    "source_month": r.source_month,
                    "source_year": r.source_year,
                }
                for r in incoming
            ],
            "preview": preview,
            "pending_count": len(pending),
            "pending_total": sum(r.amount for r in pending),
        }
    )


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/tax-carryover/recompute", methods=["POST"]
)
@require_permission("treasury", "approve")
def recompute_tax_carryovers(clan_id):
    """Regenerate pending proposals for a closed month.

    Only ``pending`` rows are rewritten: confirmed and cancelled rows are the
    treasurer's decisions and stay untouched. A pending row whose excess has
    disappeared (payments shrank, the member left) is removed.
    """
    today = date.today()
    data = request.get_json(silent=True) or {}
    month = _as_int(data.get("month"), 0)
    year = _as_int(data.get("year"), 0)
    if not (1 <= month <= 12) or year < 2000:
        return jsonify({"error": "month и year обязательны"}), 400
    if not is_month_closed(month, year, today):
        return (
            jsonify(
                {
                    "error": "month_not_closed",
                    "message": "Перенос формируется только по завершённому месяцу; "
                    "для текущего месяца доступен прогноз.",
                }
            ),
            400,
        )

    proposals = _compute_tax_carryovers(clan_id, month, year, today)
    by_nick = {p.nick.lower(): p for p in proposals}

    existing = TaxCarryover.query.filter_by(
        clan_id=clan_id, source_month=month, source_year=year
    ).all()
    existing_by_nick = {row.nick.lower(): row for row in existing}

    user = getattr(g, "current_user", None)
    created = updated = removed = 0

    for nick_lower, row in list(existing_by_nick.items()):
        if row.status != STATUS_PENDING:
            continue
        proposal = by_nick.get(nick_lower)
        if proposal is None:
            db.session.delete(row)
            removed += 1
        elif row.amount != proposal.amount:
            row.amount = proposal.amount
            updated += 1

    for nick_lower, proposal in by_nick.items():
        if nick_lower in existing_by_nick:
            continue
        db.session.add(
            TaxCarryover(
                clan_id=clan_id,
                nick=proposal.nick,
                source_month=proposal.source_month,
                source_year=proposal.source_year,
                amount=proposal.amount,
                status=STATUS_PENDING,
                created_by=user.id if user else None,
            )
        )
        created += 1

    _audit(
        "tax_carryover_recompute",
        target_type="tax_carryover",
        target_id=clan_id,
        clan_id=clan_id,
        new={
            "month": month,
            "year": year,
            "created": created,
            "updated": updated,
            "removed": removed,
        },
    )
    db.session.commit()

    rows = (
        TaxCarryover.query.filter_by(
            clan_id=clan_id, source_month=month, source_year=year
        )
        .order_by(TaxCarryover.nick)
        .all()
    )
    return jsonify(
        {
            "success": True,
            "created": created,
            "updated": updated,
            "removed": removed,
            "carryovers": [r.to_dict() for r in rows],
        }
    )


def _review_tax_carryover(clan_id, carryover_id, status):
    row = TaxCarryover.query.filter_by(id=carryover_id, clan_id=clan_id).first()
    if not row:
        return jsonify({"error": "Перенос не найден"}), 404
    if row.status != STATUS_PENDING:
        return (
            jsonify(
                {
                    "error": "not_pending",
                    "message": f"Перенос уже обработан ({row.status})",
                }
            ),
            409,
        )

    data = request.get_json(silent=True) or {}
    if "comment" in data:
        row.comment = _clip(data.get("comment"), 500)

    user = getattr(g, "current_user", None)
    row.status = status
    row.reviewed_by = user.id if user else None
    row.reviewed_at = datetime.utcnow()

    _audit(
        f"tax_carryover_{status}",
        target_type="tax_carryover",
        target_id=row.id,
        clan_id=clan_id,
        old={"status": STATUS_PENDING},
        new={
            "status": status,
            "nick": row.nick,
            "amount": row.amount,
            "source_month": row.source_month,
            "source_year": row.source_year,
            "comment": row.comment or "",
        },
    )
    db.session.commit()
    return jsonify({"success": True, "carryover": row.to_dict()})


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/tax-carryover/<int:carryover_id>/confirm",
    methods=["POST"]
)
@require_permission("treasury", "approve")
def confirm_tax_carryover(clan_id, carryover_id):
    return _review_tax_carryover(clan_id, carryover_id, STATUS_CONFIRMED)


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/tax-carryover/<int:carryover_id>/cancel",
    methods=["POST"]
)
@require_permission("treasury", "approve")
def cancel_tax_carryover(clan_id, carryover_id):
    return _review_tax_carryover(clan_id, carryover_id, STATUS_CANCELLED)


@clan_info_bp.route("/api/clan/<int:clan_id>/tax-carryover/bulk", methods=["POST"])
@require_permission("treasury", "approve")
def bulk_review_tax_carryovers(clan_id):
    """Confirm or cancel a whole batch («Подтвердить все» / «Отменить все»)."""
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    if action not in ("confirm", "cancel"):
        return jsonify({"error": "action должен быть confirm или cancel"}), 400

    ids = [_as_int(i) for i in (data.get("ids") or [])]
    ids = [i for i in ids if i]
    if not ids:
        return jsonify({"error": "ids обязателен"}), 400

    status = STATUS_CONFIRMED if action == "confirm" else STATUS_CANCELLED
    comment = _clip(data.get("comment"), 500)
    user = getattr(g, "current_user", None)

    rows = TaxCarryover.query.filter(
        TaxCarryover.clan_id == clan_id, TaxCarryover.id.in_(ids)
    ).all()
    found_ids = {row.id for row in rows}

    updated_ids, skipped_ids = [], []
    for row in rows:
        if row.status != STATUS_PENDING:
            skipped_ids.append(row.id)
            continue
        row.status = status
        if comment:
            row.comment = comment
        row.reviewed_by = user.id if user else None
        row.reviewed_at = datetime.utcnow()
        updated_ids.append(row.id)

    missing_ids = [i for i in ids if i not in found_ids]
    _audit(
        f"tax_carryover_bulk_{action}",
        target_type="tax_carryover",
        target_id=clan_id,
        clan_id=clan_id,
        new={
            "updated": len(updated_ids),
            "skipped": skipped_ids,
            "missing": missing_ids,
            "comment": comment,
        },
    )
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "updated": len(updated_ids),
            "updated_ids": updated_ids,
            "skipped_ids": skipped_ids,
            "missing_ids": missing_ids,
        }
    )


# --------------------------------------------------------------------------- #
# Treasury journal («журнал корректировок»)
# --------------------------------------------------------------------------- #

# Reason codes a treasurer picks when correcting a record. Served to the UI
# from here so the dropdown and the stored values cannot drift apart.
TREASURY_REASON_CODES = [
    {"code": "carryover_credit", "label": "Зачёт переплаты"},
    {"code": "carryover_refund", "label": "Возврат переплаты"},
    {"code": "level_surcharge", "label": "Доначисление (рост уровня)"},
    {"code": "wrong_nick", "label": "Ошибочный ник"},
    {"code": "duplicate", "label": "Дубль операции"},
    {"code": "import_fix", "label": "Исправление импорта"},
    {"code": "council_decision", "label": "Решение главы/совета"},
    {"code": "other", "label": "Другое"},
]

# Everything a treasurer can do to the treasury, in journal order.
TREASURY_JOURNAL_ACTIONS = [
    "treasury_operation_update",
    "treasury_operation_reassign",
    "treasury_compensation_create",
    "treasury_import",
    "treasury_backup_restore",
    "treasury_journal_revert",
    "tax_carryover_recompute",
    "tax_carryover_confirmed",
    "tax_carryover_cancelled",
    "tax_carryover_bulk_confirm",
    "tax_carryover_bulk_cancel",
]

# Which fields a journal entry restores, per action: the revert writes them back
# from the entry's `old` payload. An action missing here is still shown in the
# journal, it just cannot be undone by a click.
REVERTABLE_FIELDS = {
    "treasury_operation_update": (
        "quantity",
        "compensation_flag",
        "compensation_comment",
    ),
    "treasury_operation_reassign": ("nick",),
}


def _audit_json(value):
    """Audit values are JSON text (or a plain string for hand-written rows)."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {"value": value}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _journal_entry(entry):
    old = _audit_json(entry.old_value)
    new = _audit_json(entry.new_value)
    return {
        "id": entry.id,
        "action": entry.action,
        "username": entry.user.username if entry.user else "system",
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "reason": (new or {}).get("reason"),
        "nick": (new or {}).get("nick") or (old or {}).get("nick"),
        "old": old,
        "new": new,
        "revertable": entry.action in REVERTABLE_FIELDS,
    }


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/journal", methods=["GET"])
@require_permission("treasury", "read")
def get_treasury_journal(clan_id):
    """Who corrected what in this clan's treasury, newest first."""
    from shared.rbac.models import AuditLog

    limit = min(max(_as_int(request.args.get("limit"), 50), 1), 200)
    offset = max(_as_int(request.args.get("offset"), 0), 0)
    action = (request.args.get("action") or "").strip()
    nick = (request.args.get("nick") or "").strip().lower()

    query = AuditLog.query.filter(
        AuditLog.clan_id == clan_id,
        AuditLog.action.in_(TREASURY_JOURNAL_ACTIONS),
    )
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    rows = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    entries = [_journal_entry(row) for row in rows]
    if nick:
        entries = [e for e in entries if nick in (e.get("nick") or "").lower()]

    return jsonify(
        {
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset,
            "reason_codes": TREASURY_REASON_CODES,
            "actions": TREASURY_JOURNAL_ACTIONS,
        }
    )


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/journal/<int:entry_id>/revert", methods=["POST"]
)
@require_permission("treasury", "write")
def revert_treasury_journal_entry(clan_id, entry_id):
    """Undo a correction by writing the previous values back.

    History is never deleted: the revert is itself a new journal entry. It is
    refused when the operation changed after the original edit, so a revert
    cannot silently drop a newer correction.
    """
    from shared.rbac.models import AuditLog

    entry = AuditLog.query.filter_by(id=entry_id, clan_id=clan_id).first()
    if not entry:
        return jsonify({"error": "Запись журнала не найдена"}), 404
    fields = REVERTABLE_FIELDS.get(entry.action)
    if not fields:
        return (
            jsonify(
                {
                    "error": "not_revertable",
                    "message": "Обратной записью откатываются только правки и переносы операций казны",
                }
            ),
            400,
        )

    old = _audit_json(entry.old_value) or {}
    new = _audit_json(entry.new_value) or {}

    operation = TreasuryOperation.query.filter_by(
        id=entry.target_id, clan_id=clan_id
    ).first()
    if not operation:
        return (
            jsonify(
                {
                    "error": "operation_missing",
                    "message": "Операции больше нет (например, её снёс переимпорт периода)",
                }
            ),
            404,
        )

    current = {field: getattr(operation, field) for field in fields}
    expected = {field: new.get(field) for field in fields}
    if current != expected:
        return (
            jsonify(
                {
                    "error": "operation_changed",
                    "message": "Операцию изменили после этой правки — откат не применён, "
                    "чтобы не потерять более поздние данные.",
                    "current": current,
                    "expected": expected,
                }
            ),
            409,
        )

    # Captured before the write-back: for a reassignment revert the nickname is
    # exactly what changes, so the entry must show it as it was.
    identity = {
        "nick": operation.nick,
        "date": operation.date,
        "operation_type": operation.operation_type,
        "object_name": operation.object_name,
    }

    for field in fields:
        if field in old and old[field] is not None:
            setattr(operation, field, old[field])

    restored = {field: getattr(operation, field) for field in fields}
    data = request.get_json(silent=True) or {}
    _audit(
        "treasury_journal_revert",
        target_type="treasury_operation",
        target_id=operation.id,
        old={**identity, **current},
        new={**{**identity, "nick": operation.nick}, **restored},
        clan_id=clan_id,
        reason=_clip(data.get("reason"), 60) or "revert",
    )
    db.session.commit()

    data_logger.info(
        f"[TREASURY] Journal entry {entry_id} reverted on operation {operation.id}"
    )
    return jsonify(
        {
            "success": True,
            "operation_id": operation.id,
            "restored": restored,
        }
    )


def _replace_operations_in_range(clan_id, operations_data):
    """Delete the clan's operations inside the day span of an incoming batch.

    Idempotency without value-based dedupe: dwar legitimately repeats identical
    rows (the same payment listed twice on a page), so "skip a row that already
    exists" would silently drop real operations. The span is derived from the
    batch itself, so re-importing the same range replaces it instead of
    doubling it, while periods outside the batch are never touched.
    """
    day_keys = [_date_str_to_comparable(op.get("date") or "") for op in operations_data]
    valid = sorted(key for key in day_keys if key)
    if not valid:
        return 0
    low, high = valid[0], valid[-1]
    existing = (
        TreasuryOperation.query.filter_by(clan_id=clan_id)
        .with_entities(TreasuryOperation.id, TreasuryOperation.date)
        .all()
    )
    doomed = [
        row_id
        for row_id, date in existing
        if low <= _date_str_to_comparable(date or "") <= high
    ]
    for start in range(0, len(doomed), 500):
        chunk = doomed[start : start + 500]
        TreasuryOperation.query.filter(TreasuryOperation.id.in_(chunk)).delete(
            synchronize_session=False
        )
    return len(doomed)


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/import", methods=["POST"])
@require_permission("treasury", "admin")
def import_treasury_operations(clan_id):
    data = request.json
    operations_data = data.get("operations", [])
    replace = data.get("replace", False)
    replace_range = bool(data.get("replace_range", False))

    data_logger.info(
        f"[TREASURY] Importing {len(operations_data)} operations for clan {clan_id} "
        f"(replace={replace}, replace_range={replace_range})"
    )

    if replace:
        TreasuryOperation.query.filter_by(clan_id=clan_id).delete()
        data_logger.info(f"[TREASURY] Cleared existing operations for clan {clan_id}")
    elif replace_range:
        # Re-importing the same range used to append and double the treasury.
        if not operations_data:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "empty_import",
                        "message": "Нечего импортировать: пустой набор операций, "
                        "существующие данные не изменены.",
                    }
                ),
                400,
            )
        removed = _replace_operations_in_range(clan_id, operations_data)
        data_logger.info(
            f"[TREASURY] Range replace for clan {clan_id}: removed {removed} "
            "operations inside the imported span"
        )

    imported = 0
    updated = 0
    skipped = 0
    skip_reasons = []

    # With a full replace the stored rows were just cleared, so the batch is
    # authoritative and every row is inserted as-is. The per-row dedupe below
    # matches on (date, nick, type, object) and would collapse the identical
    # rows dwar legitimately repeats (the same payment listed twice), silently
    # dropping real operations.
    authoritative = bool(replace or replace_range)

    data_logger.info(
        f"[TREASURY] Processing {len(operations_data)} operations from frontend"
    )

    for i, op in enumerate(operations_data):
        try:
            date = _clip(op.get("date"), 20)
            nick = _clip(op.get("nick"), 100)
            operation_type = _clip(op.get("operation_type"), 100)
            object_name = _clip(op.get("object_name"), 200)
            quantity = _as_int(op.get("quantity"), 0)
            compensation_flag = op.get("compensation_flag", False)
            compensation_comment = _clip(op.get("compensation_comment"), 500)

            if not date or not nick:
                skip_reasons.append(f"op {i}: empty date or nick")
                skipped += 1
                continue

            existing = None
            if not authoritative:
                existing = TreasuryOperation.query.filter_by(
                    clan_id=clan_id,
                    date=date,
                    nick=nick,
                    operation_type=operation_type,
                    object_name=object_name,
                ).first()

            if existing:
                if existing.quantity == quantity:
                    data_logger.debug(
                        f"[TREASURY] Op {i} will update: {date}|{nick}|{operation_type}|{object_name}|{quantity}"
                    )
                    existing.quantity = quantity
                    existing.compensation_flag = compensation_flag
                    existing.compensation_comment = compensation_comment
                    updated += 1
                else:
                    data_logger.debug(
                        f"[TREASURY] Op {i} will insert NEW (different qty): {date}|{nick}|{operation_type}|{object_name}|{quantity} (existing qty={existing.quantity})"
                    )
                    treasury_op = TreasuryOperation(
                        clan_id=clan_id,
                        date=date,
                        nick=nick,
                        operation_type=operation_type,
                        object_name=object_name,
                        quantity=quantity,
                        compensation_flag=compensation_flag,
                        compensation_comment=compensation_comment,
                    )
                    db.session.add(treasury_op)
                    imported += 1
            else:
                data_logger.debug(
                    f"[TREASURY] Op {i} will insert: {date}|{nick}|{operation_type}|{object_name}|{quantity}"
                )
                treasury_op = TreasuryOperation(
                    clan_id=clan_id,
                    date=date,
                    nick=nick,
                    operation_type=operation_type,
                    object_name=object_name,
                    quantity=quantity,
                    compensation_flag=compensation_flag,
                    compensation_comment=compensation_comment,
                )
                db.session.add(treasury_op)
                imported += 1
        except Exception as e:
            data_logger.error(f"[TREASURY] Error importing operation {i}: {str(e)}")
            skip_reasons.append(f"op {i}: exception {str(e)}")
            skipped += 1

    if skip_reasons:
        data_logger.warning(f"[TREASURY] Skipped operations: {skip_reasons}")

    _audit(
        "treasury_import",
        target_type="clan_treasury",
        target_id=clan_id,
        clan_id=clan_id,
        new={
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "replace": replace,
            "replace_range": replace_range,
        },
    )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        data_logger.error(f"[TREASURY] Import commit failed: {e}")
        return jsonify(
            {
                "success": False,
                "imported": 0,
                "updated": 0,
                "skipped": skipped,
                "errors": skip_reasons + [f"Ошибка записи в БД: {e}"],
                "message": f"Не удалось сохранить операции: {e}",
            }
        ), 400

    final_count = TreasuryOperation.query.filter_by(clan_id=clan_id).count()
    data_logger.info(
        f"[TREASURY] Import completed for clan {clan_id}: added={imported}, updated={updated}, skipped={skipped}, total={final_count}"
    )

    return jsonify(
        {
            "success": True,
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "message": f"Импортировано {imported}, обновлено {updated}",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/date-coverage", methods=["GET"])
@require_permission("clan_info", "read")
def get_treasury_date_coverage(clan_id):
    """Return date coverage structure: years -> months -> days with operation counts."""
    from collections import defaultdict

    operations = TreasuryOperation.query.filter_by(clan_id=clan_id).all()

    coverage = {}
    total_ops = 0
    all_dates = []

    for op in operations:
        m = __import__("re").match(r"(\d{2})\.(\d{2})\.(\d{4})", op.date)
        if not m:
            continue
        day, month, year = m.group(1), m.group(2), m.group(3)
        date_key = f"{day}.{month}.{year}"
        all_dates.append(date_key)
        total_ops += 1

        if year not in coverage:
            coverage[year] = {"months": {}, "total_ops": 0}
        if month not in coverage[year]["months"]:
            coverage[year]["months"][month] = {"days": set(), "total_ops": 0}
        coverage[year]["months"][month]["days"].add(day)
        coverage[year]["months"][month]["total_ops"] += 1
        coverage[year]["total_ops"] += 1

    # Convert sets to sorted lists
    for year_data in coverage.values():
        for month_data in year_data["months"].values():
            month_data["days"] = sorted(
                month_data["days"], key=lambda d: int(d), reverse=True
            )

    # Sort years and months descending
    sorted_coverage = {}
    for year in sorted(coverage.keys(), reverse=True):
        year_data = coverage[year]
        sorted_months = {}
        for month in sorted(year_data["months"].keys(), reverse=True):
            sorted_months[month] = year_data["months"][month]
        sorted_coverage[year] = {
            "months": sorted_months,
            "total_ops": year_data["total_ops"],
        }

    # 'DD.MM.YYYY' strings do not sort chronologically (min() picked a
    # January date as "earliest" while December was reported as "latest").
    if all_dates:
        ordered_dates = sorted(all_dates, key=_date_str_to_comparable)
        earliest, latest = ordered_dates[0], ordered_dates[-1]
    else:
        earliest = latest = None

    window = get_source_window(clan_id)

    return jsonify(
        {
            "years": sorted_coverage,
            "total_dates_with_data": len(set(all_dates)),
            "total_operations": total_ops,
            "earliest_date": earliest,
            "latest_date": latest,
            # Boundary of the history dwar still serves. None until an import
            # attempt has reached the end of the report (no probing).
            "source_window": (
                {
                    "oldest_available_date": window.oldest_date,
                    "total_pages": window.total_pages,
                    "learned_at": (
                        window.learned_at.isoformat() if window.learned_at else None
                    ),
                }
                if window and window.oldest_date
                else None
            ),
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury", methods=["POST"])
@require_permission("treasury", "admin")
def fetch_treasury_operations(clan_id):
    data_logger.info(f"[TREASURY] Starting treasury fetch for clan {clan_id}")

    try:
        html, _ = fetch_clan_treasury_report()

        data_logger.info(f"[TREASURY] Received HTML length: {len(html)}")

        if "single_top_redirect" in html or "index.php" in html:
            data_logger.warning(
                f"[TREASURY] Site requires authentication, got redirect page"
            )
            return jsonify(
                {
                    "success": False,
                    "error": "Требуется авторизация на w1.dwar.ru",
                    "message": "Для импорта казны необходимо войти в игру через браузер и предоставить cookies сессии.",
                }
            ), 200

        operations = parse_clan_treasury_operations(html)

        data_logger.info(f"[TREASURY] Parsed {len(operations)} operations from page")

        old_count = TreasuryOperation.query.filter_by(clan_id=clan_id).count()
        TreasuryOperation.query.filter_by(clan_id=clan_id).delete()

        for op in operations:
            treasury_op = TreasuryOperation(
                clan_id=clan_id,
                date=op.get("date", ""),
                nick=op.get("nick", ""),
                operation_type=op.get("type", ""),
                object_name=op.get("object", ""),
                quantity=op.get("quantity", 0),
            )
            db.session.add(treasury_op)

        db.session.commit()

        final_count = TreasuryOperation.query.filter_by(clan_id=clan_id).count()
        data_logger.info(
            f"[TREASURY] Completed for clan {clan_id}: old={old_count}, new={final_count}"
        )

        return jsonify(
            {
                "success": True,
                "imported": final_count,
                "message": f"Импортировано {final_count} операций",
            }
        )
    except Exception as e:
        data_logger.error(
            f"[TREASURY] Error fetching treasury for clan {clan_id}: {str(e)}"
        )
        return jsonify(
            {
                "success": False,
                "error": str(e),
                "message": "Ошибка при импорте. Возможно, требуется авторизация на сайте.",
            }
        ), 500


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/cookies/save", methods=["POST"])
@require_permission("treasury", "admin")
def save_treasury_cookies(clan_id):
    from urllib.parse import unquote

    data = request.json
    cookies_str = data.get("cookies", "").strip()

    if not cookies_str:
        return jsonify(
            {"success": False, "error": "Cookies не могут быть пустыми"}
        ), 400

    data_logger.info(f"[COOKIES] Saving cookies for clan {clan_id}")

    session = requests.Session()
    for part in cookies_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            value = unquote(value.strip())
            session.cookies.set(key, value)
            data_logger.info(f"[COOKIES] Set cookie: {key}={value[:30]}...")

    try:
        test_html, _ = fetch_clan_treasury_report(session=session, page=0)
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка проверки: {str(e)}"}), 500

    data_logger.info(f"[COOKIES] Validation response: {len(test_html)} bytes")

    is_valid = not is_login_redirect(test_html)

    if not is_valid:
        if "single_top_redirect" in test_html:
            redirect_match = __import__("re").search(
                r'single_top_redirect\(["\']([^"\']+)["\']\)', test_html
            )
            redirect_url = redirect_match.group(1) if redirect_match else "unknown"
            data_logger.warning(f"[COOKIES] Server redirect to: {redirect_url}")

    existing = ClanCookie.query.filter_by(clan_id=clan_id).first()
    if existing:
        existing.cookie_string = cookies_str
        existing.is_valid = is_valid
        existing.updated_at = datetime.utcnow()
        data_logger.info(
            f"[COOKIES] Updated cookies for clan {clan_id}, valid={is_valid}"
        )
    else:
        new_cookie = ClanCookie(
            clan_id=clan_id,
            cookie_string=cookies_str,
            is_valid=is_valid,
        )
        db.session.add(new_cookie)
        data_logger.info(
            f"[COOKIES] Created cookies for clan {clan_id}, valid={is_valid}"
        )

    db.session.commit()

    if is_valid:
        return jsonify({"success": True, "message": "Cookies сохранены и валидны"})
    else:
        return jsonify(
            {
                "success": False,
                "error": "session_expired",
                "message": "Сессия истекла. Войдите в игру заново на dwar.ru, затем скопируйте свежие cookies.",
            }
        )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/cookies/status", methods=["GET"])
@require_permission("clan_info", "read")
def get_treasury_cookies_status(clan_id):
    cookie = ClanCookie.query.filter_by(clan_id=clan_id).first()

    if not cookie:
        return jsonify({"has_cookies": False})

    return jsonify(
        {
            "has_cookies": True,
            "is_valid": cookie.is_valid,
            "updated_at": cookie.updated_at.isoformat() if cookie.updated_at else None,
        }
    )


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/auto-fetch-json", methods=["POST"]
)
@require_permission("treasury", "admin")
def auto_fetch_treasury_json(clan_id):
    """JSON-based fetch for optimized range imports (no SSE)."""
    from urllib.parse import unquote

    cookie = ClanCookie.query.filter_by(clan_id=clan_id).first()
    if not cookie or not cookie.is_valid:
        return jsonify(
            {
                "success": False,
                "error": "no_valid_cookies",
                "message": "Нет валидных cookies.",
            }
        )

    data = request.json or {}
    start_date = data.get("start_date", "01.01.2025")
    end_date = data.get("end_date")
    start_page = data.get("start_page", 0)
    end_page = data.get("end_page")

    data_logger.info(
        f"[TREASURY] JSON fetch: start_date={start_date}, end_date={end_date}, pages={start_page}-{end_page}"
    )

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    for part in cookie.cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            session.cookies.set(key.strip(), unquote(value.strip()))

    all_operations = []
    pages_fetched = 0

    # Ensure start_page <= end_page
    if start_page is not None and end_page is not None and start_page > end_page:
        start_page, end_page = end_page, start_page

    loop_start = start_page if start_page is not None and start_page > 0 else 0
    loop_end = end_page if end_page is not None else 500
    cutoff_comparable = _date_str_to_comparable(start_date)
    end_comparable = _date_str_to_comparable(end_date) if end_date else None

    # Never walk past the learned boundary: the pages there are empty and the
    # caller would get an unexplained "0 operations, success" result.
    window = get_source_window(clan_id)
    boundary = (window.oldest_date or "") if window else ""
    boundary_day = _date_str_to_comparable(boundary)
    range_trimmed = False
    if boundary_day and cutoff_comparable and cutoff_comparable < boundary_day:
        if end_comparable and end_comparable < boundary_day:
            return jsonify(_source_unavailable(boundary))
        cutoff_comparable = boundary_day
        start_date = boundary
        range_trimmed = True
        data_logger.info(
            f"[TREASURY] Fetch start trimmed to {boundary} (learned boundary)"
        )

    data_logger.info(f"[TREASURY] Fetch loop: pages {loop_start} to {loop_end}")

    # A page that parses to zero operations used to end the walk silently: the
    # caller got success:true, a short list and no explanation. Record WHY the
    # walk stopped and say it out loud in the response.
    empty_page = None
    tiny_answer_page = None

    for page in range(loop_start, loop_end):
        try:
            html, session = fetch_clan_treasury_report(session=session, page=page)
        except Exception as e:
            return jsonify(
                {"success": False, "error": f"Ошибка на странице {page}: {str(e)}"}
            )

        if is_login_redirect(html):
            cookie.is_valid = False
            db.session.commit()
            return jsonify(
                {
                    "success": False,
                    "error": "session_expired",
                    "message": "Сессия истекла",
                }
            )

        # A real report page is ~40-95 KB; a stub means the source answered
        # with something that is not a report (dead session, maintenance).
        if len(html) < 1000:
            tiny_answer_page = page
            data_logger.warning(
                f"[TREASURY] Page {page}: suspiciously small answer "
                f"({len(html)} chars), stopping"
            )
            break

        page_ops = parse_clan_treasury_operations(html)
        if not page_ops:
            empty_page = page
            data_logger.warning(
                f"[TREASURY] Page {page}: no operations parsed, stopping"
            )
            break

        latest_on_page = max(
            (_op_date_day(op["date"]) for op in page_ops), default=""
        )
        earliest_on_page = min(
            (_op_date_day(op["date"]) for op in page_ops), default=""
        )

        data_logger.info(
            f"[TREASURY] Page {page}: {len(page_ops)} ops, latest={latest_on_page}, earliest={earliest_on_page}, "
            f"cutoff={cutoff_comparable}, end={end_comparable}"
        )

        # Early exit: ALL ops on this page are older than start_date
        if latest_on_page and latest_on_page < cutoff_comparable:
            data_logger.info(
                f"[TREASURY] Page {page}: latest {latest_on_page} < start {cutoff_comparable}, stopping"
            )
            break

        # Filter ops within [start_date, end_date]
        filtered = [
            op
            for op in page_ops
            if _op_in_range(_op_date_day(op["date"]), cutoff_comparable, end_comparable)
        ]
        data_logger.info(f"[TREASURY] Page {page}: {len(filtered)} ops in range")
        all_operations.extend(filtered)
        pages_fetched += 1

    # A page short of the last requested one means the walk was cut short —
    # the report simply ending is the only harmless case.
    stopped_early = False
    warning = None
    if tiny_answer_page is not None:
        stopped_early = True
        warning = (
            f"Источник вернул пустой ответ на странице {tiny_answer_page} — сбор прерван, "
            "данные могут быть неполными. Повторите сбор."
        )
    elif empty_page is not None and empty_page < loop_end - 1:
        stopped_early = True
        warning = (
            f"Страница {empty_page} не содержит операций — сбор прерван раньше конца "
            "диапазона, данные могут быть неполными. Повторите сбор."
        )

    message = (
        f"Собрано {len(all_operations)} операций со {pages_fetched} страниц"
        + (
            f" (начало обрезано до {boundary}: более ранние данные в источнике удалены)"
            if range_trimmed and boundary
            else ""
        )
    )
    if warning:
        message = f"{message}. {warning}"

    return jsonify(
        {
            "success": True,
            "operations": all_operations,
            "pages_fetched": pages_fetched,
            "trimmed": range_trimmed,
            "stopped_early": stopped_early,
            "warning": warning,
            "oldest_available_date": boundary or None,
            "message": message,
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/auto-fetch", methods=["POST"])
@require_permission("clan_info", "admin")
def auto_fetch_treasury(clan_id):
    from urllib.parse import unquote

    cookie = ClanCookie.query.filter_by(clan_id=clan_id).first()
    if not cookie or not cookie.is_valid:
        return jsonify(
            {
                "success": False,
                "error": "no_valid_cookies",
                "message": "Нет валидных cookies. Сохраните cookies перед авто-импортом.",
            }
        )

    data_logger.info(f"[TREASURY] Auto-fetch starting for clan {clan_id}")

    session = requests.Session()
    for part in cookie.cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            session.cookies.set(key.strip(), unquote(value.strip()))

    result = fetch_all_pages_until_date(
        session, cutoff_date_str="01.01.2025", max_pages=500
    )

    if not result["success"]:
        data_logger.warning(
            f"[TREASURY] Auto-fetch failed for clan {clan_id}: {result['stopped_reason']}"
        )

        if result["stopped_reason"] == "session_expired":
            if cookie:
                cookie.is_valid = False
                db.session.commit()

        return jsonify(
            {
                "success": False,
                "error": result["stopped_reason"],
                "message": result.get("error", "Ошибка при сборе данных"),
                "operations": result["operations"],
                "pages_fetched": result["pages_fetched"],
            }
        )

    ops = result["operations"]

    date_range = {}
    if ops:
        dates = []
        for op in ops:
            m = __import__("re").match(r"(\d{2})\.(\d{2})\.(\d{4})", op["date"])
            if m:
                dates.append(f"{m.group(3)}-{m.group(2)}-{m.group(1)}")
        if dates:
            date_range = {"earliest": min(dates), "latest": max(dates)}

    data_logger.info(
        f"[TREASURY] Auto-fetch completed for clan {clan_id}: {len(ops)} ops from {result['pages_fetched']} pages"
    )

    return jsonify(
        {
            "success": True,
            "operations": ops,
            "pages_fetched": result["pages_fetched"],
            "date_range": date_range,
            "message": f"Собрано {len(ops)} операций со {result['pages_fetched']} страниц",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/estimate", methods=["POST"])
@require_permission("treasury", "admin")
def estimate_treasury_pages(clan_id):
    """Binary search to estimate page count in a date range before import."""
    from urllib.parse import unquote

    cookie = ClanCookie.query.filter_by(clan_id=clan_id).first()
    if not cookie or not cookie.is_valid:
        return jsonify(
            {
                "success": False,
                "error": "no_valid_cookies",
                "message": "Нет валидных cookies.",
            }
        )

    data = request.json or {}
    start_date = data.get("start_date", "01.01.2025")
    end_date = data.get("end_date")

    data_logger.info(
        f"[TREASURY] Estimating pages for clan {clan_id}: {start_date} to {end_date}"
    )

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
    )
    for part in cookie.cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            session.cookies.set(key.strip(), unquote(value.strip()))

    # A range older than the learned boundary cannot be served: dwars report
    # simply ends there. Answer plainly instead of returning "1 page" that
    # later yields an empty, unexplained import.
    requested_start_date = start_date
    window = get_source_window(clan_id)
    boundary = (window.oldest_date or "") if window else ""
    boundary_day = _date_str_to_comparable(boundary)
    requested_start_day = _date_str_to_comparable(start_date)
    end_comparable_req = _date_str_to_comparable(end_date) if end_date else ""
    trimmed = False

    if boundary_day and requested_start_day and requested_start_day < boundary_day:
        if end_comparable_req and end_comparable_req < boundary_day:
            # Entirely older than the learned window: answer without bothering
            # the source.
            return jsonify(_source_unavailable(boundary))
        # Partially older than the boundary. The boundary is LEARNED state and
        # can be wrong (a too-new value once froze every older period), so ask
        # the source with the ORIGINAL start first: a saturated answer reports
        # the true end of the history and corrects the boundary below, and only
        # then is the start trimmed.
        data_logger.info(
            f"[TREASURY] Requested start {start_date} predates boundary {boundary}: "
            "probing the source before trimming"
        )

    result = estimate_pages_in_range(session, start_date, end_date)

    if "error" in result:
        return jsonify(
            {
                "success": False,
                "error": result["error"],
                "message": result.get("message", ""),
            }
        )

    # Learn / refresh the boundary from what the report actually contains —
    # but ONLY from a saturated search. `oldest_page_earliest` is the oldest
    # operation *inside the requested range*; for a narrow recent range that is
    # simply the range's own start, and learning it froze the window at
    # 30.09.2026 after single-day estimates (the boundary only moved forward,
    # so every older period became un-importable).
    #
    # Saturated means: the caller asked for something older than everything the
    # report holds (requested start < the oldest date found) AND the binary
    # search parked on the report's last page. Such a run reports the true end
    # of the history, so it may also correct a boundary that is too new.
    sample_dates = result.get("sample_dates") or {}
    report_oldest_day = (sample_dates.get("oldest_page_earliest") or "")[:8]
    report_oldest_date = _day_to_display(report_oldest_day)
    total_pages = result.get("total_pages") or 0
    last_page = (total_pages - 1) if total_pages else None
    saturated = (
        bool(report_oldest_day)
        and bool(requested_start_day)
        and requested_start_day < report_oldest_day
        and last_page is not None
        and result.get("end_page") == last_page
    )
    if saturated and report_oldest_day != boundary_day:
        remember_source_window(clan_id, report_oldest_date, result.get("total_pages"))
        boundary, boundary_day = report_oldest_date, report_oldest_day

    # If the requested start predates the boundary just learned, the page range
    # above describes a period the source no longer has. Redo the estimate
    # against the boundary so the caller receives a range it can import —
    # otherwise the answer is honest ("data starts later") but useless.
    if boundary_day and requested_start_day and requested_start_day < boundary_day:
        if end_comparable_req and end_comparable_req < boundary_day:
            return jsonify(_source_unavailable(boundary))
        trimmed = True
        start_date = boundary
        data_logger.info(
            f"[TREASURY] Re-estimating from learned boundary {boundary}"
        )
        result = estimate_pages_in_range(session, start_date, end_date)
        if "error" in result:
            return jsonify(
                {
                    "success": False,
                    "error": result["error"],
                    "message": result.get("message", ""),
                }
            )
        sample_dates = result.get("sample_dates") or {}

    estimated = result.get("estimated_pages", 0)
    if estimated <= 0:
        return jsonify(_source_unavailable(boundary))

    return jsonify(
        {
            "success": True,
            "start_page": result["start_page"],
            "end_page": result["end_page"],
            "estimated_pages": estimated,
            "total_pages": result["total_pages"],
            "sample_dates": sample_dates,
            "requested_start_date": requested_start_date,
            "effective_start_date": start_date,
            "trimmed": trimmed,
            "oldest_available_date": boundary or None,
            "message": (
                f"~{estimated} страниц в диапазоне {start_date}–{end_date or 'сейчас'}"
                + (
                    f" (начало обрезано до {boundary}: более ранние данные в источнике удалены)"
                    if trimmed and boundary
                    else ""
                )
            ),
        }
    )


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/auto-fetch-stream", methods=["GET"]
)
def auto_fetch_treasury_stream(clan_id):
    from flask import Response, request
    from urllib.parse import unquote
    import json
    from shared.rbac.models import SessionToken
    from shared.models.user import User
    from datetime import datetime, timezone

    # Auth via query param (for SSE) or standard header
    token = request.args.get("token") or request.headers.get(
        "Authorization", ""
    ).replace("Bearer ", "")
    current_user = None
    if token:
        session_token = SessionToken.find_by_token(token)
        if session_token:
            expires = session_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(timezone.utc):
                current_user = User.query.get(session_token.user_id)

    if not current_user or get_user_permission(current_user, "treasury", "admin") == "none":

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "forbidden",
                        "message": "Недостаточно прав",
                    }
                )
                + "\n\n"
            )

        return Response(error_gen(), mimetype="text/event-stream")

    cookie = ClanCookie.query.filter_by(clan_id=clan_id).first()
    if not cookie or not cookie.is_valid:

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "no_valid_cookies",
                        "message": "Нет валидных cookies",
                    }
                )
                + "\n\n"
            )

        return Response(error_gen(), mimetype="text/event-stream")

    data_logger.info(f"[TREASURY] SSE auto-fetch starting for clan {clan_id}")

    start_date = request.args.get("start_date", "01.01.2025")
    end_date = request.args.get("end_date", None)
    start_page = int(request.args.get("start_page", 0))
    end_page = request.args.get("end_page", None)
    if end_page is not None:
        end_page = int(end_page)
    total_pages_override = request.args.get("total_pages", None)
    if total_pages_override is not None:
        total_pages_override = int(total_pages_override)
    data_logger.info(
        f"[TREASURY] SSE start_date={start_date}, end_date={end_date}, start_page={start_page}, end_page={end_page}"
    )

    def generate():
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )
        for part in cookie.cookie_string.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                session.cookies.set(key.strip(), unquote(value.strip()))

        try:
            for event_type, data in fetch_all_pages_streaming(
                session,
                cutoff_date_str=start_date,
                end_date_str=end_date,
                max_pages=500,
                start_page=start_page,
                end_page=end_page,
                total_pages_override=total_pages_override,
            ):
                payload = {"type": event_type}
                payload.update(data)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            data_logger.warning("[TREASURY] SSE generator interrupted")
        except Exception as e:
            data_logger.error(
                f"[TREASURY] SSE generator error: {str(e)}", exc_info=True
            )
            error_payload = {
                "type": "error",
                "reason": "generator_error",
                "message": str(e),
            }
            yield f"data: {json.dumps(error_payload)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# =============================================================================
# Membership import endpoints
# =============================================================================


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/members/auto-fetch-stream", methods=["GET"]
)
def auto_fetch_members_stream(clan_id):
    from flask import Response, request
    from urllib.parse import unquote
    import json
    from shared.rbac.models import SessionToken
    from shared.models.user import User
    from datetime import datetime, timezone

    token = request.args.get("token") or request.headers.get(
        "Authorization", ""
    ).replace("Bearer ", "")
    current_user = None
    if token:
        session_token = SessionToken.find_by_token(token)
        if session_token:
            expires = session_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(timezone.utc):
                current_user = User.query.get(session_token.user_id)

    if not current_user or get_user_permission(current_user, "clan_info", "admin") == "none":

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "forbidden",
                        "message": "Недостаточно прав",
                    }
                )
                + "\n\n"
            )

        return Response(error_gen(), mimetype="text/event-stream")

    cookie = ClanCookie.query.filter_by(clan_id=clan_id).first()
    if not cookie or not cookie.is_valid:

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "no_valid_cookies",
                        "message": "Нет валидных cookies",
                    }
                )
                + "\n\n"
            )

        return Response(error_gen(), mimetype="text/event-stream")

    # Capture DB data INSIDE app context before returning Response
    db_members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).all()
    db_nicks = {m.nick.lower() for m in db_members}

    data_logger.info(f"[MEMBERSHIP] SSE auto-fetch starting for clan {clan_id}")

    def generate():
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )
        for part in cookie.cookie_string.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                session.cookies.set(key.strip(), unquote(value.strip()))

        # Phase 1: Diff
        try:
            html = fetch_clan_management_page(session, clan_id)
        except Exception as e:
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "fetch_error",
                        "message": f"Ошибка: {str(e)}",
                    }
                )
                + "\n\n"
            )
            return

        if is_login_redirect(html):
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "session_expired",
                        "message": "Сессия истекла, обновите cookies",
                    }
                )
                + "\n\n"
            )
            return

        fetched_members = parse_clan_members_from_management(html, clan_id)
        fetched_nicks = {m["nick"].lower() for m in fetched_members}

        # Build a lookup of existing members for join_date check
        db_member_map = {m.nick.lower(): m for m in db_members}

        joined = []
        needs_update = []
        for m in fetched_members:
            nick_lower = m["nick"].lower()
            if nick_lower not in db_nicks:
                joined.append(m)
            else:
                # Existing member — check if join_date is missing
                db_m = db_member_map.get(nick_lower)
                if db_m and not db_m.join_date and m.get("join_date"):
                    needs_update.append(m)

        left = [m for m in db_members if m.nick.lower() not in fetched_nicks]

        yield (
            "data: "
            + json.dumps(
                {
                    "type": "diff",
                    "joined": joined,
                    "needs_update": needs_update,
                    "left": [
                        {
                            "nick": m.nick,
                            "last_seen_level": m.level,
                            "last_seen_role": m.clan_role,
                        }
                        for m in left
                    ],
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

        # Phase 2: History
        for event_type, data in fetch_all_history_pages_streaming(
            session, clan_id, cutoff_date_str="01.01.2025", max_pages=100
        ):
            payload = {"type": event_type}
            payload.update(data)
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/members/diff-import", methods=["POST"])
@require_permission("clan_info", "admin")
def import_member_diff(clan_id):
    from flask import g

    data = request.json
    joined_list = data.get("joined", [])
    left_list = data.get("left", [])

    # Enforce "exactly one Глава Ордена per active roster" at import time.
    # Without this, a single bad import can mark many members as leader.
    # Existing leaders are accepted as-is; new leaders require no other
    # active leader in the same import batch and no other active leader
    # already in the DB. The check is batch-aware: we count leaders in
    # joined_list first, then any remaining conflicts fail the import.
    HEAD_ROLE = "Глава Ордена"
    batch_leaders: set[str] = set()
    for m in joined_list:
        nr = (m.get("clan_role") or "").strip()
        if nr == HEAD_ROLE:
            nick = (m.get("nick") or "").strip()
            if nick:
                batch_leaders.add(nick.lower())
    if batch_leaders:
        existing_leaders = (
            ClanMemberInfo.query.filter_by(
                clan_id=clan_id, is_deleted=False, clan_role=HEAD_ROLE
            ).with_entities(ClanMemberInfo.nick).all()
        )
        db_leaders = {n[0].lower() for n in existing_leaders if n[0]}
        # A new leader in the batch is allowed iff it is the only leader
        # in (DB ∪ batch) — i.e. exactly one distinct nick across both.
        all_leaders = db_leaders | batch_leaders
        if len(all_leaders) > 1:
            return jsonify(
                {
                    "success": False,
                    "joined_count": 0,
                    "left_count": 0,
                    "errors": [
                        "Несколько глав клана: "
                        + ", ".join(sorted(all_leaders))
                        + ". Оставьте одного."
                    ],
                    "message": "Импорт отклонён: несколько глав в одном клане.",
                }
            ), 400

    data_logger.info(
        f"[MEMBERSHIP] Diff import for clan {clan_id}: joined={len(joined_list)}, left={len(left_list)}"
    )

    joined_count = 0
    left_count = 0
    errors = []
    today = datetime.now().strftime("%d.%m.%Y")

    for member_data in joined_list:
        try:
            nick = member_data.get("nick", "").strip()
            if not nick:
                errors.append("Пустой ник в joined")
                continue
            if len(nick) > 100:
                errors.append(
                    f"Ник слишком длинный ({len(nick)} символов): {nick[:30]}..."
                )
                continue

            existing = ClanMemberInfo.query.filter_by(
                clan_id=clan_id, nick=nick
            ).first()
            join_date = _clip(member_data.get("join_date"), 20) or today
            if existing:
                # Re-join of a previously left member: resurrect instead of
                # inserting a second row for the same nick.
                existing.is_deleted = False
                existing.left_date = ""
                existing.leave_reason = ""
                if not existing.join_date:
                    existing.join_date = join_date
                if not existing.trial_until and member_data.get("trial_until"):
                    existing.trial_until = _clip(member_data.get("trial_until"), 20)
                data_logger.debug(
                    f"[MEMBERSHIP] Joined member {nick} already exists, updated join_date={existing.join_date}"
                )
                event = ClanMembershipEvent(
                    clan_id=clan_id,
                    nick=nick,
                    event_type="joined",
                    event_date=join_date,
                    source="diff",
                )
                db.session.add(event)
                joined_count += 1
                continue

            member = ClanMemberInfo(
                clan_id=clan_id,
                nick=nick,
                icon=_clip(member_data.get("icon"), 10),
                game_rank=_clip(member_data.get("game_rank"), 100),
                level=_as_int(member_data.get("level"), 1),
                profession=_clip(member_data.get("profession"), 100),
                profession_level=_as_int(member_data.get("profession_level"), 0),
                clan_role=_clip(member_data.get("clan_role"), 100) or "Рыцарь Ордена",
                join_date=join_date,
                trial_until=_clip(member_data.get("trial_until"), 20),
            )
            db.session.add(member)

            event = ClanMembershipEvent(
                clan_id=clan_id,
                nick=nick,
                event_type="joined",
                event_date=join_date,
                source="diff",
            )
            db.session.add(event)
            joined_count += 1
        except Exception as e:
            errors.append(f"Ошибка добавления {member_data.get('nick', '?')}: {str(e)}")

    for left_data in left_list:
        try:
            nick = left_data.get("nick", "").strip()
            if not nick:
                errors.append("Пустой ник в left")
                continue

            member = ClanMemberInfo.query.filter_by(
                clan_id=clan_id, nick=nick, is_deleted=False
            ).first()
            if not member:
                data_logger.debug(
                    f"[MEMBERSHIP] Left member {nick} not found in DB, skipping"
                )
                continue

            member.is_deleted = True
            left_date = _clip(left_data.get("left_date"), 20) or today
            leave_reason = _clip(left_data.get("leave_reason"), 200)
            member.left_date = left_date
            member.leave_reason = leave_reason

            event = ClanMembershipEvent(
                clan_id=clan_id,
                nick=nick,
                event_type="left",
                event_date=left_date,
                source="diff",
                leave_reason=leave_reason,
            )
            db.session.add(event)
            left_count += 1
        except Exception as e:
            errors.append(f"Ошибка удаления {left_data.get('nick', '?')}: {str(e)}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        data_logger.error(f"[MEMBERSHIP] Diff import commit failed: {e}")
        return jsonify(
            {
                "success": False,
                "joined_count": 0,
                "left_count": 0,
                "errors": errors + [f"Ошибка записи в БД: {e}"],
                "message": f"Не удалось сохранить изменения: {e}",
            }
        ), 400

    data_logger.info(
        f"[MEMBERSHIP] Diff import completed: joined={joined_count}, left={left_count}, errors={len(errors)}"
    )

    return jsonify(
        {
            "success": True,
            "joined_count": joined_count,
            "left_count": left_count,
            "errors": errors,
            "message": f"Обработано {joined_count + left_count} изменений: {joined_count} вступил, {left_count} вышел",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/members/history-import", methods=["POST"])
@require_permission("clan_info", "admin")
def import_history_events(clan_id):
    from flask import g

    data = request.json
    events_list = data.get("events", [])

    data_logger.info(
        f"[MEMBERSHIP] History import for clan {clan_id}: {len(events_list)} events"
    )

    processed = 0
    skipped = 0
    errors = []

    for event_data in events_list:
        try:
            nick = _clip(event_data.get("nick"), 100)
            event_type = _clip(event_data.get("event_type"), 10)
            event_date = _clip(event_data.get("event_date"), 20)

            if not nick or not event_type or not event_date:
                errors.append(
                    f"Пропущено: nick={nick}, type={event_type}, date={event_date}"
                )
                skipped += 1
                continue

            existing_event = ClanMembershipEvent.query.filter_by(
                clan_id=clan_id,
                nick=nick,
                event_type=event_type,
                event_date=event_date,
            ).first()
            if existing_event:
                skipped += 1
                continue

            event = ClanMembershipEvent(
                clan_id=clan_id,
                nick=nick,
                event_type=event_type,
                event_date=event_date,
                source="history",
                leave_reason=_clip(event_data.get("leave_reason"), 200),
            )
            db.session.add(event)

            if event_type == "joined":
                member = ClanMemberInfo.query.filter_by(
                    clan_id=clan_id, nick=nick
                ).first()
                if member:
                    if not member.join_date:
                        member.join_date = event_date
                    member.is_deleted = False
                    member.left_date = ""
                    member.leave_reason = ""
                else:
                    member = ClanMemberInfo(
                        clan_id=clan_id,
                        nick=nick,
                        level=_as_int(event_data.get("level"), 1),
                        clan_role="Рыцарь Ордена",
                        join_date=event_date,
                    )
                    db.session.add(member)

            elif event_type == "left":
                member = ClanMemberInfo.query.filter_by(
                    clan_id=clan_id, nick=nick, is_deleted=False
                ).first()
                if member:
                    member.is_deleted = True
                    member.left_date = event_date
                    member.leave_reason = event_data.get("leave_reason", "")

            processed += 1
        except Exception as e:
            errors.append(f"Ошибка обработки {event_data.get('nick', '?')}: {str(e)}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        data_logger.error(f"[MEMBERSHIP] History import commit failed: {e}")
        return jsonify(
            {
                "success": False,
                "processed_count": 0,
                "skipped_count": skipped,
                "errors": errors + [f"Ошибка записи в БД: {e}"],
                "message": f"Не удалось сохранить историю: {e}",
            }
        ), 400

    data_logger.info(
        f"[MEMBERSHIP] History import completed: processed={processed}, skipped={skipped}, errors={len(errors)}"
    )

    return jsonify(
        {
            "success": True,
            "processed_count": processed,
            "skipped_count": skipped,
            "errors": errors,
            "message": f"Обработано {processed} событий из истории",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/members/events", methods=["GET"])
@require_permission("clan_info", "read")
def get_membership_events(clan_id):
    source = request.args.get("source")
    event_type = request.args.get("event_type")

    query = ClanMembershipEvent.query.filter_by(clan_id=clan_id)
    if source:
        query = query.filter_by(source=source)
    if event_type:
        query = query.filter_by(event_type=event_type)

    events = query.order_by(ClanMembershipEvent.id.desc()).all()

    return jsonify(
        [
            {
                "id": e.id,
                "nick": e.nick,
                "event_type": e.event_type,
                "event_date": e.event_date,
                "source": e.source,
                "leave_reason": e.leave_reason,
                "synced": e.synced,
                "created_at": e.created_at.isoformat() if e.created_at else "",
            }
            for e in events
        ]
    )


# =============================================================================
# Level change events endpoints
# =============================================================================


@clan_info_bp.route(
    "/api/clan/<int:clan_id>/level-events/import-stream", methods=["GET"]
)
def import_level_events_stream(clan_id):
    from flask import Response, request
    from urllib.parse import unquote
    import json

    token = request.args.get("token") or request.headers.get(
        "Authorization", ""
    ).replace("Bearer ", "")
    current_user = None
    if token:
        from shared.rbac.models import SessionToken
        from shared.models.user import User
        from datetime import datetime, timezone

        session_token = SessionToken.find_by_token(token)
        if session_token:
            expires = session_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(timezone.utc):
                current_user = User.query.get(session_token.user_id)

    if not current_user or get_user_permission(current_user, "clan_info", "admin") == "none":

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "forbidden",
                        "message": "Недостаточно прав",
                    }
                )
                + "\n\n"
            )

        return Response(error_gen(), mimetype="text/event-stream")

    cookie = ClanCookie.query.filter_by(clan_id=clan_id).first()
    if not cookie or not cookie.is_valid:

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "no_valid_cookies",
                        "message": "Нет валидных cookies",
                    }
                )
                + "\n\n"
            )

        return Response(error_gen(), mimetype="text/event-stream")

    data_logger.info(f"[LEVEL] SSE level events import starting for clan {clan_id}")

    def generate():
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )
        for part in cookie.cookie_string.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                session.cookies.set(key.strip(), unquote(value.strip()))

        for event_type, data in fetch_level_events_streaming(
            session, clan_id=clan_id, max_pages=500
        ):
            payload = {"type": event_type}
            payload.update(data)
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/level-events/save", methods=["POST"])
@require_permission("clan_info", "admin")
def save_level_events(clan_id):
    data = request.json
    events = data.get("events", [])

    imported = 0
    skipped = 0

    for ev in events:
        existing = ClanLevelChangeEvent.query.filter_by(
            clan_id=clan_id,
            nick=ev["nick"],
            event_date=ev["event_date"],
        ).first()

        if existing:
            skipped += 1
            continue

        new_event = ClanLevelChangeEvent(
            clan_id=clan_id,
            nick=ev["nick"],
            old_level=ev.get("old_level", 0),
            new_level=ev["new_level"],
            event_date=ev["event_date"],
        )
        db.session.add(new_event)
        imported += 1

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "message": f"Импортировано {imported}, пропущено {skipped}",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/level-events", methods=["GET"])
@require_permission("clan_info", "read")
def get_level_events(clan_id):
    events = (
        ClanLevelChangeEvent.query.filter_by(clan_id=clan_id)
        .order_by(ClanLevelChangeEvent.event_date.desc())
        .all()
    )

    return jsonify(
        [
            {
                "id": e.id,
                "nick": e.nick,
                "old_level": e.old_level,
                "new_level": e.new_level,
                "event_date": e.event_date,
                "created_at": e.created_at.isoformat() if e.created_at else "",
            }
            for e in events
        ]
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/level-history", methods=["GET"])
@require_permission("clan_info", "read")
def get_level_history(clan_id):
    """Return level history organized by player for tax norm calculation."""
    events = (
        ClanLevelChangeEvent.query.filter_by(clan_id=clan_id)
        .order_by(ClanLevelChangeEvent.event_date.asc())
        .all()
    )

    # Group by player
    history = {}
    for e in events:
        nick_lower = e.nick.lower()
        if nick_lower not in history:
            history[nick_lower] = []
        history[nick_lower].append(
            {
                "date": e.event_date,
                "old_level": e.old_level,
                "new_level": e.new_level,
            }
        )

    return jsonify(history)
