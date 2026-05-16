# mabinogi-mml Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 곡명 → (커뮤니티 MML/MIDI 탐색 또는 폴백 작곡) → 마비노기 모바일 제약 검증을 거친 붙여넣기용 MML을 만드는, 플러그인 비소속 CC·Codex 크로스 에이전트 스킬을 구축한다.

**Architecture:** 단일 소스 `skills/mabinogi-mml/`(레포 루트, plugins/ 밖). 결정적 로직은 Python stdlib 스크립트 2개(`midi_to_mml.py` 변환, `validate_mml.py` 검증), LLM 프레임워크는 `SKILL.md`+`references/`. `make install`이 `~/.claude/skills/`·`~/.codex/skills/`에 심링크해 양 에이전트 네이티브 발견. CLAUDE.md의 플러그인 강제 모델은 standalone 구조로 재작성(기존 18개 스킬 grandfather).

**Tech Stack:** Python 3.12 stdlib only (`struct`, `argparse`), Markdown, GNU Make, pytest.

**실행 중 사용자 기여 지점 (learning):** Task 14(옥타브 표기 전략), Task 16(폴리포니 축약 정책) — 정답 복수, 도메인 판단 필요. 실행 서브에이전트는 해당 함수 시그니처+컨텍스트를 만든 뒤 사용자에게 5~10줄 구현을 요청할 것.

**알려진 단순화 (v1, YAGNI):** MIDI 트랙 내 겹치는 음은 멜로디 1개로 축약(정책은 Task 16에서 결정). 진짜 화음은 트랙 분리로만. "MIDI 불러오면 후처리 필요"라는 커뮤니티 통념과 일치 — 스킬은 깔끔한 멜로디 베이스 + 검증을 제공, 사용자가 마비꼬에서 다듬음.

---

## File Structure

```
skills/mabinogi-mml/
  SKILL.md                  생성 — frontmatter + 워크플로우 + 능력경계 (≤150줄)
  VERSION                   생성 — 0.1.0
  CHANGELOG.md              생성
  references/
    mml-syntax.md           생성 — 마비노기 모바일 MML 문법
    mobile-workflow.md      생성 — 모바일 제약 + 마비꼬 export + 게임 단계
  scripts/
    midi_to_mml.py          생성 — SMF 파싱 → MML
    validate_mml.py         생성 — 모바일 제약 검증 + 압축 제안
  tests/
    test_validate_mml.py    생성
    test_midi_to_mml.py     생성 (SMF 픽스처 헬퍼 내장)
Makefile                    수정 — _symlink-skills 타깃 + clean/status 대칭
CLAUDE.md                   수정 — 플러그인 모델 → standalone 크로스 에이전트 구조
```

상수 (두 스크립트 공유 — 각 파일 상단에 정의, DRY는 파일 내):
- `MAX_TRACKS = 6`
- `MAX_CHARS_PER_PART = 1200`  # 1200/2400 소스 상이. 보수적 기본값. 사용자가 게임 실측 후 조정. CLI `--max-chars`로 override.
- `MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}`
- `OCTAVE_UP, OCTAVE_DOWN = "<", ">"`  # 마비노기 관례: `<`=옥타브↑. CLI/상수로 교체 가능.
- `MIDI_C4 = 60`  # MIDI 60 = 마비노기 o4 'c' 기준 매핑

---

## Task 1: 스킬 디렉토리 + 메타 파일 스캐폴드

**Files:**
- Create: `skills/mabinogi-mml/VERSION`
- Create: `skills/mabinogi-mml/CHANGELOG.md`
- Create: `skills/mabinogi-mml/scripts/` `references/` `tests/fixtures/` (빈 디렉토리, `.gitkeep`)

- [ ] **Step 1: 디렉토리 + VERSION + CHANGELOG 생성**

```bash
mkdir -p skills/mabinogi-mml/scripts skills/mabinogi-mml/references skills/mabinogi-mml/tests
printf '0.1.0\n' > skills/mabinogi-mml/VERSION
cat > skills/mabinogi-mml/CHANGELOG.md <<'EOF'
# Changelog

## 0.1.0 (2026-05-16)
- 최초 릴리스: MIDI→MML 변환, 모바일 제약 검증, 소스 탐색 워크플로우.
- 플러그인 비소속 CC·Codex 크로스 에이전트 스킬.
EOF
```

- [ ] **Step 2: 커밋**

```bash
git add skills/mabinogi-mml/VERSION skills/mabinogi-mml/CHANGELOG.md
git commit -m "scaffold(mabinogi-mml): VERSION + CHANGELOG"
```

---

## Task 2: validate_mml.py — parse_tracks (TDD)

**Files:**
- Create: `skills/mabinogi-mml/scripts/validate_mml.py`
- Test: `skills/mabinogi-mml/tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_validate_mml.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from validate_mml import parse_tracks

def test_parse_tracks_splits_on_comma_strips_wrapper():
    assert parse_tracks("MML@cde,fga,bb;") == ["cde", "fga", "bb"]

def test_parse_tracks_single_track_no_wrapper():
    assert parse_tracks("cdefg") == ["cdefg"]

def test_parse_tracks_trailing_empty_tracks_kept():
    assert parse_tracks("MML@cde,,;") == ["cde", "", ""]
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: FAIL (`ModuleNotFoundError` 또는 `ImportError: cannot import name 'parse_tracks'`)

- [ ] **Step 3: 최소 구현**

```python
# scripts/validate_mml.py
"""마비노기 모바일 MML 제약 검증 + 압축 제안. stdlib only."""

MAX_TRACKS = 6
MAX_CHARS_PER_PART = 1200  # 1200/2400 소스 상이. 보수적 기본. 게임 실측 후 조정.
MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}


