#!/usr/bin/env python3
"""todo CRUD CLI — 순수 one-shot. 대화 없음.

Usage:
    python3 todo_crud.py add --title "..." [--done-definition "..."] [--category ...] ...
    python3 todo_crud.py list [--status backlog] [--category 업무] [--sort default] [--fields id,title,...]
    python3 todo_crud.py show --id N
    python3 todo_crud.py edit --id N [--estimated-min N] [--parent-id N] [--project ...] ...
    python3 todo_crud.py move --id N --status wip [--reason "..."] [--force]
    python3 todo_crud.py defer --id N --reason "..."
    python3 todo_crud.py done --id N
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "mcp" / "life-dashboard"))
from db import (
    get_conn, upsert_todo, get_todo, get_todos, update_todo_status, upsert_project,
)


def _print_json(obj) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


def _positive_int(s: str) -> int:
    try:
        n = int(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a positive integer (got {s!r})")
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0 (got {n})")
    return n


def _resolve_project(conn, name: str, repo: str | None = None) -> int:
    """project name → id. 새로 생성될 때만 stderr로 [info] 로그."""
    existed = conn.execute(
        "SELECT 1 FROM projects WHERE name = ? AND repo IS ?", (name, repo)
    ).fetchone() is not None
    pid = upsert_project(conn, name, repo=repo)
    if not existed:
        print(f"[info] new project '{name}' created (id={pid})", file=sys.stderr)
    return pid


def cmd_add(args):
    if args.estimated_min is None and not args.skip_estimated:
        print("error: --estimated-min N or --skip-estimated required", file=sys.stderr)
        sys.exit(1)
    if args.estimated_min is not None and args.skip_estimated:
        print("error: --estimated-min and --skip-estimated are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    data = {
        "title": args.title,
        "done_definition": args.done_definition,
        "category": args.category,
        "priority": args.priority,
        "parent_id": args.parent_id,
        "quarter": args.quarter,
        "deadline": args.deadline,
        "estimated_min": args.estimated_min,
        "notes": args.notes,
    }
    conn = get_conn()
    try:
        if args.project:
            data["project_id"] = _resolve_project(conn, args.project, repo=args.repo)
        tid = upsert_todo(conn, data)
        conn.commit()
        _print_json(get_todo(conn, tid))
    except Exception as e:
        conn.rollback()
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_list(args):
    conn = get_conn()
    try:
        rows = get_todos(conn, status=args.status, category=args.category, sort=args.sort)
        if args.limit:
            rows = rows[: args.limit]
        if args.fields:
            fields = [f.strip() for f in args.fields.split(",") if f.strip()]
            cursor = conn.execute(
                "SELECT t.*, p.name as project_name FROM todos t "
                "LEFT JOIN projects p ON t.project_id = p.id LIMIT 0"
            )
            valid = {d[0] for d in cursor.description}
            invalid = [f for f in fields if f not in valid]
            if invalid:
                print(
                    f"error: invalid fields: {','.join(invalid)}. "
                    f"valid: {','.join(sorted(valid))}",
                    file=sys.stderr,
                )
                sys.exit(1)
            rows = [{f: r.get(f) for f in fields} for r in rows]
        _print_json(rows)
    finally:
        conn.close()


def cmd_show(args):
    conn = get_conn()
    try:
        t = get_todo(conn, args.id)
        if not t:
            print(f"error: todo {args.id} not found", file=sys.stderr)
            sys.exit(1)
        _print_json(t)
    finally:
        conn.close()


_EDIT_FIELDS = (
    "title", "done_definition", "category", "priority", "parent_id",
    "quarter", "deadline", "estimated_min", "notes",
)


def cmd_edit(args):
    """선택 필드만 update. None 인자는 보존. project는 name → id 변환.
    --clear-estimated / --clear-parent-id: 해당 필드를 NULL로 (각각 --estimated-min / --parent-id와 상호 배타)."""
    if args.estimated_min is not None and args.clear_estimated:
        print("error: --estimated-min and --clear-estimated are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    if args.parent_id is not None and args.clear_parent_id:
        print("error: --parent-id and --clear-parent-id are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    overrides = {f: getattr(args, f) for f in _EDIT_FIELDS if getattr(args, f) is not None}
    if (not overrides and args.project is None
            and not args.clear_estimated and not args.clear_parent_id):
        print("error: at least one field required (no-op forbidden)", file=sys.stderr)
        sys.exit(1)
    conn = get_conn()
    try:
        existing = get_todo(conn, args.id)
        if not existing:
            print(f"error: todo {args.id} not found", file=sys.stderr)
            sys.exit(1)
        merged = {k: existing.get(k) for k in (
            "id", "title", "done_definition", "priority", "project_id", "parent_id",
            "category", "quarter", "deadline", "estimated_min", "notes",
        )}
        merged.update(overrides)
        if args.clear_estimated:
            merged["estimated_min"] = None
        if args.clear_parent_id:
            merged["parent_id"] = None
        if args.project is not None:
            merged["project_id"] = _resolve_project(conn, args.project, repo=args.repo)
        upsert_todo(conn, merged)
        conn.commit()
        _print_json(get_todo(conn, args.id))
    except Exception as e:
        conn.rollback()
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_move(args):
    if args.status == "deferred" and not args.reason:
        print("error: --reason required when --status deferred (use defer command for shorthand)", file=sys.stderr)
        sys.exit(1)
    conn = get_conn()
    try:
        if args.status == "wip" and not args.skip_estimated_check:
            t = get_todo(conn, args.id)
            est = t["estimated_min"] if t else None
            if t and (est is None or est <= 0):
                print(
                    f"error: todo {args.id} estimated_min is missing or non-positive. "
                    f"Pass --estimated-min via 'edit' first, or --skip-estimated-check to override",
                    file=sys.stderr,
                )
                sys.exit(1)
        update_todo_status(conn, args.id, args.status, reason=args.reason, force=args.force)
        conn.commit()
        _print_json(get_todo(conn, args.id))
    except Exception as e:
        conn.rollback()
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_defer(args):
    conn = get_conn()
    try:
        update_todo_status(conn, args.id, "deferred", reason=args.reason)
        conn.commit()
        _print_json(get_todo(conn, args.id))
    except Exception as e:
        conn.rollback()
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_done(args):
    conn = get_conn()
    try:
        t = get_todo(conn, args.id)
        if t and t.get("subtasks"):
            unfinished = [s for s in t["subtasks"] if s["status"] != "done"]
            if unfinished:
                titles = ", ".join(f"#{s['id']} '{s['title']}'" for s in unfinished)
                if not args.force:
                    print(f"error: unfinished subtasks remain: {titles}. Use --force to override.", file=sys.stderr)
                    sys.exit(1)
                print(f"[warn] parent done --force leaves unfinished subtasks: {titles}", file=sys.stderr)
        update_todo_status(conn, args.id, "done")
        conn.commit()
        _print_json(get_todo(conn, args.id))
    except Exception as e:
        conn.rollback()
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Create todo (default status=backlog)")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--done-definition", dest="done_definition")
    p_add.add_argument("--category")
    p_add.add_argument("--priority", type=int)
    p_add.add_argument("--project")
    p_add.add_argument("--repo")
    p_add.add_argument("--parent-id", dest="parent_id", type=int)
    p_add.add_argument("--quarter")
    p_add.add_argument("--deadline", help="ISO: YYYY-MM-DD or YYYY-MM-DDTHH:MM")
    p_add.add_argument("--estimated-min", dest="estimated_min", type=_positive_int,
                       help="Positive int (분). NULL로 두려면 --skip-estimated")
    p_add.add_argument("--skip-estimated", dest="skip_estimated", action="store_true",
                       help="Explicitly skip estimated_min (stored as NULL)")
    p_add.add_argument("--notes")

    p_list = sub.add_parser("list", help="List todos")
    p_list.add_argument("--status", choices=["backlog", "wip", "done", "blocked", "deferred"])
    p_list.add_argument("--category")
    p_list.add_argument("--sort", default="default", choices=["default", "priority", "deadline"])
    p_list.add_argument("--limit", type=int)
    p_list.add_argument("--fields", help="Comma-separated field names (e.g. 'id,title,status')")

    p_show = sub.add_parser("show", help="Show single todo with subtasks")
    p_show.add_argument("--id", required=True, type=int)

    p_move = sub.add_parser("move", help="Transition status")
    p_move.add_argument("--id", required=True, type=int)
    p_move.add_argument("--status", required=True,
                        choices=["backlog", "wip", "done", "blocked", "deferred"])
    p_move.add_argument("--reason")
    p_move.add_argument("--force", action="store_true",
                        help="Override WIP limit or unfinished-subtask warning")
    p_move.add_argument("--skip-estimated-check", dest="skip_estimated_check", action="store_true",
                        help="Allow moving to wip even if estimated_min is NULL")

    p_edit = sub.add_parser("edit", help="Update select fields (None preserves existing)")
    p_edit.add_argument("--id", required=True, type=int)
    p_edit.add_argument("--title")
    p_edit.add_argument("--done-definition", dest="done_definition")
    p_edit.add_argument("--category")
    p_edit.add_argument("--priority", type=int)
    p_edit.add_argument("--project")
    p_edit.add_argument("--repo")
    p_edit.add_argument("--parent-id", dest="parent_id", type=int)
    p_edit.add_argument("--quarter")
    p_edit.add_argument("--deadline", help="ISO: YYYY-MM-DD or YYYY-MM-DDTHH:MM")
    p_edit.add_argument("--estimated-min", dest="estimated_min", type=_positive_int)
    p_edit.add_argument("--clear-estimated", dest="clear_estimated", action="store_true",
                        help="Set estimated_min back to NULL")
    p_edit.add_argument("--clear-parent-id", dest="clear_parent_id", action="store_true",
                        help="Set parent_id back to NULL")
    p_edit.add_argument("--notes")

    p_defer = sub.add_parser("defer", help="Defer with reason")
    p_defer.add_argument("--id", required=True, type=int)
    p_defer.add_argument("--reason", required=True)

    p_done = sub.add_parser("done", help="Mark done (checks unfinished subtasks)")
    p_done.add_argument("--id", required=True, type=int)
    p_done.add_argument("--force", action="store_true")

    dispatch = {
        "add": cmd_add,
        "list": cmd_list,
        "show": cmd_show,
        "edit": cmd_edit,
        "move": cmd_move,
        "defer": cmd_defer,
        "done": cmd_done,
    }
    args = ap.parse_args()
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
