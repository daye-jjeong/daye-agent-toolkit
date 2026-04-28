#!/usr/bin/env python3
"""todo CRUD CLI — 순수 one-shot. 대화 없음.

Usage:
    python3 todo_crud.py add --title "..." [--done-definition "..."] [--category ...] ...
    python3 todo_crud.py list [--status backlog] [--category 업무] [--sort default]
    python3 todo_crud.py show --id N
    python3 todo_crud.py edit --id N [--estimated-min N] [--deadline ...] [--project ...] ...
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
            pid = upsert_project(conn, args.project, repo=args.repo)
            data["project_id"] = pid
        tid = upsert_todo(conn, data)
        conn.commit()
        _print_json({"id": tid, "title": args.title, "status": "backlog"})
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_list(args):
    conn = get_conn()
    try:
        rows = get_todos(conn, status=args.status, category=args.category, sort=args.sort)
        if args.limit:
            rows = rows[: args.limit]
        _print_json(rows)
    finally:
        conn.close()


def cmd_show(args):
    conn = get_conn()
    try:
        t = get_todo(conn, args.id)
        if not t:
            print(f"Error: todo {args.id} not found", file=sys.stderr)
            sys.exit(1)
        _print_json(t)
    finally:
        conn.close()


_EDIT_FIELDS = (
    "title", "done_definition", "category", "priority",
    "quarter", "deadline", "estimated_min", "notes",
)


def cmd_edit(args):
    """선택 필드만 update. None 인자는 보존. project는 name → id 변환."""
    overrides = {f: getattr(args, f) for f in _EDIT_FIELDS if getattr(args, f) is not None}
    if not overrides and args.project is None:
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
        if args.project is not None:
            merged["project_id"] = upsert_project(conn, args.project, repo=args.repo)
        upsert_todo(conn, merged)
        conn.commit()
        _print_json(get_todo(conn, args.id))
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_move(args):
    conn = get_conn()
    try:
        if args.status == "wip" and not args.skip_estimated_check:
            row = conn.execute(
                "SELECT estimated_min FROM todos WHERE id = ?", (args.id,)
            ).fetchone()
            if row and row["estimated_min"] is None:
                print(
                    f"error: todo {args.id} estimated_min is NULL. "
                    f"Pass --estimated-min via 'edit' first, or --skip-estimated-check to override",
                    file=sys.stderr,
                )
                sys.exit(1)
        update_todo_status(conn, args.id, args.status, reason=args.reason, force=args.force)
        conn.commit()
        t = get_todo(conn, args.id)
        _print_json({"id": args.id, "status": t["status"], "started_at": t["started_at"], "done_at": t["done_at"]})
    except ValueError as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_defer(args):
    conn = get_conn()
    try:
        update_todo_status(conn, args.id, "deferred", reason=args.reason)
        conn.commit()
        _print_json({"id": args.id, "status": "deferred", "deferred_reason": args.reason})
    except ValueError as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def cmd_done(args):
    conn = get_conn()
    try:
        # 부모 todo라면 subtasks 확인
        t = get_todo(conn, args.id)
        if t and t.get("subtasks"):
            unfinished = [s for s in t["subtasks"] if s["status"] != "done"]
            if unfinished and not args.force:
                titles = ", ".join(s["title"] for s in unfinished)
                print(f"Warning: unfinished subtasks remain: {titles}. Use --force to override.", file=sys.stderr)
                sys.exit(1)
        update_todo_status(conn, args.id, "done")
        conn.commit()
        _print_json({"id": args.id, "status": "done"})
    except ValueError as e:
        conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
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
    p_add.add_argument("--estimated-min", dest="estimated_min", type=int)
    p_add.add_argument("--skip-estimated", dest="skip_estimated", action="store_true",
                       help="Explicitly skip estimated_min (stored as NULL)")
    p_add.add_argument("--notes")

    p_list = sub.add_parser("list", help="List todos")
    p_list.add_argument("--status", choices=["backlog", "wip", "done", "blocked", "deferred"])
    p_list.add_argument("--category")
    p_list.add_argument("--sort", default="default", choices=["default", "priority", "deadline"])
    p_list.add_argument("--limit", type=int)

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
    p_edit.add_argument("--quarter")
    p_edit.add_argument("--deadline", help="ISO: YYYY-MM-DD or YYYY-MM-DDTHH:MM")
    p_edit.add_argument("--estimated-min", dest="estimated_min", type=int)
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