def parse_tracks(mml: str) -> list[str]:
    """`MML@t1,t2,...;` → 트랙 문자열 리스트. 래퍼 없으면 단일 트랙."""
    s = mml.strip()
    if s.upper().startswith("MML@"):
        s = s[4:]
    if s.endswith(";"):
        s = s[:-1]
    return s.split(",")
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/validate_mml.py skills/mabinogi-mml/tests/test_validate_mml.py
git commit -m "feat(mabinogi-mml): validate_mml parse_tracks"
```

---

## Task 3: validate_mml.py — 트랙 수 / 글자수 검증 (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/validate_mml.py`
- Test: `skills/mabinogi-mml/tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import check_limits

def test_check_limits_ok():
    assert check_limits(["abc", "def"], max_tracks=6, max_chars=1200) == []

def test_check_limits_too_many_tracks():
    tracks = ["a"] * 7
    v = check_limits(tracks, max_tracks=6, max_chars=1200)
    assert any("트랙" in m and "7" in m for m in v)

def test_check_limits_char_overflow_reports_track_index():
    v = check_limits(["x" * 1201, "ok"], max_tracks=6, max_chars=1200)
    assert any("트랙 1" in m and "1201" in m for m in v)
    assert not any("트랙 2" in m for m in v)
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: FAIL (`cannot import name 'check_limits'`)

- [ ] **Step 3: 구현 추가**

```python
def check_limits(tracks: list[str], max_tracks: int = MAX_TRACKS,
                 max_chars: int = MAX_CHARS_PER_PART) -> list[str]:
    """제약 위반 메시지 리스트. 빈 리스트면 통과."""
    violations: list[str] = []
    if len(tracks) > max_tracks:
        violations.append(
            f"트랙 수 {len(tracks)}개 — 최대 {max_tracks}개 초과")
    for i, t in enumerate(tracks, start=1):
        if len(t) > max_chars:
            violations.append(
                f"트랙 {i} 글자수 {len(t)} — 파트당 최대 {max_chars} 초과")
    return violations
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/validate_mml.py skills/mabinogi-mml/tests/test_validate_mml.py
git commit -m "feat(mabinogi-mml): validate_mml check_limits"
```

---

## Task 4: validate_mml.py — 트랙 tick 길이 + 디싱크 검출 (TDD)

마비노기 모바일은 파트 간 길이 불일치 시 박자가 어긋난다. 각 트랙의 총 tick 길이를 계산해 비교.

**Files:**
- Modify: `skills/mabinogi-mml/scripts/validate_mml.py`
- Test: `skills/mabinogi-mml/tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import track_tick_length, check_desync

def test_track_tick_length_quarter_note_default_l4():
    # 기본 l4(4분음표) 음표 4개 = 1마디 = 4 quarter = 4*480 tick (PPQ 480)
    assert track_tick_length("cdef", ppq=480) == 4 * 480

def test_track_tick_length_explicit_lengths_and_rest():
    # c8 (8분=240) + r4 (4분쉼=480) + e2 (2분=960)
    assert track_tick_length("c8r4e2", ppq=480) == 240 + 480 + 960

def test_track_tick_length_dotted():
    # c4. = 4분음표 * 1.5 = 720
    assert track_tick_length("c4.", ppq=480) == 720

def test_check_desync_flags_mismatch():
    v = check_desync(["cdef", "cde"], ppq=480)  # 1920 vs 1440
    assert any("디싱크" in m or "길이" in m for m in v)

def test_check_desync_ok_equal_lengths():
    assert check_desync(["cdef", "cdef"], ppq=480) == []
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: FAIL (`cannot import name 'track_tick_length'`)

- [ ] **Step 3: 구현 추가**

```python
import re

_TOKEN_RE = re.compile(
    r"(?P<note>[a-gA-G])(?P<acc>[+#-]?)(?P<len>\d*)(?P<dot>\.*)"
    r"|(?P<rest>[rR])(?P<rlen>\d*)(?P<rdot>\.*)"
    r"|[lL](?P<ldef>\d+)"
    r"|[oO]\d+|[<>]|[tT]\d+|[vV]\d+|[nN]\d+"
)


def _len_to_ticks(length: int, dots: int, ppq: int) -> int:
    base = (4 * ppq) // length
    total, add = base, base
    for _ in range(dots):
        add //= 2
        total += add
    return total


def track_tick_length(track: str, ppq: int = 480) -> int:
    """트랙의 총 연주 길이(tick). l 기본길이/점음표/쉼표 반영. o<>tvn은 길이 0."""
    cur_l = MABI_DEFAULTS["l"]
    total = 0
    for m in _TOKEN_RE.finditer(track):
        if m.group("ldef"):
            cur_l = int(m.group("ldef"))
        elif m.group("note"):
            ln = int(m.group("len")) if m.group("len") else cur_l
            total += _len_to_ticks(ln, len(m.group("dot")), ppq)
        elif m.group("rest"):
            ln = int(m.group("rlen")) if m.group("rlen") else cur_l
            total += _len_to_ticks(ln, len(m.group("rdot")), ppq)
    return total


def check_desync(tracks: list[str], ppq: int = 480) -> list[str]:
    """트랙 길이 불일치(박자 어긋남) 검출."""
    lengths = [track_tick_length(t, ppq) for t in tracks if t.strip()]
    if len(set(lengths)) > 1:
        return [f"트랙 길이 불일치(디싱크 위험): {lengths} tick"]
    return []
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/validate_mml.py skills/mabinogi-mml/tests/test_validate_mml.py
git commit -m "feat(mabinogi-mml): validate_mml tick length + desync"
```

