#!/usr/bin/env python3
"""mabinogi-equipment-cost 스킬 진입점 — 원가표 서버·시세 수집.

스킬은 얇은 래퍼다. 코드 본체는 레포의 apps/mabinogi/equipment-cost/에 있다.
이 파일 위치에서 레포 루트를 찾아 그쪽 스크립트를 실행한다(심링크는 resolve()가
따라 레포 원본으로 풀린다).

    run.py                → serve.py (원가표, 기본 8765)
    run.py serve [포트]   → serve.py
    run.py collect ...    → collect.py (items·recipes·prices·loop·seed)
"""

import pathlib
import subprocess
import sys

_here = pathlib.Path(__file__).resolve()
# run.py → scripts → mabinogi-equipment-cost → skills → <레포 루트>
repo_root = _here.parents[3]
base = repo_root / "apps" / "mabinogi" / "equipment-cost" / "scripts"

args = sys.argv[1:]
if args and args[0] == "collect":
    target, rest = base / "collect.py", args[1:]
elif args and args[0] == "serve":
    target, rest = base / "serve.py", args[1:]
else:  # 기본: 원가표 서버
    target, rest = base / "serve.py", args

if not target.exists():
    sys.exit(
        f"대상을 못 찾음: {target}\n"
        f"레포 루트({repo_root}) 아래에 apps/mabinogi/equipment-cost/이 있는지 확인."
    )

raise SystemExit(subprocess.call([sys.executable, str(target), *rest]))
