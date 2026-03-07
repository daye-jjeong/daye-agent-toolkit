#!/usr/bin/env python3
"""life-dashboard MCP server — unified activity data access."""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from db import get_conn, get_coach_state

KST = timezone(timedelta(hours=9))
app = Server("life-dashboard")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_today_summary",
            description="오늘의 활동 요약 — 작업시간, 세션수, 태그, 레포별 분포",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_date_summary",
            description="특정일의 활동 요약",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"}
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="get_weekly_summary",
            description="최근 7일 활동 요약 — 일별 작업시간, 패턴 분석",
            inputSchema={
                "type": "object",
                "properties": {
                    "end_date": {"type": "string", "description": "끝 날짜 YYYY-MM-DD (기본: 오늘)"}
                },
            },
        ),
    ]


def _build_date_summary(conn, date_str: str, coach_state: dict | None = None) -> dict:
    stats = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ?", (date_str,)
    ).fetchone()

    if not stats:
        return {"date": date_str, "has_data": False}

    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    activities = conn.execute("""
        SELECT repo, tag, summary, start_at, end_at, duration_min
        FROM activities WHERE start_at >= ? AND start_at < ? AND source = 'cc'
        ORDER BY start_at
    """, (date_str, next_date)).fetchall()

    return {
        "date": date_str,
        "has_data": True,
        "work_hours": stats["work_hours"],
        "session_count": stats["session_count"],
        "first_session": stats["first_session"],
        "last_session_end": stats["last_session_end"],
        "tag_breakdown": json.loads(stats["tag_breakdown"]) if stats["tag_breakdown"] else {},
        "repos": json.loads(stats["repos"]) if stats["repos"] else {},
        "sessions": [
            {
                "repo": a["repo"],
                "tag": a["tag"],
                "summary": a["summary"][:150] if a["summary"] else "",
                "start": a["start_at"][11:16] if a["start_at"] else "",
                "end": a["end_at"][11:16] if a["end_at"] else "",
                "duration_min": a["duration_min"],
            }
            for a in activities
        ],
        "coach_state": coach_state if coach_state is not None else get_coach_state(conn),
    }


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    conn = get_conn()
    try:
        if name == "get_today_summary":
            today = datetime.now(KST).strftime("%Y-%m-%d")
            result = _build_date_summary(conn, today)

        elif name == "get_date_summary":
            date_arg = arguments.get("date", "")
            try:
                datetime.strptime(date_arg, "%Y-%m-%d")
            except ValueError:
                result = {"error": f"Invalid date format. Expected YYYY-MM-DD, got: {date_arg}"}
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
            result = _build_date_summary(conn, date_arg)

        elif name == "get_weekly_summary":
            end = arguments.get("end_date") or datetime.now(KST).strftime("%Y-%m-%d")
            try:
                end_dt = datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                result = {"error": f"Invalid date format. Expected YYYY-MM-DD, got: {end}"}
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
            state = get_coach_state(conn)
            days = []
            for i in range(6, -1, -1):
                d = (end_dt - timedelta(days=i)).strftime("%Y-%m-%d")
                days.append(_build_date_summary(conn, d, coach_state=state))
            total_hours = sum(d.get("work_hours", 0) for d in days if d["has_data"])
            active_days = sum(1 for d in days if d["has_data"])
            result = {
                "period": f"{days[0]['date']} ~ {days[-1]['date']}",
                "total_work_hours": round(total_hours, 1),
                "active_days": active_days,
                "daily": days,
                "coach_state": state,
            }
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        print(f"[life-dashboard] tool error: {name}: {e}", file=sys.stderr)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
    finally:
        conn.close()


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