---

## Task 5: validate_mml.py — 템포 위치 경고 + 압축 제안 (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/validate_mml.py`
- Test: `skills/mabinogi-mml/tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import check_tempo_placement, suggest_compression

def test_tempo_mid_track_warns():
    v = check_tempo_placement(["t120cdef", "cdt140ef"])
    assert any("트랙 2" in m and "템포" in m for m in v)

def test_tempo_at_start_ok():
    assert check_tempo_placement(["t120cdef", "t120cdef"]) == []

def test_suggest_compression_repeated_length():
    # 같은 길이 8이 반복되면 l8 기본길이 제안
    s = suggest_compression("c8d8e8f8g8a8")
    assert any("l8" in x for x in s)

def test_suggest_compression_clean_track_no_suggestion():
    assert suggest_compression("l4cdef") == []
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: FAIL (`cannot import name 'check_tempo_placement'`)

- [ ] **Step 3: 구현 추가**

```python
def check_tempo_placement(tracks: list[str]) -> list[str]:
    """t 명령이 트랙 첫 음표 뒤에 나오면 경고(모바일 박자 어긋남 원인)."""
    warnings: list[str] = []
    for i, t in enumerate(tracks, start=1):
        first_note = re.search(r"[a-gA-Gr]", t)
        for tm in re.finditer(r"[tT]\d+", t):
            if first_note and tm.start() > first_note.start():
                warnings.append(
                    f"트랙 {i}: 음표 뒤 템포 명령({tm.group()}) — "
                    f"모바일에서 박자 어긋남 위험. 트랙 맨 앞으로 이동 권장")
                break
    return warnings


def suggest_compression(track: str) -> list[str]:
    """글자수 절약 제안(텍스트). 자동 수정 아님 — 위험하므로 제안만."""
    out: list[str] = []
    lengths = re.findall(r"[a-gA-G][+#-]?(\d+)", track)
    if lengths:
        from collections import Counter
        common, cnt = Counter(lengths).most_common(1)[0]
        if cnt >= 4:
            out.append(
                f"길이 {common} 음표가 {cnt}회 — `l{common}` 기본길이로 "
                f"개별 숫자 생략 시 글자수 절약")
    if "n" not in track.lower() and re.search(r"[a-gA-G]", track):
        out.append("`N` 명령(절대 음높이) 사용 시 옥타브 명령 생략 가능 "
                    "— 마비꼬 export에서 'N 명령 허용' 체크")
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: PASS (15 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/validate_mml.py skills/mabinogi-mml/tests/test_validate_mml.py
git commit -m "feat(mabinogi-mml): validate_mml tempo placement + compression hints"
```

---

## Task 6: validate_mml.py — validate() 통합 + CLI (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/validate_mml.py`
- Test: `skills/mabinogi-mml/tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import validate
import subprocess, json

def test_validate_aggregates_all_checks():
    rep = validate("MML@t120cdef,t120cde;", max_chars=1200)
    assert rep["ok"] is False  # 디싱크(1920 vs 1440)
    assert any("디싱크" in m or "길이" in m for m in rep["violations"])
    assert "suggestions" in rep

def test_validate_clean_passes():
    rep = validate("MML@t120cdef,t120cdef;")
    assert rep["ok"] is True
    assert rep["violations"] == []

def test_cli_outputs_json(tmp_path):
    out = subprocess.run(
        ["python3", "scripts/validate_mml.py", "--json", "MML@cdef,cde;"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        capture_output=True, text=True)
    assert out.returncode == 1  # 위반 있으면 exit 1
    data = json.loads(out.stdout)
    assert data["ok"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: FAIL (`cannot import name 'validate'`)

- [ ] **Step 3: 구현 추가**

```python
def validate(mml: str, max_tracks: int = MAX_TRACKS,
             max_chars: int = MAX_CHARS_PER_PART, ppq: int = 480) -> dict:
    tracks = parse_tracks(mml)
    violations = (check_limits(tracks, max_tracks, max_chars)
                  + check_desync(tracks, ppq)
                  + check_tempo_placement(tracks))
    suggestions: list[str] = []
    for i, t in enumerate(tracks, start=1):
        for s in suggest_compression(t):
            suggestions.append(f"트랙 {i}: {s}")
    return {"ok": not violations, "tracks": len(tracks),
            "violations": violations, "suggestions": suggestions}


def _main(argv: list[str]) -> int:
    import argparse, json, sys
    p = argparse.ArgumentParser(description="마비노기 모바일 MML 검증")
    p.add_argument("mml", help="MML 문자열 또는 @파일경로")
    p.add_argument("--max-chars", type=int, default=MAX_CHARS_PER_PART)
    p.add_argument("--max-tracks", type=int, default=MAX_TRACKS)
    p.add_argument("--ppq", type=int, default=480)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    text = a.mml
    if text.startswith("@"):
        with open(text[1:], encoding="utf-8") as f:
            text = f.read().strip()
    rep = validate(text, a.max_tracks, a.max_chars, a.ppq)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False))
    else:
        print("OK" if rep["ok"] else "FAIL")
        for v in rep["violations"]:
            print(f"  ✗ {v}")
        for s in rep["suggestions"]:
            print(f"  · {s}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q`
Expected: PASS (18 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/validate_mml.py skills/mabinogi-mml/tests/test_validate_mml.py
git commit -m "feat(mabinogi-mml): validate_mml validate() + CLI"
```

---

## Task 7: midi_to_mml.py — SMF 픽스처 헬퍼 + read_vlq (TDD)

**Files:**
- Create: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 작성 (픽스처 헬퍼 포함)**

```python
# tests/test_midi_to_mml.py
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from midi_to_mml import read_vlq


def make_smf(ppq: int, events: list[tuple[int, bytes]]) -> bytes:
    """최소 SMF(format 0, 1 track). events=[(delta, raw_event_bytes), ...]
    raw_event_bytes는 status+data (러닝스테이터스 미사용)."""
    def vlq(n: int) -> bytes:
        out = bytearray([n & 0x7F])
        n >>= 7
        while n:
            out.insert(0, (n & 0x7F) | 0x80)
            n >>= 7
        return bytes(out)
    trk = bytearray()
    for delta, ev in events:
        trk += vlq(delta) + ev
    trk += vlq(0) + b"\xFF\x2F\x00"  # End of Track
    head = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq)
    track = b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
    return head + track


def test_read_vlq_single_byte():
    assert read_vlq(b"\x40", 0) == (0x40, 1)

def test_read_vlq_multi_byte():
    # 0x81 0x00 -> 128
    assert read_vlq(b"\x81\x00", 0) == (128, 2)

def test_read_vlq_offset():
    assert read_vlq(b"\xFF\x81\x00", 1) == (128, 3)
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'read_vlq'`)

- [ ] **Step 3: 최소 구현**

```python
# scripts/midi_to_mml.py
"""MIDI(SMF) → 마비노기 모바일 MML. stdlib only."""
import struct

MAX_TRACKS = 6
MIDI_C4 = 60
MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}
OCTAVE_UP, OCTAVE_DOWN = "<", ">"


