# Self-Profile 스킬 구현 Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 업무 데이터 기반 자기 프로파일링 스킬 — 정량 수집 + LLM 분석 프레임워크

**Architecture:** collect.py(DB→JSON) + SKILL.md(LLM 프레임워크) + profile-dimensions.md(차원 정의). life-dashboard DB를 쿼리하여 snapshot JSON 생성, LLM이 profile.md 산출.

**Tech Stack:** Python3 stdlib (sqlite3, json, argparse, pathlib), SQLite

**Spec:** `docs/plans/2026-03-14-self-profile-design.md`

---

### Task 1: 스킬 스캐폴드

**Files:**
- Create: `shared/self-profile/.claude-skill`
- Create: `shared/self-profile/SKILL.md` (뼈대만)

- [x] **Step 1: .claude-skill 생성**

```json
{
  "name": "self-profile",
  "version": "0.1.0",
  "description": "업무 데이터 기반 자기 프로파일링 — 정량 분석 + 페르소나 생성",
  "entrypoint": "SKILL.md"
}
```

- [x] **Step 2: SKILL.md 뼈대 생성**

frontmatter + 기본 구조만. 내용은 Task 5에서 채움.

```markdown
---
name: self-profile
description: 업무 데이터 기반 자기 프로파일링 — 정량 분석 + 페르소나 생성
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Self-Profile Skill

(Task 5에서 완성)
```

- [x] **Step 3: 커밋**

```bash
git add shared/self-profile/.claude-skill shared/self-profile/SKILL.md
git commit -m "feat(self-profile): add skill scaffold"
```

---

### Task 2: collect.py — 테스트 작성

**Files:**
- Create: `shared/self-profile/scripts/collect.py` (빈 뼈대)
- Create: `shared/self-profile/tests/test_collect.py`

collect.py의 핵심 로직을 테스트로 먼저 정의한다. DB 의존 부분은 in-memory SQLite로 테스트.

- [x] **Step 1: collect.py 빈 뼈대 생성**

```python
#!/usr/bin/env python3
"""Self-Profile data collector — DB → JSON snapshot."""

import argparse
import json
import sys


def collect(days: int = 30, since: str | None = None,
            project_roots: list[str] | None = None) -> dict:
    """Collect profile data and return as dict."""
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description="Self-profile data collector")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--since", type=str, default=None)
    parser.add_argument("--project-roots", type=str, default=None,
                        help="Comma-separated project root paths")
    args = parser.parse_args()

    roots = args.project_roots.split(",") if args.project_roots else None
    result = collect(days=args.days, since=args.since, project_roots=roots)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [x] **Step 2: 테스트 파일 생성 — 스키마 헬퍼 + 기본 구조 테스트**

```python
#!/usr/bin/env python3
"""Tests for self-profile collect.py."""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# collect.py를 import할 수 있도록 path 설정
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest


def _create_test_db() -> sqlite3.Connection:
    """In-memory DB with life-dashboard schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema_path = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp" / "schema.sql"
    conn.executescript(schema_path.read_text())
    return conn


def _insert_activity(conn, *, source="cc", session_id="s1", repo="test-repo",
                     tag="코딩", start_at="2026-03-01 10:00", end_at="2026-03-01 10:30",
                     duration_min=30):
    conn.execute("""
        INSERT INTO activities (source, session_id, repo, tag, start_at, end_at, duration_min)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (source, session_id, repo, tag, start_at, end_at, duration_min))
    conn.commit()


