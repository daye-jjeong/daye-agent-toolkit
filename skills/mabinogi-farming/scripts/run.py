#!/usr/bin/env python3
"""mabinogi-farming 스킬 진입점 — 영혼석 파밍 대시보드를 띄운다.

스킬은 얇은 래퍼다. 실제 코드는 레포의 apps/mabinogi/farming/에 있다. 이 파일
위치에서 레포 루트를 찾아 그 대시보드를 실행한다(인자는 그대로 넘긴다 —
--port·--no-browser 등). 설치는 ~/.claude/skills·~/.codex/skills로의 심링크라
resolve()가 심링크를 따라 레포 원본 경로로 풀린다.
"""

import pathlib
import subprocess
import sys

_here = pathlib.Path(__file__).resolve()
# run.py → scripts → mabinogi-farming → skills → <레포 루트>
repo_root = _here.parents[3]
target = repo_root / "apps" / "mabinogi" / "farming" / "farming-dashboard.py"

if not target.exists():
    sys.exit(
        f"대시보드를 못 찾음: {target}\n"
        f"레포 루트({repo_root}) 아래에 apps/mabinogi/farming/이 있는지 확인."
    )

raise SystemExit(subprocess.call([sys.executable, str(target), *sys.argv[1:]]))