def read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    """가변길이 수량 읽기. 반환 (value, next_pos)."""
    value = 0
    while True:
        b = data[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            return value, pos
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml read_vlq + SMF fixture helper"
```

---

## Task 8: midi_to_mml.py — parse_header + split_tracks (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import parse_header, split_tracks

def test_parse_header_returns_fmt_ntrks_ppq():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    assert parse_header(smf) == (0, 1, 480)

def test_split_tracks_returns_one_chunk():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    chunks = split_tracks(smf)
    assert len(chunks) == 1
    assert chunks[0].endswith(b"\xFF\x2F\x00")
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'parse_header'`)

- [ ] **Step 3: 구현 추가**

```python
def parse_header(data: bytes) -> tuple[int, int, int]:
    """MThd 파싱 → (format, ntrks, division). SMPTE division 미지원(양수 PPQ 가정)."""
    if data[:4] != b"MThd":
        raise ValueError("MThd 청크 없음 — 유효한 SMF 아님")
    length, fmt, ntrks, division = struct.unpack(">IHHH", data[4:14])
    if division & 0x8000:
        raise ValueError("SMPTE division 미지원 (PPQ 형식만)")
    return fmt, ntrks, division


def split_tracks(data: bytes) -> list[bytes]:
    """MTrk 청크들의 본문 바이트 리스트."""
    chunks: list[bytes] = []
    pos = 14
    while pos < len(data):
        if data[pos:pos + 4] != b"MTrk":
            break
        (length,) = struct.unpack(">I", data[pos + 4:pos + 8])
        chunks.append(data[pos + 8:pos + 8 + length])
        pos += 8 + length
    return chunks
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml parse_header + split_tracks"
```

---

## Task 9: midi_to_mml.py — parse_track_events → 노트 추출 (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import extract_notes

def test_extract_notes_single_note():
    # C4(60) on@0, off@480
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    chunk = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    notes = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 480, 60)]  # (start_tick, dur_tick, midi_pitch)

def test_extract_notes_note_on_zero_velocity_is_off():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (240, b"\x90\x3C\x00")])
    notes = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 240, 60)]

def test_extract_notes_running_status():
    # 두 번째 노트는 status 생략(러닝 스테이터스): 0x90 후 3C 40 / 3E 40
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (0, b"\x3E\x40"),
                         (480, b"\x80\x3C\x40"), (0, b"\x3E\x40")])
    notes = sorted(extract_notes(split_tracks(smf)[0]))
    assert notes == [(0, 480, 60), (0, 480, 62)]
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'extract_notes'`)

- [ ] **Step 3: 구현 추가**

```python
def extract_notes(chunk: bytes) -> list[tuple[int, int, int]]:
    """트랙 청크 → [(start_tick, dur_tick, midi_pitch)]. 러닝스테이터스 지원."""
    pos, abs_tick, status = 0, 0, 0
    pending: dict[int, list[int]] = {}  # pitch -> [start_tick,...]
    notes: list[tuple[int, int, int]] = []
    n = len(chunk)
    while pos < n:
        delta, pos = read_vlq(chunk, pos)
        abs_tick += delta
        b = chunk[pos]
        if b & 0x80:
            status = b
            pos += 1
        # else: running status, status 유지
        ev = status & 0xF0
        if ev in (0x80, 0x90):
            pitch, vel = chunk[pos], chunk[pos + 1]
            pos += 2
            on = ev == 0x90 and vel > 0
            if on:
                pending.setdefault(pitch, []).append(abs_tick)
            else:
                if pending.get(pitch):
                    start = pending[pitch].pop(0)
                    notes.append((start, abs_tick - start, pitch))
        elif ev in (0xA0, 0xB0, 0xE0):
            pos += 2
        elif ev in (0xC0, 0xD0):
            pos += 1
        elif status == 0xFF:
            mtype = chunk[pos]
            pos += 1
            mlen, pos = read_vlq(chunk, pos)
            pos += mlen
            if mtype == 0x2F:
                break
        elif status in (0xF0, 0xF7):
            slen, pos = read_vlq(chunk, pos)
            pos += slen
    return notes
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml extract_notes (running status)"
```

---

## Task 10: midi_to_mml.py — ticks_to_length 양자화 (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import ticks_to_length

def test_ticks_to_length_quarter():
    assert ticks_to_length(480, ppq=480) == "4"

def test_ticks_to_length_eighth():
    assert ticks_to_length(240, ppq=480) == "8"

def test_ticks_to_length_dotted_quarter():
    assert ticks_to_length(720, ppq=480) == "4."

def test_ticks_to_length_quantizes_near_value():
    # 470 tick ≈ 4분음표(480)로 스냅
    assert ticks_to_length(470, ppq=480) == "4"

def test_ticks_to_length_64th_grid_floor():
    # 매우 짧으면 최소 64분음표로
    assert ticks_to_length(5, ppq=480) == "64"
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'ticks_to_length'`)

