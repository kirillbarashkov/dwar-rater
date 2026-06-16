from flask import Blueprint, request, jsonify
from datetime import datetime
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
)
from shared.services.data_logger import data_logger
from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    ClanMemberInfo,
    TreasuryOperation,
    ClanCookie,
    ClanMembershipEvent,
    ClanLevelChangeEvent,
)
from shared.rbac import require_permission, feature, Permission as PermDef


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


LEADER_ROLE = "Глава Ордена"
DEPUTY_ROLE = "Зам. Главы"
COUNCIL_ROLE = "Совесть"
COMMANDER_ROLE = "Воевода"

DEFAULT_COUNCIL_SLOTS = 4
CLAN_MAX_PLAYERS = 70


def build_clan_structure_from_members(clan_id, existing_structure=None):
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).all()

    leaders = [m for m in members if m.clan_role == LEADER_ROLE]
    deputies = [m for m in members if m.clan_role == DEPUTY_ROLE]
    council = [m for m in members if m.clan_role == COUNCIL_ROLE]
    commanders = [m for m in members if m.clan_role == COMMANDER_ROLE]

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

    if deputies:
        structure["deputies"] = [
            {"nick": d.nick, "description": d.clan_role} for d in deputies
        ]

    if council:
        structure["council"] = [
            {"nick": c.nick, "description": c.clan_role} for c in council
        ]

    if commanders:
        structure["commander"] = {
            "nick": commanders[0].nick,
            "description": commanders[0].clan_role,
        }

    if existing_structure:
        if "council" in existing_structure and "council" not in structure:
            valid_council = []
            for c in existing_structure["council"]:
                nick = c.get("nick", "")
                if any(m.nick == nick for m in members):
                    valid_council.append(c)
            if valid_council:
                structure["council"] = valid_council

        if "commander" in existing_structure and "commander" not in structure:
            cmd_nick = existing_structure["commander"].get("nick", "")
            if cmd_nick and any(m.nick == cmd_nick for m in members):
                structure["commander"] = existing_structure["commander"]

        if "council_slots" in existing_structure:
            structure["council_slots"] = existing_structure["council_slots"]

    other_count = len(
        [
            m
            for m in members
            if m.clan_role
            not in (LEADER_ROLE, DEPUTY_ROLE, COUNCIL_ROLE, COMMANDER_ROLE)
        ]
    )
    structure["has_members"] = other_count > 0

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
    from flask import g

    if not g.current_user or g.current_user.role != "admin":
        data_logger.warning(f"[IMPORT] Unauthorized import attempt for clan {clan_id}")
        return jsonify(
            {"error": "Только администратор может импортировать участников"}
        ), 403

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
@require_permission("clan_info", "admin")
def restore_treasury_backup(clan_id):
    from flask import g

    if not g.current_user or g.current_user.role != "admin":
        return jsonify(
            {"error": "Только администратор может восстанавливать бэкапы"}
        ), 403

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
@require_permission("clan_info", "admin")
def update_treasury_operation(clan_id, operation_id):
    from flask import g

    if not g.current_user or g.current_user.role != "admin":
        return jsonify({"error": "Только администратор может изменять операции"}), 403

    operation = TreasuryOperation.query.filter_by(
        id=operation_id, clan_id=clan_id
    ).first()
    if not operation:
        return jsonify({"error": "Операция не найдена"}), 404

    data = request.json

    if "quantity" in data:
        operation.quantity = int(data["quantity"])
    if "compensation_flag" in data:
        operation.compensation_flag = bool(data["compensation_flag"])
    if "compensation_comment" in data:
        operation.compensation_comment = data["compensation_comment"]

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


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/compensation", methods=["POST"])
@require_permission("clan_info", "admin")
def create_treasury_compensation(clan_id):
    from flask import g

    if not g.current_user or g.current_user.role != "admin":
        return jsonify(
            {"error": "Только администратор может создавать компенсации"}
        ), 403

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


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/import", methods=["POST"])
@require_permission("clan_info", "admin")
def import_treasury_operations(clan_id):
    from flask import g

    if not g.current_user or g.current_user.role != "admin":
        data_logger.warning(
            f"[TREASURY] Unauthorized import attempt for clan {clan_id}"
        )
        return jsonify({"error": "Только администратор может импортировать казну"}), 403

    data = request.json
    operations_data = data.get("operations", [])
    replace = data.get("replace", False)

    data_logger.info(
        f"[TREASURY] Importing {len(operations_data)} operations for clan {clan_id} (replace={replace})"
    )

    if replace:
        TreasuryOperation.query.filter_by(clan_id=clan_id).delete()
        data_logger.info(f"[TREASURY] Cleared existing operations for clan {clan_id}")

    imported = 0
    updated = 0
    skipped = 0
    skip_reasons = []

    data_logger.info(
        f"[TREASURY] Processing {len(operations_data)} operations from frontend"
    )

    for i, op in enumerate(operations_data):
        try:
            date = op.get("date", "")
            nick = op.get("nick", "")
            operation_type = op.get("operation_type", "")
            object_name = op.get("object_name", "")
            quantity = op.get("quantity", 0)
            compensation_flag = op.get("compensation_flag", False)
            compensation_comment = op.get("compensation_comment", "")

            if not date or not nick:
                skip_reasons.append(f"op {i}: empty date or nick")
                skipped += 1
                continue

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

    db.session.commit()

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

    earliest = min(all_dates) if all_dates else None
    latest = max(all_dates) if all_dates else None

    return jsonify(
        {
            "years": sorted_coverage,
            "total_dates_with_data": len(set(all_dates)),
            "total_operations": total_ops,
            "earliest_date": earliest,
            "latest_date": latest,
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury", methods=["POST"])
@require_permission("clan_info", "admin")
def fetch_treasury_operations(clan_id):
    from flask import g

    if not g.current_user or g.current_user.role != "admin":
        data_logger.warning(f"[TREASURY] Unauthorized fetch attempt for clan {clan_id}")
        return jsonify({"error": "Только администратор может обновлять казну"}), 403

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
@require_permission("clan_info", "admin")
def save_treasury_cookies(clan_id):
    from flask import g
    from urllib.parse import unquote

    if not g.current_user or g.current_user.role != "admin":
        return jsonify({"error": "Только администратор может управлять cookies"}), 403

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
@require_permission("clan_info", "admin")
def auto_fetch_treasury_json(clan_id):
    """JSON-based fetch for optimized range imports (no SSE)."""
    from flask import g
    from urllib.parse import unquote

    if not g.current_user or g.current_user.role != "admin":
        return jsonify({"error": "Только администратор"}), 403

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
    loop_start = start_page if start_page > 0 else 0
    loop_end = end_page if end_page is not None else 500
    cutoff_comparable = _date_str_to_comparable(start_date)
    end_comparable = _date_str_to_comparable(end_date) if end_date else None

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

        page_ops = parse_clan_treasury_operations(html)
        if not page_ops:
            break

        latest_on_page = max(
            (_parse_date_to_comparable(op["date"]) for op in page_ops), default=""
        )

        if end_comparable and latest_on_page and latest_on_page < end_comparable:
            break
        if latest_on_page and latest_on_page < cutoff_comparable:
            break

        if end_comparable is not None:
            filtered = [
                op
                for op in page_ops
                if _parse_date_to_comparable(op["date"]) <= end_comparable
            ]
            all_operations.extend(filtered)
        else:
            all_operations.extend(page_ops)
        pages_fetched += 1

    return jsonify(
        {
            "success": True,
            "operations": all_operations,
            "pages_fetched": pages_fetched,
            "message": f"Собрано {len(all_operations)} операций со {pages_fetched} страниц",
        }
    )


@clan_info_bp.route("/api/clan/<int:clan_id>/treasury/auto-fetch", methods=["POST"])
@require_permission("clan_info", "admin")
def auto_fetch_treasury(clan_id):
    from flask import g
    from urllib.parse import unquote

    if not g.current_user or g.current_user.role != "admin":
        return jsonify(
            {"error": "Только администратор может запускать авто-импорт"}
        ), 403

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
@require_permission("clan_info", "admin")
def estimate_treasury_pages(clan_id):
    """Binary search to estimate page count in a date range before import."""
    from flask import g
    from urllib.parse import unquote

    if not g.current_user or g.current_user.role != "admin":
        return jsonify({"error": "Только администратор"}), 403

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

    result = estimate_pages_in_range(session, start_date, end_date)

    if "error" in result:
        return jsonify(
            {
                "success": False,
                "error": result["error"],
                "message": result.get("message", ""),
            }
        )

    return jsonify(
        {
            "success": True,
            "start_page": result["start_page"],
            "end_page": result["end_page"],
            "estimated_pages": result["estimated_pages"],
            "total_pages": result["total_pages"],
            "sample_dates": result["sample_dates"],
            "message": f"~{result['estimated_pages']} страниц в диапазоне {start_date}–{end_date or 'сейчас'}",
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
        session_token = SessionToken.query.filter_by(token=token).first()
        if session_token:
            expires = session_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(timezone.utc):
                current_user = User.query.get(session_token.user_id)

    if not current_user or current_user.role != "admin":

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "forbidden",
                        "message": "Только администратор",
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
        session_token = SessionToken.query.filter_by(token=token).first()
        if session_token:
            expires = session_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(timezone.utc):
                current_user = User.query.get(session_token.user_id)

    if not current_user or current_user.role != "admin":

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "forbidden",
                        "message": "Только администратор",
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

    if not g.current_user or g.current_user.role != "admin":
        return jsonify(
            {"error": "Только администратор может импортировать изменения"}
        ), 403

    data = request.json
    joined_list = data.get("joined", [])
    left_list = data.get("left", [])

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
                clan_id=clan_id, nick=nick, is_deleted=False
            ).first()
            if existing:
                # Update join_date if missing
                if not existing.join_date and member_data.get("join_date"):
                    existing.join_date = member_data["join_date"]
                if not existing.trial_until and member_data.get("trial_until"):
                    existing.trial_until = member_data["trial_until"]
                data_logger.debug(
                    f"[MEMBERSHIP] Joined member {nick} already exists, updated join_date={existing.join_date}"
                )
                continue

            member = ClanMemberInfo(
                clan_id=clan_id,
                nick=nick,
                icon=member_data.get("icon", ""),
                game_rank=member_data.get("game_rank", ""),
                level=member_data.get("level", 1),
                profession=member_data.get("profession", ""),
                profession_level=member_data.get("profession_level", 0),
                clan_role=member_data.get("clan_role", "Рыцарь Ордена"),
                join_date=member_data.get("join_date", today),
                trial_until=member_data.get("trial_until", ""),
            )
            db.session.add(member)

            event = ClanMembershipEvent(
                clan_id=clan_id,
                nick=nick,
                event_type="joined",
                event_date=member_data.get("join_date", today),
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
            member.left_date = left_data.get("left_date", today)
            member.leave_reason = left_data.get("leave_reason", "")

            event = ClanMembershipEvent(
                clan_id=clan_id,
                nick=nick,
                event_type="left",
                event_date=left_data.get("left_date", today),
                source="diff",
                leave_reason=left_data.get("leave_reason", ""),
            )
            db.session.add(event)
            left_count += 1
        except Exception as e:
            errors.append(f"Ошибка удаления {left_data.get('nick', '?')}: {str(e)}")

    db.session.commit()

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

    if not g.current_user or g.current_user.role != "admin":
        return jsonify(
            {"error": "Только администратор может импортировать историю"}
        ), 403

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
            nick = event_data.get("nick", "").strip()
            event_type = event_data.get("event_type", "")
            event_date = event_data.get("event_date", "")

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
                leave_reason=event_data.get("leave_reason", ""),
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
                        level=event_data.get("level", 1),
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

    db.session.commit()

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

        session_token = SessionToken.query.filter_by(token=token).first()
        if session_token:
            expires = session_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(timezone.utc):
                current_user = User.query.get(session_token.user_id)

    if not current_user or current_user.role != "admin":

        def error_gen():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "reason": "forbidden",
                        "message": "Только администратор",
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