def _insert_signal(conn, *, session_id="s1", date="2026-03-01",
                   signal_type="mistake", content="test signal", repo="test-repo"):
    conn.execute("""
        INSERT INTO behavioral_signals (session_id, date, signal_type, content, repo)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, date, signal_type, content, repo))
    conn.commit()


class TestJsonSchema:
    """출력 JSON이 설계 스키마를 따르는지 검증."""

    def test_top_level_keys(self, collect_with_db):
        result = collect_with_db([])
        assert set(result.keys()) == {"period", "sessions", "behavioral_signals",
                                       "corrections", "daily_trend"}

    def test_sessions_has_dual_metrics(self, collect_with_db):
        """by_weekday, by_hour, by_tag은 count + total_min 둘 다 있어야 한다."""
        _insert_activity(collect_with_db.conn, session_id="s1",
                         start_at="2026-03-01 10:00", duration_min=30)
        result = collect_with_db(["2026-03-01"])
        sat = result["sessions"]["by_weekday"].get("Sun")  # 2026-03-01 = Sunday
        assert sat is not None
        assert "count" in sat and "total_min" in sat

    def test_by_source_breakdown(self, collect_with_db):
        """source별 breakdown이 있어야 한다."""
        _insert_activity(collect_with_db.conn, session_id="s1", source="cc")
        _insert_activity(collect_with_db.conn, session_id="s2", source="codex")
        result = collect_with_db(["2026-03-01"])
        assert "cc" in result["sessions"]["by_source"]
        assert "codex" in result["sessions"]["by_source"]


class TestNullHandling:
    """NULL/빈 데이터 처리."""

    def test_empty_tag_becomes_기타(self, collect_with_db):
        _insert_activity(collect_with_db.conn, session_id="s1", tag="")
        result = collect_with_db(["2026-03-01"])
        assert "기타" in result["sessions"]["by_tag"]

    def test_null_tag_becomes_기타(self, collect_with_db):
        _insert_activity(collect_with_db.conn, session_id="s1", tag=None)
        result = collect_with_db(["2026-03-01"])
        assert "기타" in result["sessions"]["by_tag"]


class TestDailyTrend:
    """daily_trend의 0-fill 검증."""

    def test_zero_fill_inactive_days(self, collect_with_db):
        """활동 없는 날도 daily_trend에 포함되어야 한다."""
        _insert_activity(collect_with_db.conn, session_id="s1",
                         start_at="2026-03-01 10:00")
        # 3일 기간 중 활동은 1일만
        result = collect_with_db(["2026-03-01", "2026-03-02", "2026-03-03"],
                                 period_start="2026-03-01", period_end="2026-03-03")
        dates = [d["date"] for d in result["daily_trend"]]
        assert "2026-03-02" in dates  # 무활동일
        inactive = next(d for d in result["daily_trend"] if d["date"] == "2026-03-02")
        assert inactive["sessions"] == 0
        assert inactive["hours"] == 0.0


class TestBehavioralSignals:
    """행동 신호 상위 N개 제한."""

    def test_top_signals_limited_to_20(self, collect_with_db):
        """각 유형별 상위 20개만 반환."""
        for i in range(25):
            _insert_signal(collect_with_db.conn, session_id=f"s{i}",
                           signal_type="mistake", content=f"mistake {i}")
        result = collect_with_db(["2026-03-01"])
        assert len(result["behavioral_signals"]["top_mistakes"]) <= 20

    def test_repeat_signals_aggregated(self, collect_with_db):
        """반복 신호가 count와 함께 집계."""
        for i in range(3):
            _insert_signal(collect_with_db.conn, session_id=f"s{i}",
                           signal_type="mistake", content="같은 실수")
        result = collect_with_db(["2026-03-01"])
        repeats = result["behavioral_signals"]["repeat_signals"]
        assert any(r["content"] == "같은 실수" and r["count"] == 3 for r in repeats)
```

NOTE: `collect_with_db` fixture는 테스트용 in-memory DB와 collect 함수를 연결하는 pytest fixture. collect.py에 `_collect_from_conn(conn, ...)` 내부 함수를 만들어서 테스트에서 conn을 주입할 수 있게 한다.

- [x] **Step 3: pytest conftest.py 생성**

```python
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from collect import _collect_from_conn


def _create_test_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema_path = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp" / "schema.sql"
    conn.executescript(schema_path.read_text())
    return conn


class _CollectHelper:
    def __init__(self):
        self.conn = _create_test_db()

    def __call__(self, dates, period_start=None, period_end=None):
        start = period_start or (dates[0] if dates else "2026-03-01")
        end = period_end or (dates[-1] if dates else "2026-03-01")
        return _collect_from_conn(self.conn, start, end, project_roots=[])


@pytest.fixture
def collect_with_db():
    helper = _CollectHelper()
    yield helper
    helper.conn.close()
```

- [x] **Step 4: 테스트 실행 — 전부 FAIL 확인**

Run: `cd shared/self-profile && python3 -m pytest tests/ -v`
Expected: FAIL (NotImplementedError 또는 ImportError)

- [x] **Step 5: 커밋**

```bash
git add shared/self-profile/scripts/collect.py shared/self-profile/tests/
git commit -m "test(self-profile): add collect.py tests (RED)"
```

---

### Task 3: collect.py — 구현

**Files:**
- Modify: `shared/self-profile/scripts/collect.py`

테스트를 통과하도록 `_collect_from_conn()`을 구현한다.

- [x] **Step 1: _collect_from_conn 핵심 구현**

`_collect_from_conn(conn, start, end, project_roots)` → dict

구현 요소:
- `period`: start, end, days 계산
- `sessions`: activities 쿼리 → by_weekday, by_hour, by_tag, by_repo, by_source (모두 count + total_min)
- NULL/빈 tag → "기타" 변환
- `behavioral_signals`: signal_type별 상위 20개 + summary counts + repeat_signals
- `corrections`: project_roots 내 `correction-*.md` 파일 스캔, 파일명에서 날짜 추출
- `daily_trend`: 기간 내 모든 날짜 생성 → activities JOIN → 0-fill

참고할 기존 코드:
- `shared/life-dashboard-mcp/db.py` — DB 연결, 쿼리 패턴
- `shared/life-coach/scripts/daily_coach.py` — activities 쿼리 패턴
- `shared/life-coach/scripts/weekly_coach.py` — 집계 패턴

- [x] **Step 2: collect() 함수에서 DB 연결 + _collect_from_conn 호출**

```python
def collect(days=30, since=None, project_roots=None):
    _MCP_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
    sys.path.insert(0, str(_MCP_DIR))
    from db import get_conn

    conn = get_conn()
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        if since:
            start = since
        else:
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        if project_roots is None:
            # 기본: ~/git_workplace/*/
            wp = Path.home() / "git_workplace"
            project_roots = [str(p) for p in wp.iterdir() if p.is_dir()] if wp.exists() else []

        return _collect_from_conn(conn, start, end, project_roots)
    finally:
        conn.close()
```

- [x] **Step 3: snapshot JSON 저장 로직 추가**

main()에서 결과를 stdout + `~/life-dashboard/profile-snapshot.json`에 저장.
기존 snapshot이 있으면 `.prev.json`으로 백업.

- [x] **Step 4: 테스트 실행 — 전부 PASS 확인**

Run: `cd shared/self-profile && python3 -m pytest tests/ -v`
Expected: ALL PASS

- [x] **Step 5: 실제 DB로 스모크 테스트**

Run: `python3 shared/self-profile/scripts/collect.py --days 7 | python3 -m json.tool | head -50`
Expected: 유효한 JSON, 각 키가 존재

- [x] **Step 6: 커밋**

```bash
git add shared/self-profile/scripts/collect.py
git commit -m "feat(self-profile): implement collect.py (GREEN)"
```

---

### Task 4: profile-dimensions.md

**Files:**
- Create: `shared/self-profile/references/profile-dimensions.md`

SKILL.md에서 참조하는 분석 차원 상세 정의. LLM이 데이터를 해석할 때 이 문서를 읽고 각 차원을 분석한다.

- [x] **Step 1: profile-dimensions.md 작성**

내용:
- 7개 차원별 해석 가이드 (시간 패턴, 작업 성향, 실수 패턴, 의사결정, 행동 패턴, 도구/레포, 교정 이력)
- 각 차원에서 "강점"과 "개선 포인트"를 어떻게 도출하는지 기준
- 페르소나 작성 가이드라인 (데이터 근거 필수, 주관적 판단 최소화)
- 개선 포인트의 A/B 제시 포맷 (현재 방식 vs 제안 방식)
- 변화 추이 해석 기준 (snapshot diff에서 유의미한 변화 판단)

- [x] **Step 2: 커밋**

```bash
git add shared/self-profile/references/profile-dimensions.md
git commit -m "docs(self-profile): add profile dimensions reference"
```

---

### Task 5: SKILL.md 완성

**Files:**
- Modify: `shared/self-profile/SKILL.md`

- [x] **Step 1: SKILL.md 전체 내용 작성**

구성:
1. 프로파일 생성/갱신 절차 (Step 1~4)
   - Step 1: `collect.py` 실행 → JSON
   - Step 2: 기존 `profile.md` + 이전 `snapshot.prev.json` Read (있으면)
   - Step 3: `references/profile-dimensions.md` 프레임으로 분석
   - Step 4: `~/life-dashboard/profile.md` 작성/업데이트
2. 차트 생성 지시 (matplotlib, /tmp/에 저장 후 open)
3. 참조 파일 목록

- [x] **Step 2: 커밋**

```bash
git add shared/self-profile/SKILL.md
git commit -m "feat(self-profile): complete SKILL.md analysis framework"
```

---

### Task 6: life-coach 연결

**Files:**
- Modify: `shared/life-coach/references/coaching-prompts.md`

- [x] **Step 1: coaching-prompts.md 서두에 profile.md 참조 추가**

```markdown
## 프로파일 참조

코칭 시작 시 `~/life-dashboard/profile.md`가 존재하면 Read한다.
페르소나/강점/개선 포인트를 코칭 톤과 내용에 반영한다.
파일이 없으면 무시하고 기존 코칭 플로우 유지.
```

- [x] **Step 2: 커밋**

```bash
git add shared/life-coach/references/coaching-prompts.md
git commit -m "feat(life-coach): reference self-profile for personalized coaching"
```

---

### Task 7: 통합 테스트 + 정리

- [x] **Step 1: 전체 테스트 실행**

Run: `cd shared/self-profile && python3 -m pytest tests/ -v`
Expected: ALL PASS

- [x] **Step 2: 실제 DB로 전체 플로우 스모크 테스트**

Run: `python3 shared/self-profile/scripts/collect.py --days 30`
확인: JSON 출력이 유효하고, `~/life-dashboard/profile-snapshot.json`이 생성됨

- [x] **Step 3: make install-cc 실행**

Run: `make install-cc`
확인: `~/.claude/skills/self-profile` 심링크 생성

- [x] **Step 4: 최종 커밋 (필요 시)**

```bash
git add -A
git commit -m "chore(self-profile): finalize skill setup"
```