- [ ] **Step 3: 구현 추가**

```python
# 표현 가능한 MML 길이 후보 (값, 표기). 점음표 = 1.5배.
_LEN_TABLE = []
for _base in (1, 2, 4, 8, 16, 32, 64):
    _LEN_TABLE.append((4.0 / _base, str(_base)))           # 일반
    _LEN_TABLE.append((4.0 / _base * 1.5, f"{_base}."))    # 점음표


def ticks_to_length(ticks: int, ppq: int = 480) -> str:
    """tick → 가장 가까운 MML 길이 표기(점음표 포함). 64분음표 그리드 하한."""
    quarters = ticks / ppq  # 4분음표 개수
    best = min(_LEN_TABLE, key=lambda c: abs(c[0] - quarters))
    return best[1]
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml ticks_to_length quantize"
```

---

## Task 11: midi_to_mml.py — midi_note_to_token 음높이 변환 (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import midi_note_to_token

def test_c4_at_octave4_no_shift():
    # 현재 옥타브 4에서 C4(60) -> "c", 옥타브 유지
    assert midi_note_to_token(60, cur_oct=4) == ("c", 4)

def test_sharp_note():
    assert midi_note_to_token(61, cur_oct=4) == ("c+", 4)

def test_octave_up_emits_shift():
    # C5(72), 현재 옥타브4 -> 옥타브 올림 토큰 + c, 새 옥타브 5
    tok, new_oct = midi_note_to_token(72, cur_oct=4)
    assert tok == "<c" and new_oct == 5  # OCTAVE_UP="<"

def test_octave_down_two_steps():
    # C2(36), 현재 옥타브4 -> ">>" + c, 옥타브 2
    tok, new_oct = midi_note_to_token(36, cur_oct=4)
    assert tok == ">>c" and new_oct == 2
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'midi_note_to_token'`)

- [ ] **Step 3: 구현 추가**

```python
_PITCH = {0: "c", 1: "c+", 2: "d", 3: "d+", 4: "e", 5: "f",
          6: "f+", 7: "g", 8: "g+", 9: "a", 10: "a+", 11: "b"}


def midi_note_to_token(pitch: int, cur_oct: int) -> tuple[str, int]:
    """MIDI 음 → (MML 토큰, 새 현재옥타브). 옥타브 차이만큼 <,> 누적.
    매핑: MIDI 60(C4) = 마비노기 o4 'c'. OCTAVE_UP/DOWN 상수 사용."""
    octave = (pitch - MIDI_C4) // 12 + 4
    name = _PITCH[(pitch - MIDI_C4) % 12]
    diff = octave - cur_oct
    if diff > 0:
        shift = OCTAVE_UP * diff
    elif diff < 0:
        shift = OCTAVE_DOWN * (-diff)
    else:
        shift = ""
    return shift + name, octave
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: PASS (17 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml midi_note_to_token"
```

---

## Task 12: midi_to_mml.py — 폴리포니 축약 정책 (TDD) ★사용자 기여 지점

이 Task의 `reduce_polyphony()`는 **정답이 여러 개인 도메인 결정**이다 (겹친 음 →
최고음? 첫 음? 가장 긴 음?). 실행 서브에이전트는 함수 시그니처+테스트+주석을 만든 뒤
**사용자에게 5~10줄 정책 구현을 요청**한다. 트레이드오프: 최고음=멜로디 보존(보컬곡
유리), 가장 긴 음=베이스/지속음 보존. 기본 권장은 "최고음"(보컬 멜로디 곡 다수).

**Files:**
- Modify: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 작성 (동작 명세)**

```python
from midi_to_mml import reduce_polyphony

def test_reduce_polyphony_highest_at_same_start():
    # 같은 start_tick에 60,64,67 동시 → 최고음 67만
    notes = [(0, 480, 60), (0, 480, 64), (0, 480, 67), (480, 240, 62)]
    assert reduce_polyphony(notes) == [(0, 480, 67), (480, 240, 62)]

def test_reduce_polyphony_overlap_truncates_earlier():
    # 0~480 60, 240~720 64 (겹침) → 최고음 우선, 앞 음은 겹침 전까지
    notes = [(0, 480, 60), (240, 480, 64)]
    out = reduce_polyphony(notes)
    assert (240, 480, 64) in out
    assert all(s + d <= 240 or p == 64 for s, d, p in out)

def test_reduce_polyphony_monophonic_unchanged():
    notes = [(0, 240, 60), (240, 240, 62)]
    assert reduce_polyphony(notes) == notes
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'reduce_polyphony'`)

- [ ] **Step 3: 구현 — ★실행 시 사용자에게 요청**

함수 시그니처/docstring/주석을 먼저 배치하고 사용자 기여를 받는다:

```python
def reduce_polyphony(
    notes: list[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    """겹치는 음을 단선율로 축약 (마비노기 트랙은 모노포닉).
    입력/출력: [(start_tick, dur_tick, midi_pitch)] (start 정렬 가정).
    정책 결정 지점 — 기본 권장: 동시/겹침 시 최고음 우선, 가려진
    앞 음은 겹침 시작 전까지로 절단, 0길이는 제거.
    """
    # TODO(사용자 기여 5~10줄): 위 정책 구현. 트레이드오프는 Task 12 헤더 참조.
    raise NotImplementedError
```

사용자 구현 수령 후 테스트로 검증.

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: PASS (20 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml reduce_polyphony policy"
```

---

## Task 13: midi_to_mml.py — notes_to_mml 단일 트랙 빌드 (TDD) ★사용자 기여 지점

`notes_to_mml`의 옥타브/기본길이 표기 전략은 글자수·가독성을 좌우하는 결정이다
(절대 `o4` 재설정 vs 상대 `<>` 누적, `l` 기본길이 채택 기준). 실행 서브에이전트는
컨텍스트+시그니처를 만든 뒤 **사용자에게 전략 5~10줄을 요청**한다. 기본 권장: 상대
`<>`(연속 음 글자수 적음) + 가장 빈번한 길이를 `l`로.

**Files:**
- Modify: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from midi_to_mml import notes_to_mml

def test_notes_to_mml_basic_sequence():
    # C4 D4 E4 각 4분음표 (ppq480), 시작 옥타브4
    notes = [(0, 480, 60), (480, 480, 62), (960, 480, 64)]
    out = notes_to_mml(notes, ppq=480)
    assert "c" in out and "d" in out and "e" in out
    assert "," not in out  # 단일 트랙

def test_notes_to_mml_inserts_rest_for_gap():
    # 0~480 C4, 960~1440 D4 → 480~960 공백 → r4
    notes = [(0, 480, 60), (960, 480, 62)]
    out = notes_to_mml(notes, ppq=480)
    assert "r4" in out

def test_notes_to_mml_empty():
    assert notes_to_mml([], ppq=480) == ""
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'notes_to_mml'`)

- [ ] **Step 3: 구현 — ★실행 시 사용자에게 전략 요청**

```python
def notes_to_mml(notes: list[tuple[int, int, int]], ppq: int = 480) -> str:
    """단선율 노트 리스트 → MML 트랙 문자열. 공백은 rest로 채움.
    옥타브/기본길이 표기 전략 = 사용자 기여 지점 (Task 13 헤더 트레이드오프).
    기본 권장: 상대 <> 옥타브 시프트 + 최빈 길이를 l 기본값으로.
    """
    if not notes:
        return ""
    notes = sorted(notes)
    parts: list[str] = []
    cur_oct = MABI_DEFAULTS["o"]
    cursor = 0
    # TODO(사용자 기여 5~10줄): l 기본길이 선정 + 루프에서 rest 채움 +
    #   midi_note_to_token / ticks_to_length 조합으로 토큰 생성.
    #   (rest 길이는 ticks_to_length 재사용; 옥타브는 midi_note_to_token 반환값으로 갱신)
    raise NotImplementedError
```

사용자 구현 수령 후 테스트 검증.

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: PASS (23 passed)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml notes_to_mml"
```

---

## Task 14: midi_to_mml.py — 최상위 변환 + N명령 + CLI (TDD)

**Files:**
- Modify: `skills/mabinogi-mml/scripts/midi_to_mml.py`
- Test: `skills/mabinogi-mml/tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import midi_to_mml
import subprocess

def test_midi_to_mml_wraps_and_caps_tracks(tmp_path):
    # 8트랙 SMF지만 max_tracks=6으로 제한 → 6개 콤마구분
    evs = [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")]
    multi = b"MThd" + struct.pack(">IHHH", 6, 1, 8, 480)
    one = b""
    def vlq(n):
        o=bytearray([n&0x7F]); n>>=7
        while n: o.insert(0,(n&0x7F)|0x80); n>>=7
        return bytes(o)
    body = vlq(0)+b"\x90\x3C\x40"+vlq(480)+b"\x80\x3C\x40"+vlq(0)+b"\xFF\x2F\x00"
    chunk = b"MTrk"+struct.pack(">I",len(body))+body
    smf = multi + chunk*8
    p = tmp_path/"x.mid"; p.write_bytes(smf)
    out = midi_to_mml(str(p), max_tracks=6)
    assert out.startswith("MML@") and out.endswith(";")
    assert out.count(",") == 5  # 6 트랙

def test_cli_reads_file(tmp_path):
    evs=[(0,b"\x90\x3C\x40"),(480,b"\x80\x3C\x40")]
    smf = make_smf(480, evs)
    p = tmp_path/"y.mid"; p.write_bytes(smf)
    r = subprocess.run(["python3","scripts/midi_to_mml.py",str(p)],
        cwd=os.path.join(os.path.dirname(__file__),".."),
        capture_output=True,text=True)
    assert r.returncode == 0
    assert r.stdout.strip().startswith("MML@")
```

- [ ] **Step 2: 실패 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_midi_to_mml.py -q`
Expected: FAIL (`cannot import name 'midi_to_mml'`)

- [ ] **Step 3: 구현 추가**

```python
def midi_to_mml(path: str, max_tracks: int = MAX_TRACKS,
                ppq_override: int | None = None) -> str:
    """SMF 파일 → `MML@t1,...;`. 트랙 max_tracks개로 제한(앞에서부터)."""
    data = open(path, "rb").read()
    _, _, ppq = parse_header(data)
    ppq = ppq_override or ppq
    tracks_mml: list[str] = []
    for chunk in split_tracks(data):
        notes = extract_notes(chunk)
        if not notes:
            continue
        tracks_mml.append(notes_to_mml(reduce_polyphony(notes), ppq))
        if len(tracks_mml) >= max_tracks:
            break
    return "MML@" + ",".join(tracks_mml) + ";"


def _main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description="MIDI → 마비노기 모바일 MML")
    p.add_argument("midi", help="SMF(.mid) 파일 경로")
    p.add_argument("--max-tracks", type=int, default=MAX_TRACKS)
    p.add_argument("--ppq", type=int, default=None)
    a = p.parse_args(argv)
    print(midi_to_mml(a.midi, a.max_tracks, a.ppq))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
```

- [ ] **Step 4: 통과 확인**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/ -q`
Expected: PASS (전체 통과, midi+validate 합산)

- [ ] **Step 5: 커밋**

```bash
git add skills/mabinogi-mml/scripts/midi_to_mml.py skills/mabinogi-mml/tests/test_midi_to_mml.py
git commit -m "feat(mabinogi-mml): midi_to_mml top-level convert + CLI"
```

---

## Task 15: references/mml-syntax.md

**Files:**
- Create: `skills/mabinogi-mml/references/mml-syntax.md`

- [ ] **Step 1: 작성**

내용(섹션): 음표 `cdefgab`·임시표 `+`/`-`, 길이 숫자·점음표, `l` 기본길이,
`o`/`<`/`>` 옥타브(MIDI 60=o4 c 매핑·`<`=↑ 관례 명시), `t` 템포, `v` 볼륨,
`r` 쉼표, `n` 절대음높이(N명령), 멀티트랙 `MML@t1,t2,...,t6;`(최대 6).
기본값 표(o4/l4/t120/v8). PC와의 차이 1줄 + 출처 링크(mabicompose.com).

- [ ] **Step 2: 커밋**

```bash
git add skills/mabinogi-mml/references/mml-syntax.md
git commit -m "docs(mabinogi-mml): mml-syntax reference"
```

---

## Task 16: references/mobile-workflow.md

**Files:**
- Create: `skills/mabinogi-mml/references/mobile-workflow.md`

- [ ] **Step 1: 작성**

내용: 모바일 제약(파트당 1200/2400 불확실성 명시, 6화음/6트랙, N명령),
마비꼬 1.5.7+ export 절차(파일>내보내기 → "N 명령 허용" 체크 → ≤6트랙 →
클립보드), MIDI 임포트 시 L64(6tick) 정렬 권장, 게임 내 단계(빈 악보 구입 →
가방>편집 → 붙여넣기 → 미리듣기 → 곡 제목 → 곡 만들기), 박자 갭 수정 팁
(Shift+Delete 갭 제거), Verify Error 대응. 출처 링크.

- [ ] **Step 2: 커밋**

```bash
git add skills/mabinogi-mml/references/mobile-workflow.md
git commit -m "docs(mabinogi-mml): mobile-workflow reference"
```

---

## Task 17: SKILL.md

**Files:**
- Create: `skills/mabinogi-mml/SKILL.md`

- [ ] **Step 1: 작성 (frontmatter + 본문 ≤150줄)**

frontmatter:
```
---
name: mabinogi-mml
description: 마비노기 모바일 작곡(MML 악보) 보조 — 곡명으로 커뮤니티 MML/MIDI 탐색, MIDI→MML 변환, 모바일 제약 검증·압축. "마비노기 악보", "MML 만들어", "마비노기 작곡" 요청에 사용.
---
```
본문 섹션: 능력경계(채보 ❌/마비꼬·게임 조작 ❌/근사 폴백 ⚠), 워크플로우 5단계
(탐색→변환→검증→출력), 스크립트 호출법(`python3 scripts/midi_to_mml.py <mid>`,
`python3 scripts/validate_mml.py @file.txt --json`), 폴백 작곡 가이드(커뮤니티
소스 1순위, 가사 없음, 개인 인게임용·상업 재배포 아님), 출력 포맷(MML +
마비꼬 체크리스트 + 게임 단계 + 검증 리포트), references/ 포인터.

- [ ] **Step 2: 줄 수 확인**

Run: `wc -l skills/mabinogi-mml/SKILL.md`
Expected: ≤150

- [ ] **Step 3: 커밋**

```bash
git add skills/mabinogi-mml/SKILL.md
git commit -m "docs(mabinogi-mml): SKILL.md"
```

---

## Task 18: Makefile — _symlink-skills (CC + Codex) + clean/status

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: 변경 적용**

`SKILLS_CC := $(HOME)/.claude/skills`, `SKILLS_CODEX := $(HOME)/.codex/skills`,
`STANDALONE_SKILLS := mabinogi-mml` 변수 추가. `install: ... _symlink-skills`.
`_symlink-skills` 타깃은 `_symlink-rules`와 동일 패턴 — 각 스킬을 두 디렉토리에
심링크, 기존 비심링크 존재 시 SKIP, 기존 심링크는 교체. `clean`/`status`에
대칭 블록 추가.

```make
SKILLS_CC := $(HOME)/.claude/skills
SKILLS_CODEX := $(HOME)/.codex/skills
STANDALONE_SKILLS := mabinogi-mml
```
```make
install: _register-plugins _symlink-rules _symlink-skills ## Install plugins + rules + skills
```
```make
_symlink-skills:
	@echo "=== Symlink standalone skills (CC + Codex) ==="
	@for tgt in "$(SKILLS_CC)" "$(SKILLS_CODEX)"; do \
		mkdir -p "$$tgt"; \
		for s in $(STANDALONE_SKILLS); do \
			dest="$$tgt/$$s"; src="$(REPO_DIR)/skills/$$s"; \
			if [ -L "$$dest" ]; then rm "$$dest"; \
			elif [ -e "$$dest" ]; then echo "  ! SKIPPED $$s in $$tgt (exists, not symlink)"; continue; \
			fi; \
			ln -s "$$src" "$$dest"; echo "  + $$s -> $$tgt"; \
		done; \
	done
```
`clean`에 제거 블록, `status`에 확인 블록을 rules 패턴과 동일하게 추가
(심링크면 제거/표시, 아니면 스킵/미설치).

- [ ] **Step 2: 드라이 검증 (실제 심링크는 Task 20에서)**

Run: `make -n install | grep symlink-skills` 및 `grep -n _symlink-skills Makefile`
Expected: 타깃 존재, install 의존성에 포함

- [ ] **Step 3: 커밋**

```bash
git add Makefile
git commit -m "build(mabinogi-mml): make install symlinks skill to CC + Codex"
```

---

## Task 19: CLAUDE.md — 플러그인 모델 → standalone 크로스 에이전트 구조

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 재작성**

기존 18개 플러그인 스킬 표/분류는 "레거시 플러그인 스킬(grandfather, 유지)"로
보존하되, 강제 문구를 제거하고 신규 표준을 명문화:
- L3, L7, L12: "플러그인 구조로 관리" → "스킬은 standalone 크로스 에이전트 방식,
  레거시 플러그인 스킬 4종 유지" 톤으로 수정
- `## 스킬 포맷`: `skills/<skill-name>/SKILL.md`(레포 루트) + frontmatter는
  CC·Codex 공통(`name`/`description`) 명시
- `## 새 스킬 추가 절차`: 1) `skills/<skill-name>/` 생성 2) SKILL.md 3) references/
  4) `make install`(양 에이전트 심링크) 5) 커밋. "플러그인 디렉토리에" 문구 삭제
- 마이그레이션 비범위 1줄 명시

context-rot 규칙: CLAUDE.md+rules 합계 토큰 체크 — 순증 크면 다이어트 제안.

- [ ] **Step 2: 일관성 확인**

Run: `grep -n "plugins/<plugin>\|해당 플러그인 디렉토리에" CLAUDE.md`
Expected: 강제 문구 없음(빈 결과 또는 레거시 설명 맥락만)

- [ ] **Step 3: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: 플러그인 모델 → standalone 크로스 에이전트 스킬 구조"
```

---

## Task 20: 통합 검증 — make install + 양 에이전트 심링크 확인

**Files:** (없음 — 검증 전용)

- [ ] **Step 1: 전체 테스트**

Run: `cd skills/mabinogi-mml && python3 -m pytest tests/ -q`
Expected: 전체 PASS, 0 failures

- [ ] **Step 2: make install 후 심링크 확인**

Run:
```bash
make install
ls -l ~/.claude/skills/mabinogi-mml ~/.codex/skills/mabinogi-mml
make status | grep -A3 skills
```
Expected: 두 경로 모두 worktree `skills/mabinogi-mml`로의 심링크. status에 `+ mabinogi-mml`.

- [ ] **Step 3: 스크립트 e2e 스모크**

Run:
```bash
cd skills/mabinogi-mml
python3 scripts/validate_mml.py "MML@cdef,cde;" --json
```
Expected: JSON, `"ok": false`, 디싱크 위반 포함, exit 1.

- [ ] **Step 4: 커밋 (검증 로그/CHANGELOG 갱신 시)**

```bash
git add -A
git commit -m "chore(mabinogi-mml): integration verification" --allow-empty
```

---

## Self-Review

**1. Spec coverage:**
- 목적/워크플로우(spec §1,6) → Task 17 SKILL.md + 2,3,7~14 스크립트 ✓
- 검증된 사실/제약(spec §2) → Task 3(글자수/트랙) 4(디싱크) 5(템포) 16(레퍼런스) ✓
- 능력경계(spec §3) → Task 17 SKILL.md 명시 ✓
- 크로스에이전트 아키텍처(spec §4) → Task 1 구조 + Task 18 심링크 + Task 20 검증 ✓
- CLAUDE.md 폐기 범위(spec §5) → Task 19, 레거시 grandfather 명시 ✓
- 컴포넌트 경계(spec §7) → 스크립트 stdlib·LLM subprocess 없음, Task 2~14 ✓
- 테스트 전략(spec §8) → 각 Task TDD, 글자수초과/7트랙/템포/디싱크/양자화 커버 ✓
- 저작권/스코프(spec §9) → Task 17 폴백 가이드(가사 없음·인게임용) ✓
- 비목표(spec §11) → plan 헤더 YAGNI + 단순화 명시 ✓

**2. Placeholder scan:** Task 12·13의 `raise NotImplementedError` + `TODO(사용자
기여)`는 learning 모드 의도적 기여 지점(테스트가 동작 명세 고정). 그 외 모든
스텝은 실제 코드/명령 포함. 통상적 플레이스홀더 없음. ✓

**3. Type consistency:** `parse_tracks`→`check_limits`/`check_desync`/
`check_tempo_placement`→`validate` 시그니처 일관. `read_vlq`→`extract_notes`,
`(start,dur,pitch)` 튜플 표기 Task 9~14 통일, `midi_note_to_token`/
`ticks_to_length`/`reduce_polyphony`/`notes_to_mml`/`midi_to_mml` 호출 체인
인자명·반환형 일치. 상수(MAX_TRACKS, MIDI_C4, OCTAVE_UP/DOWN, MABI_DEFAULTS)
양 스크립트에서 동일 정의(파일 내 DRY). ✓

갭 없음. 인라인 수정 불필요.
