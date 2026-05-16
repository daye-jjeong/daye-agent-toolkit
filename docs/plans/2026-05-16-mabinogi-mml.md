# mabinogi-mml Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 곡명 → (커뮤니티 MML/MIDI 탐색 또는 폴백 작곡) → 마비노기 모바일 제약 검증을 거친 붙여넣기용 MML을 만드는, 플러그인 비소속 CC·Codex 크로스 에이전트 스킬을 구축한다.

**Architecture:** 단일 소스 `skills/mabinogi-mml/`(레포 루트, plugins/ 밖). 결정적 로직은 Python stdlib 스크립트 2개(`midi_to_mml.py` 변환, `validate_mml.py` 검증), LLM 프레임워크는 `SKILL.md`+`references/`. `make install`이 `~/.claude/skills/`·`~/.codex/skills/`에 심링크해 양 에이전트 네이티브 발견. CLAUDE.md 플러그인 모델은 standalone 구조로 재작성.

**Tech Stack:** Python 3.12 stdlib only (`struct`, `re`, `argparse`, `json`), Markdown, GNU Make, pytest.

**Adversarial review 반영 (v2):**
- F1: SMF 파서 **실패-폐쇄형** — 헤더/청크 검증, 미지원은 명시 에러, 변환 손실(unmatched note·skipped chunk·quantization error)을 **리포트로 노출**. format-1/meta/sysex/triplet golden test.
- F2: `validate_mml`의 `N` 명령은 길이 0이 아니라 **현재 기본길이 음표**로 계산. `check_desync`는 hard-fail이 아닌 **warning**(인트로/아웃트로 길이차 정상), `--strict`로 승격.
- F3: `make clean/status` 실제 코드 plan에 명시, 비심링크 충돌은 **가시적 경고 + status에 x 표시**, Task 20에 양 에이전트 discovery smoke. (CC 비플러그인 발견은 실증됨 — `~/.claude/skills/`의 심링크 스킬들이 현 세션 available-skills에 노출.)
- F4: CLAUDE.md 플러그인 모델 **완전폐기 유지** — 사용자 명시 지시(instruction priority). 기존 18개 스킬은 물리적 유지(grandfather), 문서 표준만 교체.
- F5: 학습 기여점(Task 11 `reduce_polyphony`, Task 13 `notes_to_mml`)은 유지하되 **음악 불변식 테스트**(모노포닉 불변·tick 길이 round-trip)로 정합성 고정.

**실행 중 사용자 기여 지점 (learning):** Task 11(폴리포니 축약 정책), Task 13(옥타브/기본길이 표기 전략) — 정답 복수, 도메인 판단. 서브에이전트는 시그니처+컨텍스트+불변식 테스트를 만든 뒤 사용자에게 5~10줄 구현을 요청.

**알려진 단순화 (v1, YAGNI):** MIDI 트랙 내 겹치는 음은 단선율로 축약(정책 Task 11). 진짜 화음은 트랙 분리로만. 변환은 best-effort이며 **손실은 숨기지 않고 리포트로 출력**(SKILL.md에 명시). triplet/긴음표는 양자화 오차로 리포트.

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
    midi_to_mml.py          생성 — SMF 파싱 → MML (+변환 리포트)
    validate_mml.py         생성 — 모바일 제약 검증 + 압축 제안
  tests/
    test_validate_mml.py    생성
    test_midi_to_mml.py     생성 (SMF 픽스처 헬퍼 내장)
Makefile                    수정 — _symlink-skills + clean/status 대칭 (실제 코드)
CLAUDE.md                   수정 — 플러그인 모델 → standalone 크로스 에이전트
```

**공유 상수 (각 스크립트 상단, 파일 내 DRY):**
- `MAX_TRACKS = 6`, `MAX_CHARS_PER_PART = 1200`  # 1200/2400 상이. 보수적 기본. `--max-chars` override.
- `MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}`
- `OCTAVE_UP, OCTAVE_DOWN = "<", ">"`, `MIDI_C4 = 60`

**데이터 계약 (태스크 간 타입 일관성):**
- `read_vlq(data,pos) -> (int, int)`
- `parse_header(data) -> (fmt:int, ntrks:int, division:int)` — 검증 실패 시 `ValueError`
- `split_tracks(data) -> list[bytes]` — 절단/MTrk수 불일치 시 `ValueError`
- `extract_notes(chunk) -> (notes:list[(start,dur,pitch)], stats:dict)` stats=`{"unmatched_on","unmatched_off","skipped_events"}`
- `ticks_to_length(ticks,ppq) -> (length:str, err_ticks:int)`
- `midi_note_to_token(pitch,cur_oct) -> (token:str, new_oct:int)`
- `reduce_polyphony(notes) -> notes` (모노포닉 불변)
- `notes_to_mml(notes,ppq) -> str`
- `quantization_error(notes,ppq) -> int`
- `convert(path,max_tracks,ppq_override) -> {"mml":str,"report":dict}`
- `midi_to_mml(path,...) -> str` = `convert(...)["mml"]`
- `validate(mml,max_tracks,max_chars,ppq,strict) -> {"ok","tracks","violations","warnings","suggestions"}`

---

## Task 1: 스킬 디렉토리 + 메타 파일 스캐폴드

**Files:** Create `skills/mabinogi-mml/VERSION`, `CHANGELOG.md`, dirs `scripts/ references/ tests/`

- [ ] **Step 1: 디렉토리 + VERSION + CHANGELOG**

```bash
mkdir -p skills/mabinogi-mml/scripts skills/mabinogi-mml/references skills/mabinogi-mml/tests
printf '0.1.0\n' > skills/mabinogi-mml/VERSION
cat > skills/mabinogi-mml/CHANGELOG.md <<'EOF'
# Changelog

## 0.1.0 (2026-05-16)
- 최초 릴리스: MIDI→MML 변환(+손실 리포트), 모바일 제약 검증, 소스 탐색 워크플로우.
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

**Files:** Create `skills/mabinogi-mml/scripts/validate_mml.py`, Test `tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트**

```python
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

- [ ] **Step 2: 실패 확인** — Run: `cd skills/mabinogi-mml && python3 -m pytest tests/test_validate_mml.py -q` → FAIL (ImportError)

- [ ] **Step 3: 최소 구현**

```python
"""마비노기 모바일 MML 제약 검증 + 압축 제안. stdlib only."""
import re

MAX_TRACKS = 6
MAX_CHARS_PER_PART = 1200  # 1200/2400 소스 상이. 보수적 기본. 게임 실측 후 조정.
MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}


def parse_tracks(mml: str) -> list[str]:
    """`MML@t1,t2,...;` → 트랙 리스트. 래퍼 없으면 단일 트랙."""
    s = mml.strip()
    if s.upper().startswith("MML@"):
        s = s[4:]
    if s.endswith(";"):
        s = s[:-1]
    return s.split(",")
```

- [ ] **Step 4: 통과 확인** — PASS (3)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): validate_mml parse_tracks"`

---

## Task 3: validate_mml.py — 트랙 수 / 글자수 검증 (TDD)

**Files:** Modify `scripts/validate_mml.py`, Test `tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import check_limits

def test_check_limits_ok():
    assert check_limits(["abc", "def"], 6, 1200) == []

def test_check_limits_too_many_tracks():
    assert any("트랙" in m and "7" in m for m in check_limits(["a"]*7, 6, 1200))

def test_check_limits_char_overflow_reports_index():
    v = check_limits(["x"*1201, "ok"], 6, 1200)
    assert any("트랙 1" in m and "1201" in m for m in v)
    assert not any("트랙 2" in m for m in v)
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
def check_limits(tracks: list[str], max_tracks: int = MAX_TRACKS,
                 max_chars: int = MAX_CHARS_PER_PART) -> list[str]:
    """제약 위반(violations). 빈 리스트면 통과."""
    v: list[str] = []
    if len(tracks) > max_tracks:
        v.append(f"트랙 수 {len(tracks)}개 — 최대 {max_tracks}개 초과")
    for i, t in enumerate(tracks, 1):
        if len(t) > max_chars:
            v.append(f"트랙 {i} 글자수 {len(t)} — 파트당 최대 {max_chars} 초과")
    return v
```

- [ ] **Step 4: 통과 확인** — PASS (6)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): validate_mml check_limits"`

---

## Task 4: validate_mml.py — tick 길이(N명령 포함) + 디싱크 warning (TDD)

**F2 반영:** `N` 명령은 현재 기본길이 음표로 계산(길이 0 아님). `check_desync`는
warning 레벨 메시지를 반환(인트로/아웃트로 길이차는 정상이므로 hard-fail 금지).

**Files:** Modify `scripts/validate_mml.py`, Test `tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import track_tick_length, check_desync

def test_tick_length_quarter_default_l4():
    assert track_tick_length("cdef", 480) == 4*480

def test_tick_length_explicit_and_rest():
    assert track_tick_length("c8r4e2", 480) == 240+480+960

def test_tick_length_dotted():
    assert track_tick_length("c4.", 480) == 720

def test_tick_length_N_command_counts_as_default_length_note():
    # F2: n60 은 길이 0 아님 — 기본 l4 음표 = 480 tick
    assert track_tick_length("n60n62", 480) == 2*480

def test_tick_length_N_command_respects_l_default():
    assert track_tick_length("l8n60n62", 480) == 2*240

def test_check_desync_returns_warning_on_mismatch():
    w = check_desync(["cdef", "cde"], 480)
    assert w and ("디싱크" in w[0] or "길이" in w[0])

def test_check_desync_empty_when_equal():
    assert check_desync(["cdef", "cdef"], 480) == []
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
_TOKEN_RE = re.compile(
    r"(?P<note>[a-gA-G])(?P<acc>[+#-]?)(?P<len>\d*)(?P<dot>\.*)"
    r"|(?P<rest>[rR])(?P<rlen>\d*)(?P<rdot>\.*)"
    r"|[nN](?P<npitch>\d+)(?P<nlen>\d*)(?P<ndot>\.*)"
    r"|[lL](?P<ldef>\d+)"
    r"|[oO]\d+|[<>]|[tT]\d+|[vV]\d+"
)


def _len_to_ticks(length: int, dots: int, ppq: int) -> int:
    base = (4 * ppq) // length
    total = add = base
    for _ in range(dots):
        add //= 2
        total += add
    return total


def track_tick_length(track: str, ppq: int = 480) -> int:
    """총 연주 길이(tick). l 기본길이/점음표/쉼표/N명령 반영. o<>tv는 0."""
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
        elif m.group("npitch"):  # F2: N명령 = 음표, 길이는 명시 또는 기본 l
            ln = int(m.group("nlen")) if m.group("nlen") else cur_l
            total += _len_to_ticks(ln, len(m.group("ndot")), ppq)
    return total


def check_desync(tracks: list[str], ppq: int = 480) -> list[str]:
    """트랙 길이 불일치 = warning(곡 구조상 정상일 수 있음, hard-fail 아님)."""
    lengths = [track_tick_length(t, ppq) for t in tracks if t.strip()]
    if len(set(lengths)) > 1:
        return [f"트랙 길이 불일치(디싱크 가능, 인트로/아웃트로면 정상): "
                f"{lengths} tick — --strict 시 위반 처리"]
    return []
```

- [ ] **Step 4: 통과 확인** — PASS (13)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): tick length (N-aware) + desync warning"`

---

## Task 5: validate_mml.py — 템포 위치 warning + 압축 제안 (TDD)

**Files:** Modify `scripts/validate_mml.py`, Test `tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import check_tempo_placement, suggest_compression

def test_tempo_mid_track_warns():
    assert any("트랙 2" in m and "템포" in m
               for m in check_tempo_placement(["t120cdef", "cdt140ef"]))

def test_tempo_at_start_ok():
    assert check_tempo_placement(["t120cdef", "t120cdef"]) == []

def test_suggest_compression_repeated_length():
    assert any("l8" in x for x in suggest_compression("c8d8e8f8g8a8"))

def test_suggest_compression_clean_no_suggestion():
    assert suggest_compression("l4cdef") == []
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
def check_tempo_placement(tracks: list[str]) -> list[str]:
    """t가 트랙 첫 음표 뒤면 warning(모바일 박자 어긋남 흔한 원인)."""
    w: list[str] = []
    for i, t in enumerate(tracks, 1):
        fn = re.search(r"[a-gA-Gr]", t)
        for tm in re.finditer(r"[tT]\d+", t):
            if fn and tm.start() > fn.start():
                w.append(f"트랙 {i}: 음표 뒤 템포({tm.group()}) — "
                         f"모바일 박자 어긋남 위험, 트랙 맨 앞 권장")
                break
    return w


def suggest_compression(track: str) -> list[str]:
    """글자수 절약 제안(텍스트만, 자동수정 안 함 — 위험)."""
    out: list[str] = []
    lengths = re.findall(r"[a-gA-G][+#-]?(\d+)", track)
    if lengths:
        from collections import Counter
        common, cnt = Counter(lengths).most_common(1)[0]
        if cnt >= 4:
            out.append(f"길이 {common} {cnt}회 — `l{common}` 기본길이로 절약")
    # N 제안은 옥타브 명령이 있을 때만 의미(절대음높이로 옥타브 명령 절약).
    if "n" not in track.lower() and re.search(r"[oO]\d+|[<>]", track):
        out.append("`N` 명령으로 옥타브 명령 생략 가능 "
                    "(마비꼬 export 'N 명령 허용' 체크)")
    return out
```

- [ ] **Step 4: 통과 확인** — PASS (17)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): tempo placement + compression hints"`

---

## Task 6: validate_mml.py — validate() (violations/warnings 분리) + CLI (TDD)

**F2 반영:** `validate`는 `violations`(글자수/트랙=hard)와 `warnings`(디싱크/템포=soft)
분리. `strict=True`면 warnings도 ok=False. CLI exit code는 ok 기준.

**Files:** Modify `scripts/validate_mml.py`, Test `tests/test_validate_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from validate_mml import validate
import subprocess, json

def test_validate_desync_is_warning_not_violation():
    rep = validate("MML@t120cdef,t120cde;")
    assert rep["violations"] == []        # 디싱크는 violation 아님
    assert any("디싱크" in w or "길이" in w for w in rep["warnings"])
    assert rep["ok"] is True              # 비strict면 통과

def test_validate_strict_promotes_warning():
    rep = validate("MML@t120cdef,t120cde;", strict=True)
    assert rep["ok"] is False

def test_validate_charlimit_is_violation():
    rep = validate("MML@" + "x"*1201 + ";", max_chars=1200)
    assert rep["ok"] is False and rep["violations"]

def test_validate_clean_passes():
    rep = validate("MML@t120cdef,t120cdef;")
    assert rep["ok"] is True and rep["violations"] == [] and rep["warnings"] == []

def test_cli_exit_code_and_json():
    out = subprocess.run(
        ["python3", "scripts/validate_mml.py", "--json", "--strict",
         "MML@cdef,cde;"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        capture_output=True, text=True)
    assert out.returncode == 1
    assert json.loads(out.stdout)["ok"] is False
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
def validate(mml: str, max_tracks: int = MAX_TRACKS,
             max_chars: int = MAX_CHARS_PER_PART, ppq: int = 480,
             strict: bool = False) -> dict:
    tracks = parse_tracks(mml)
    violations = check_limits(tracks, max_tracks, max_chars)
    warnings = check_desync(tracks, ppq) + check_tempo_placement(tracks)
    suggestions = [f"트랙 {i}: {s}"
                   for i, t in enumerate(tracks, 1)
                   for s in suggest_compression(t)]
    ok = not violations and (not warnings if strict else True)
    return {"ok": ok, "tracks": len(tracks), "violations": violations,
            "warnings": warnings, "suggestions": suggestions}


def _main(argv: list[str]) -> int:
    import argparse, json
    p = argparse.ArgumentParser(description="마비노기 모바일 MML 검증")
    p.add_argument("mml", help="MML 문자열 또는 @파일경로")
    p.add_argument("--max-chars", type=int, default=MAX_CHARS_PER_PART)
    p.add_argument("--max-tracks", type=int, default=MAX_TRACKS)
    p.add_argument("--ppq", type=int, default=480)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    text = a.mml
    if text.startswith("@"):
        with open(text[1:], encoding="utf-8") as f:
            text = f.read().strip()
    rep = validate(text, a.max_tracks, a.max_chars, a.ppq, a.strict)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False))
    else:
        print("OK" if rep["ok"] else "FAIL")
        for x in rep["violations"]:
            print(f"  ✗ {x}")
        for x in rep["warnings"]:
            print(f"  ⚠ {x}")
        for x in rep["suggestions"]:
            print(f"  · {x}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
```

- [ ] **Step 4: 통과 확인** — `python3 -m pytest tests/test_validate_mml.py -q` PASS (22)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): validate() violations/warnings split + CLI"`

---

## Task 7: midi_to_mml.py — SMF 픽스처 헬퍼 + read_vlq (TDD)

**Files:** Create `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 (픽스처 헬퍼 포함)**

```python
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from midi_to_mml import read_vlq


def _vlq(n: int) -> bytes:
    o = bytearray([n & 0x7F]); n >>= 7
    while n:
        o.insert(0, (n & 0x7F) | 0x80); n >>= 7
    return bytes(o)


def make_smf(ppq: int, events: list[tuple[int, bytes]], fmt: int = 0,
             ntrks: int = 1) -> bytes:
    """최소 SMF. events=[(delta, raw_event_bytes)]. EOT 자동 append."""
    trk = bytearray()
    for delta, ev in events:
        trk += _vlq(delta) + ev
    trk += _vlq(0) + b"\xFF\x2F\x00"
    head = b"MThd" + struct.pack(">IHHH", 6, fmt, ntrks, ppq)
    track = b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
    return head + track


def test_read_vlq_single_byte():
    assert read_vlq(b"\x40", 0) == (0x40, 1)

def test_read_vlq_multi_byte():
    assert read_vlq(b"\x81\x00", 0) == (128, 2)

def test_read_vlq_offset():
    assert read_vlq(b"\xFF\x81\x00", 1) == (128, 3)
```

- [ ] **Step 2: 실패 확인** → FAIL (ImportError)
- [ ] **Step 3: 최소 구현**

```python
"""MIDI(SMF) → 마비노기 모바일 MML (+변환 손실 리포트). stdlib only.
손상/비표준 입력은 조용히 통과시키지 않고 ValueError 또는 리포트로 노출한다."""
import struct

MAX_TRACKS = 6
MIDI_C4 = 60
MABI_DEFAULTS = {"o": 4, "l": 4, "t": 120, "v": 8}
OCTAVE_UP, OCTAVE_DOWN = "<", ">"


def read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    """가변길이 수량 → (value, next_pos)."""
    value = 0
    while True:
        b = data[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            return value, pos
```

- [ ] **Step 4: 통과 확인** — PASS (3)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): read_vlq + SMF fixture helper"`

---

## Task 8: midi_to_mml.py — parse_header + split_tracks (실패-폐쇄형, TDD)

**F1 반영:** 헤더 길이/포맷 검증, MTrk 수 불일치·절단 시 `ValueError`. 조용한 break 금지.

**Files:** Modify `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import parse_header, split_tracks
import pytest

def test_parse_header_ok():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    assert parse_header(smf) == (0, 1, 480)

def test_parse_header_rejects_non_mthd():
    with pytest.raises(ValueError):
        parse_header(b"XXXX" + b"\x00"*10)

def test_parse_header_rejects_smpte_division():
    bad = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 0x8000) + b"MTrk\x00\x00\x00\x00"
    with pytest.raises(ValueError):
        parse_header(bad)

def test_split_tracks_one_chunk():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    chunks = split_tracks(smf)
    assert len(chunks) == 1 and chunks[0].endswith(b"\xFF\x2F\x00")

def test_split_tracks_raises_on_truncation():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    with pytest.raises(ValueError):
        split_tracks(smf[:-3])  # MTrk 본문 절단

def test_split_tracks_raises_on_ntrks_mismatch():
    # 헤더는 2트랙 선언, 실제 1트랙
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")],
                   ntrks=2)
    with pytest.raises(ValueError):
        split_tracks(smf)
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
def parse_header(data: bytes) -> tuple[int, int, int]:
    """MThd 검증·파싱 → (format, ntrks, division). 비표준은 ValueError."""
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("MThd 청크 없음 — 유효한 SMF 아님")
    length, fmt, ntrks, division = struct.unpack(">IHHH", data[4:14])
    if length != 6:
        raise ValueError(f"MThd 길이 {length} ≠ 6 — 손상 의심")
    if fmt not in (0, 1, 2):
        raise ValueError(f"미지원 SMF format {fmt}")
    if division & 0x8000:
        raise ValueError("SMPTE division 미지원 (PPQ 형식만)")
    return fmt, ntrks, division


def split_tracks(data: bytes) -> list[bytes]:
    """MTrk 본문 리스트. 선언 ntrks와 불일치하거나 절단되면 ValueError."""
    _, ntrks, _ = parse_header(data)
    chunks: list[bytes] = []
    pos = 14
    while pos < len(data):
        if data[pos:pos + 4] != b"MTrk":
            raise ValueError(f"오프셋 {pos}: MTrk 아닌 청크 — 손상/미지원")
        (length,) = struct.unpack(">I", data[pos + 4:pos + 8])
        end = pos + 8 + length
        if end > len(data):
            raise ValueError("MTrk 본문 절단 — 손상 파일")
        chunks.append(data[pos + 8:end])
        pos = end
    if len(chunks) != ntrks:
        raise ValueError(f"MTrk 수 {len(chunks)} ≠ 헤더 선언 {ntrks}")
    return chunks
```

- [ ] **Step 4: 통과 확인** — PASS (9)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): fail-closed parse_header + split_tracks"`

---

## Task 9: midi_to_mml.py — extract_notes + 손실 통계 (TDD)

**F1 반영:** unmatched note-on/off, skipped 이벤트를 stats로 반환(조용히 버리지 않음).
러닝스테이터스·vel0=off·meta/sysex 길이 스킵 처리.

**Files:** Modify `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import extract_notes

def test_extract_single_note_and_clean_stats():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    notes, stats = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 480, 60)]
    assert stats == {"unmatched_on": 0, "unmatched_off": 0,
                     "skipped_events": 0}

def test_vel0_noteon_is_off():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (240, b"\x90\x3C\x00")])
    notes, _ = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 240, 60)]

def test_running_status():
    smf = make_smf(480, [(0, b"\x90\x3C\x40"), (0, b"\x3E\x40"),
                         (480, b"\x80\x3C\x40"), (0, b"\x3E\x40")])
    notes, _ = extract_notes(split_tracks(smf)[0])
    assert sorted(notes) == [(0, 480, 60), (0, 480, 62)]

def test_meta_and_sysex_skipped_counted():
    # tempo meta(FF 51 03) + sysex(F0..F7) 사이 노트
    smf = make_smf(480, [
        (0, b"\xFF\x51\x03\x07\xA1\x20"),
        (0, b"\xF0\x02\x11\xF7"),
        (0, b"\x90\x3C\x40"), (480, b"\x80\x3C\x40")])
    notes, stats = extract_notes(split_tracks(smf)[0])
    assert notes == [(0, 480, 60)]
    assert stats["skipped_events"] >= 2

def test_unmatched_note_on_counted():
    # note-on 후 off 없음 → unmatched_on 1
    smf = make_smf(480, [(0, b"\x90\x3C\x40")])
    notes, stats = extract_notes(split_tracks(smf)[0])
    assert notes == [] and stats["unmatched_on"] == 1
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
def extract_notes(chunk: bytes) -> tuple[list[tuple[int, int, int]], dict]:
    """트랙 청크 → ([(start,dur,pitch)], stats). 손실 통계 명시."""
    pos = abs_tick = status = 0
    pending: dict[int, list[int]] = {}
    notes: list[tuple[int, int, int]] = []
    stats = {"unmatched_on": 0, "unmatched_off": 0, "skipped_events": 0}
    n = len(chunk)
    while pos < n:
        delta, pos = read_vlq(chunk, pos)
        abs_tick += delta
        b = chunk[pos]
        if b & 0x80:
            status = b
            pos += 1
        ev = status & 0xF0
        if ev in (0x80, 0x90):
            pitch, vel = chunk[pos], chunk[pos + 1]
            pos += 2
            if ev == 0x90 and vel > 0:
                pending.setdefault(pitch, []).append(abs_tick)
            else:
                if pending.get(pitch):
                    start = pending[pitch].pop(0)
                    notes.append((start, abs_tick - start, pitch))
                else:
                    stats["unmatched_off"] += 1
        elif ev in (0xA0, 0xB0, 0xE0):
            pos += 2
            stats["skipped_events"] += 1
        elif ev in (0xC0, 0xD0):
            pos += 1
            stats["skipped_events"] += 1
        elif status == 0xFF:
            mtype = chunk[pos]
            pos += 1
            mlen, pos = read_vlq(chunk, pos)
            pos += mlen
            if mtype == 0x2F:
                break  # EOT는 구조 마커 — 변환 손실 아니므로 skipped 제외
            stats["skipped_events"] += 1
        elif status in (0xF0, 0xF7):
            slen, pos = read_vlq(chunk, pos)
            pos += slen
            stats["skipped_events"] += 1
        else:
            raise ValueError(f"미지원 상태 바이트 {status:#x} @ {pos}")
    stats["unmatched_on"] = sum(len(v) for v in pending.values())
    return notes, stats
```

- [ ] **Step 4: 통과 확인** — PASS (14)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): extract_notes + loss stats"`

---

## Task 10: midi_to_mml.py — ticks_to_length (양자화 오차 반환, TDD)

**F1 반영:** 양자화 오차(err_ticks)를 함께 반환 → 상위에서 손실 리포트. triplet/긴음표
스냅 손실을 숨기지 않음.

**Files:** Modify `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import ticks_to_length

def test_quarter_zero_error():
    assert ticks_to_length(480, 480) == ("4", 0)

def test_eighth_zero_error():
    assert ticks_to_length(240, 480) == ("8", 0)

def test_dotted_quarter():
    assert ticks_to_length(720, 480) == ("4.", 0)

def test_near_value_snaps_with_error():
    s, err = ticks_to_length(470, 480)
    assert s == "4" and err == 10

def test_triplet_eighth_reports_error():
    # 8분 셋잇단 ≈ 160 tick. 표현 불가 → 가까운 길이 + 0 아닌 err
    s, err = ticks_to_length(160, 480)
    assert err > 0
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
_LEN_TABLE: list[tuple[float, str]] = []
for _b in (1, 2, 4, 8, 16, 32, 64):
    _LEN_TABLE.append((4.0 / _b, str(_b)))
    _LEN_TABLE.append((4.0 / _b * 1.5, f"{_b}."))


def ticks_to_length(ticks: int, ppq: int = 480) -> tuple[str, int]:
    """tick → (가장 가까운 MML 길이, 양자화 오차 tick절댓값)."""
    quarters = ticks / ppq
    val, label = min(_LEN_TABLE, key=lambda c: abs(c[0] - quarters))
    err = abs(round(val * ppq) - ticks)
    return label, err
```

- [ ] **Step 4: 통과 확인** — PASS (19)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): ticks_to_length with quant error"`

---

## Task 11: midi_to_mml.py — reduce_polyphony (TDD) ★사용자 기여 지점

핵심 음악 결정(겹친 음 → 최고음/첫음/최장음). **불변식 테스트**가 음악 정합성을
고정한다(F5): 출력은 모노포닉(구간 겹침 없음). 서브에이전트는 시그니처+불변식
테스트를 만든 뒤 사용자에게 5~10줄 정책 구현을 요청. 기본 권장: 최고음 우선.

**Files:** Modify `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 (동작 + 불변식)**

```python
from midi_to_mml import reduce_polyphony

def _monophonic(notes):
    s = sorted(notes)
    return all(s[i][0] + s[i][1] <= s[i+1][0] for i in range(len(s)-1))

def test_highest_at_same_start():
    out = reduce_polyphony([(0,480,60),(0,480,64),(0,480,67),(480,240,62)])
    assert out == [(0,480,67),(480,240,62)]

def test_monophonic_unchanged():
    n = [(0,240,60),(240,240,62)]
    assert reduce_polyphony(n) == n

def test_invariant_output_is_monophonic():
    # 불변식: 어떤 입력이든 출력은 구간 비겹침 (F5 음악 정합성 고정)
    n = [(0,480,60),(120,480,64),(300,200,67),(900,480,62)]
    assert _monophonic(reduce_polyphony(n))

def test_invariant_no_zero_or_negative_duration():
    out = reduce_polyphony([(0,480,60),(240,480,64)])
    assert all(d > 0 for _, d, _ in out)
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 — ★실행 시 사용자에게 요청**

시그니처/docstring/주석 배치 후 사용자 기여 수령:

```python
def reduce_polyphony(
    notes: list[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    """겹치는 음을 단선율로 축약 (마비노기 트랙은 모노포닉).
    in/out: [(start_tick,dur_tick,midi_pitch)].
    불변식(테스트 강제): 출력은 구간 비겹침, dur>0.
    정책 결정 — 기본 권장: 동시/겹침 시 최고음, 가린 앞음은 절단, 0길이 제거.
    """
    # TODO(사용자 기여 5~10줄): 위 정책. 불변식 테스트가 정합성 가드.
    raise NotImplementedError
```

사용자 구현 수령 → 테스트 검증.

- [ ] **Step 4: 통과 확인** — PASS (23)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): reduce_polyphony policy"`

---

## Task 12: midi_to_mml.py — midi_note_to_token (TDD)

**Files:** Modify `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import midi_note_to_token

def test_c4_no_shift():
    assert midi_note_to_token(60, 4) == ("c", 4)

def test_sharp():
    assert midi_note_to_token(61, 4) == ("c+", 4)

def test_octave_up():
    assert midi_note_to_token(72, 4) == ("<c", 5)

def test_octave_down_two():
    assert midi_note_to_token(36, 4) == (">>c", 2)
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
_PITCH = {0:"c",1:"c+",2:"d",3:"d+",4:"e",5:"f",
          6:"f+",7:"g",8:"g+",9:"a",10:"a+",11:"b"}


def midi_note_to_token(pitch: int, cur_oct: int) -> tuple[str, int]:
    """MIDI 음 → (MML 토큰, 새 옥타브). MIDI60=o4 c. OCTAVE_UP/DOWN 사용."""
    octave = (pitch - MIDI_C4) // 12 + 4
    name = _PITCH[(pitch - MIDI_C4) % 12]
    diff = octave - cur_oct
    shift = OCTAVE_UP*diff if diff > 0 else OCTAVE_DOWN*(-diff) if diff < 0 else ""
    return shift + name, octave
```

- [ ] **Step 4: 통과 확인** — PASS (27)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): midi_note_to_token"`

---

## Task 13: midi_to_mml.py — notes_to_mml + quantization_error (TDD) ★사용자 기여 지점

옥타브/기본길이 표기 전략(글자수·가독성). **불변식 테스트**가 정합성 고정(F5):
`track_tick_length(notes_to_mml(notes)) == Σ dur` (rest 포함, round-trip).
서브에이전트는 컨텍스트+불변식 테스트 후 사용자에게 전략 5~10줄 요청. 기본 권장:
상대 `<>` + 최빈 길이를 `l`. `quantization_error`는 변환 손실 합(별도 함수, 기여 무관).

**Files:** Modify `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 (동작 + round-trip 불변식)**

```python
from midi_to_mml import notes_to_mml, quantization_error
from validate_mml import track_tick_length  # round-trip 검증용

def test_basic_sequence():
    out = notes_to_mml([(0,480,60),(480,480,62),(960,480,64)], 480)
    assert "c" in out and "d" in out and "e" in out and "," not in out

def test_rest_for_gap():
    assert "r" in notes_to_mml([(0,480,60),(960,480,62)], 480)

def test_empty():
    assert notes_to_mml([], 480) == ""

def test_invariant_round_trip_tick_length():
    # F5: 생성 MML의 총 tick = 원본 음표+gap 합 (양자화 0인 정렬 입력)
    notes = [(0,480,60),(480,240,62),(960,480,64)]
    span = 960 + 480  # 마지막 끝
    assert track_tick_length(notes_to_mml(notes, 480), 480) == span

def test_quantization_error_zero_for_aligned():
    assert quantization_error([(0,480,60),(480,240,62)], 480) == 0

def test_quantization_error_positive_for_triplet():
    assert quantization_error([(0,160,60)], 480) > 0
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현**

`quantization_error`는 즉시 구현(기여 무관):

```python
def quantization_error(notes: list[tuple[int, int, int]],
                       ppq: int = 480) -> int:
    """각 음표 duration 양자화 오차 합(tick). 변환 손실 리포트용."""
    return sum(ticks_to_length(d, ppq)[1] for _, d, _ in notes)
```

`notes_to_mml`은 ★실행 시 사용자에게 전략 요청 (시그니처/주석 선배치):

```python
def notes_to_mml(notes: list[tuple[int, int, int]], ppq: int = 480) -> str:
    """단선율 → MML 트랙. 공백은 rest로 채움.
    불변식(테스트 강제): track_tick_length(반환) == 음표+gap 총 tick.
    옥타브/기본길이 전략 = 사용자 기여. 기본 권장: 상대 <> + 최빈 l.
    helper: midi_note_to_token, ticks_to_length(라벨만 사용).
    """
    if not notes:
        return ""
    notes = sorted(notes)
    # TODO(사용자 기여 5~10줄): l 기본길이 + 루프(gap→rest, note→token).
    #   rest 길이/음표 길이는 ticks_to_length(...)[0] 라벨 사용.
    #   옥타브는 midi_note_to_token 반환 new_oct로 갱신.
    raise NotImplementedError
```

사용자 구현 수령 → 테스트(특히 round-trip 불변식) 검증.

- [ ] **Step 4: 통과 확인** — PASS (33)
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): notes_to_mml + quantization_error"`

---

## Task 14: midi_to_mml.py — convert() + 손실 리포트 + CLI (TDD)

**F1 반영:** `convert`가 MML + 변환 리포트(skipped/unmatched/quant_error/트랙
사용·드롭) 반환. `midi_to_mml`은 호환 위해 mml만. CLI는 MML stdout + 리포트 stderr,
`--report`로 JSON.

**Files:** Modify `scripts/midi_to_mml.py`, Test `tests/test_midi_to_mml.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
from midi_to_mml import convert, midi_to_mml

def test_convert_returns_mml_and_report(tmp_path):
    smf = make_smf(480, [(0,b"\x90\x3C\x40"),(480,b"\x80\x3C\x40")])
    p = tmp_path/"a.mid"; p.write_bytes(smf)
    r = convert(str(p))
    assert r["mml"].startswith("MML@") and r["mml"].endswith(";")
    assert set(r["report"]) >= {"skipped_chunks","unmatched","quant_error",
                                "tracks_used","tracks_dropped"}

def test_convert_caps_and_reports_dropped_tracks(tmp_path):
    body = _vlq(0)+b"\x90\x3C\x40"+_vlq(480)+b"\x80\x3C\x40"+_vlq(0)+b"\xFF\x2F\x00"
    chunk = b"MTrk"+struct.pack(">I",len(body))+body
    smf = b"MThd"+struct.pack(">IHHH",6,1,8,480)+chunk*8
    p = tmp_path/"m.mid"; p.write_bytes(smf)
    r = convert(str(p), max_tracks=6)
    assert r["mml"].count(",") == 5
    assert r["report"]["tracks_used"] == 6
    assert r["report"]["tracks_dropped"] == 2

def test_midi_to_mml_returns_only_mml(tmp_path):
    smf = make_smf(480, [(0,b"\x90\x3C\x40"),(480,b"\x80\x3C\x40")])
    p = tmp_path/"b.mid"; p.write_bytes(smf)
    assert midi_to_mml(str(p)).startswith("MML@")

def test_cli_prints_mml_stdout(tmp_path):
    smf = make_smf(480, [(0,b"\x90\x3C\x40"),(480,b"\x80\x3C\x40")])
    p = tmp_path/"c.mid"; p.write_bytes(smf)
    import subprocess
    out = subprocess.run(["python3","scripts/midi_to_mml.py",str(p)],
        cwd=os.path.join(os.path.dirname(__file__),".."),
        capture_output=True,text=True)
    assert out.returncode == 0 and out.stdout.strip().startswith("MML@")
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현 추가**

```python
def convert(path: str, max_tracks: int = MAX_TRACKS,
            ppq_override: int | None = None) -> dict:
    """SMF → {"mml": "MML@...;", "report": {...}}. 손실 명시."""
    with open(path, "rb") as f:
        data = f.read()
    _, _, ppq = parse_header(data)
    ppq = ppq_override or ppq
    chunks = split_tracks(data)
    tracks_mml: list[str] = []
    agg = {"unmatched_on": 0, "unmatched_off": 0, "skipped_events": 0}
    quant_err = 0
    nonempty = 0
    for chunk in chunks:
        raw, stats = extract_notes(chunk)
        for k in agg:
            agg[k] += stats[k]
        if not raw:
            continue
        nonempty += 1
        if len(tracks_mml) < max_tracks:
            mono = reduce_polyphony(raw)
            tracks_mml.append(notes_to_mml(mono, ppq))
            quant_err += quantization_error(mono, ppq)
    report = {
        "skipped_chunks": len(chunks) - nonempty,
        "unmatched": agg,
        "quant_error": quant_err,
        "tracks_used": len(tracks_mml),
        "tracks_dropped": max(0, nonempty - len(tracks_mml)),
    }
    return {"mml": "MML@" + ",".join(tracks_mml) + ";", "report": report}


def midi_to_mml(path: str, max_tracks: int = MAX_TRACKS,
                ppq_override: int | None = None) -> str:
    return convert(path, max_tracks, ppq_override)["mml"]


def _main(argv: list[str]) -> int:
    import argparse, json, sys
    p = argparse.ArgumentParser(description="MIDI → 마비노기 모바일 MML")
    p.add_argument("midi")
    p.add_argument("--max-tracks", type=int, default=MAX_TRACKS)
    p.add_argument("--ppq", type=int, default=None)
    p.add_argument("--report", action="store_true",
                   help="변환 리포트를 JSON으로 stdout에 추가 출력")
    a = p.parse_args(argv)
    r = convert(a.midi, a.max_tracks, a.ppq)
    print(r["mml"])
    if a.report:
        print(json.dumps(r["report"], ensure_ascii=False))
    else:
        print(f"[report] {r['report']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
```

- [ ] **Step 4: 통과 확인** — `python3 -m pytest tests/ -q` 전체 PASS
- [ ] **Step 5: 커밋** — `git commit -m "feat(mabinogi-mml): convert() + loss report + CLI"`

---

## Task 15: references/mml-syntax.md

**Files:** Create `skills/mabinogi-mml/references/mml-syntax.md`

- [ ] **Step 1: 작성** — 음표 `cdefgab`·임시표 `+`/`-`, 길이·점음표, `l` 기본길이,
`o`/`<`(↑)/`>`(↓) 옥타브(MIDI60=o4 c 매핑 명시), `t` 템포, `v` 볼륨, `r` 쉼표,
`N` 절대음높이(=음표, 길이는 명시 또는 기본 `l` — validator와 일치), 멀티트랙
`MML@t1,...,t6;`(최대 6). 기본값 표(o4/l4/t120/v8). PC 차이 1줄 + 출처(mabicompose.com).
- [ ] **Step 2: 커밋** — `git commit -m "docs(mabinogi-mml): mml-syntax reference"`

---

## Task 16: references/mobile-workflow.md

**Files:** Create `skills/mabinogi-mml/references/mobile-workflow.md`

- [ ] **Step 1: 작성** — 모바일 제약(파트당 1200/2400 불확실성 명시, 6트랙, N명령),
마비꼬 1.5.7+ export(파일>내보내기 → 'N 명령 허용' → ≤6트랙 → 클립보드), MIDI
임포트 L64(6tick) 권장 + **변환 리포트 손실 확인 강조**, 게임 단계(빈 악보 구입→
가방>편집→붙여넣기→미리듣기→곡 제목→곡 만들기), 박자 갭 수정(Shift+Delete),
Verify Error 대응. 출처 링크.
- [ ] **Step 2: 커밋** — `git commit -m "docs(mabinogi-mml): mobile-workflow reference"`

---

## Task 17: SKILL.md

**Files:** Create `skills/mabinogi-mml/SKILL.md`

- [ ] **Step 1: 작성 (frontmatter + ≤150줄)**

frontmatter:
```
---
name: mabinogi-mml
description: 마비노기 모바일 작곡(MML 악보) 보조 — 곡명으로 커뮤니티 MML/MIDI 탐색, MIDI→MML 변환(손실 리포트), 모바일 제약 검증·압축. "마비노기 악보", "MML 만들어", "마비노기 작곡" 요청에 사용.
---
```
본문: 능력경계(채보 ❌/마비꼬·게임 조작 ❌/폴백 근사 ⚠/**변환 손실은 리포트로
표시**), 워크플로우 5단계(탐색→변환→검증→출력), 스크립트 호출
(`python3 scripts/midi_to_mml.py <mid> --report`, `validate_mml.py @f --json [--strict]`),
**리포트 해석 가이드**(skipped/unmatched/quant_error 높으면 마비꼬 수동 후처리 안내),
폴백 작곡 가이드(커뮤니티 1순위, 가사 없음, 개인 인게임용·상업 재배포 아님),
출력 포맷(MML+마비꼬 체크리스트+게임 단계+검증/변환 리포트), references/ 포인터.

- [ ] **Step 2: 줄 수** — `wc -l skills/mabinogi-mml/SKILL.md` ≤150
- [ ] **Step 3: 커밋** — `git commit -m "docs(mabinogi-mml): SKILL.md"`

---

## Task 18: Makefile — _symlink-skills + clean/status (실제 코드, F3)

**F3 반영:** clean/status 실제 make 코드 명시. 비심링크 충돌은 가시적 경고 +
status에 `x` 표시(조용한 성공 금지).

**Files:** Modify `Makefile`

- [ ] **Step 1: 변수 추가 (상단 변수 블록)**

```make
SKILLS_CC := $(HOME)/.claude/skills
SKILLS_CODEX := $(HOME)/.codex/skills
STANDALONE_SKILLS := mabinogi-mml
```

- [ ] **Step 2: install 의존성에 추가**

```make
install: _register-plugins _symlink-rules _symlink-skills ## Install plugins + rules + skills
```

- [ ] **Step 3: _symlink-skills 타깃 추가**

```make
_symlink-skills:
	@echo "=== Symlink standalone skills (CC + Codex) ==="
	@for tgt in "$(SKILLS_CC)" "$(SKILLS_CODEX)"; do \
		mkdir -p "$$tgt"; \
		for s in $(STANDALONE_SKILLS); do \
			dest="$$tgt/$$s"; src="$(REPO_DIR)/skills/$$s"; \
			if [ -L "$$dest" ]; then rm "$$dest"; \
			elif [ -e "$$dest" ]; then echo "  ! CONFLICT $$s in $$tgt (exists, not symlink) — manual fix needed"; continue; \
			fi; \
			ln -s "$$src" "$$dest"; echo "  + $$s -> $$tgt"; \
		done; \
	done
```

- [ ] **Step 4: clean 에 제거 블록 추가 (기존 rules 제거 블록 뒤)**

```make
	@echo "=== Remove standalone skill symlinks ==="
	@for tgt in "$(SKILLS_CC)" "$(SKILLS_CODEX)"; do \
		for s in $(STANDALONE_SKILLS); do \
			dest="$$tgt/$$s"; \
			if [ -L "$$dest" ]; then rm "$$dest"; echo "  - removed $$s ($$tgt)"; fi; \
		done; \
	done
```

- [ ] **Step 5: status 에 확인 블록 추가 (기존 rules 확인 뒤)**

```make
	@echo "=== Standalone skills ==="
	@for tgt in "$(SKILLS_CC)" "$(SKILLS_CODEX)"; do \
		for s in $(STANDALONE_SKILLS); do \
			dest="$$tgt/$$s"; \
			if [ -L "$$dest" ]; then echo "  + $$s ($$tgt)"; \
			elif [ -e "$$dest" ]; then echo "  x $$s ($$tgt) — CONFLICT, not symlink"; \
			else echo "  x $$s ($$tgt) — not installed"; fi; \
		done; \
	done
```

- [ ] **Step 6: 드라이 검증** — Run: `make -n install | grep symlink-skills` 및
`grep -n "_symlink-skills\|STANDALONE_SKILLS" Makefile` → 타깃·변수·install 의존성 존재
- [ ] **Step 7: 커밋** — `git commit -m "build(mabinogi-mml): make symlink skill to CC+Codex (visible conflict)"`

---

## Task 19: CLAUDE.md — 플러그인 모델 폐기 → standalone 크로스 에이전트 (F4: 사용자 명시 지시)

기존 18개 플러그인 스킬 표/분류는 "레거시(grandfather, 물리 유지)"로 보존하되
강제 문구 제거 + 신규 표준 명문화.

**Files:** Modify `CLAUDE.md`

- [ ] **Step 1: 재작성**
- L3/L7/L12: "Claude Code 플러그인 구조로 관리" → "스킬은 standalone 크로스
  에이전트(`skills/`, CC+Codex 심링크). 레거시 플러그인 스킬 4종은 유지" 톤
- `## 스킬 포맷`: `skills/<skill-name>/SKILL.md`(레포 루트) + frontmatter는
  CC·Codex 공통(`name`/`description`). 레거시 `plugins/<plugin>/...`는 "변경 안 함" 1줄
- `## 새 스킬 추가 절차`: 1) `skills/<skill-name>/` 2) SKILL.md(≤150줄) 3) references/
  4) `make install`(양 에이전트 심링크) 5) 커밋. "플러그인 디렉토리에" 문구 삭제
- "마이그레이션 비범위(기존 18개 물리 유지)" 1줄
- [ ] **Step 2: 일관성 + context-rot 확인** — Run:
`grep -n "해당 플러그인 디렉토리에\|plugins/<plugin>/skills" CLAUDE.md` → 강제 문구
없음(레거시 설명 맥락만). CLAUDE.md+rules 합계 토큰 순증 크면 다이어트 1줄 제안.
- [ ] **Step 3: 커밋** — `git commit -m "docs: 플러그인 모델 폐기 → standalone 크로스 에이전트 스킬 표준"`

---

## Task 20: 통합 검증 — 테스트 + make install + 양 에이전트 discovery smoke (F3)

**Files:** (검증 전용)

- [ ] **Step 1: 전체 테스트** — `cd skills/mabinogi-mml && python3 -m pytest tests/ -q` 전체 PASS, 0 fail
- [ ] **Step 2: make install + 심링크 + status**

```bash
make install
ls -l ~/.claude/skills/mabinogi-mml ~/.codex/skills/mabinogi-mml
make status | grep -A6 "Standalone skills"
```
Expected: 두 경로 모두 worktree `skills/mabinogi-mml` 심링크. status `+ mabinogi-mml` ×2.

- [ ] **Step 3: Discovery smoke (양 에이전트)**

```bash
# 심링크 해석 + SKILL.md frontmatter 유효성 (양 에이전트 공통 발견 조건)
for p in ~/.claude/skills/mabinogi-mml ~/.codex/skills/mabinogi-mml; do
  test -f "$p/SKILL.md" && head -4 "$p/SKILL.md" | grep -q "^name: mabinogi-mml" \
    && echo "OK $p" || echo "FAIL $p"
done
```
Expected: 둘 다 `OK`. (CC 자동 발견은 `~/.claude/skills/`의 기존 심링크 스킬이 현
세션 available-skills에 노출되는 것으로 실증됨. Codex 발견은 동일 SKILL.md 포맷·
`~/.codex/skills/` 기존 스킬 선례로 보장 — 사용자가 Codex 세션에서 `/mabinogi-mml`
또는 곡명 요청으로 최종 확인.)

- [ ] **Step 4: 스크립트 e2e 스모크**

```bash
cd skills/mabinogi-mml
python3 scripts/validate_mml.py "MML@cdef,cde;" --json --strict   # ok:false, exit 1
python3 scripts/validate_mml.py "MML@cdef,cde;" --json            # ok:true (디싱크=warning)
```
Expected: strict는 exit 1·`"ok":false`, 비strict는 `"ok":true`·warnings에 디싱크.

- [ ] **Step 5: 커밋** — `git add -A && git commit -m "chore(mabinogi-mml): integration verification" --allow-empty`

---

## Self-Review (v2)

**1. Spec coverage:** 목적/워크플로우(spec §1,6)→T17+스크립트. 검증사실/제약(§2)→
T3·T4(N·디싱크)·T5·T16. 능력경계(§3)→T17(+손실 리포트 명시). 크로스에이전트(§4)→
T1·T18·T20. CLAUDE.md 폐기(§5,F4)→T19. 컴포넌트 경계(§7)→stdlib·no LLM subprocess,
T2~14. 테스트(§8)→각 T TDD + 불변식. 저작권(§9)→T17. 비목표(§11)→헤더 YAGNI. ✓

**2. Adversarial 반영 확인:** F1→T8(fail-closed)·T9(loss stats)·T10(quant err)·
T14(report). F2→T4(N-aware tick·desync warning)·T6(violations/warnings·--strict).
F3→T18(clean/status 실코드·CONFLICT 가시화)·T20(discovery smoke). F4→T19(완전폐기
유지, 사용자 지시). F5→T11·T13(불변식 테스트: 모노포닉·round-trip). ✓

**3. Placeholder scan:** T11·T13의 `NotImplementedError`+`TODO(사용자 기여)`는
learning 의도적 기여점(불변식 테스트가 정합성 가드). 그 외 전 스텝 실제 코드/명령. ✓

**4. Type consistency:** `extract_notes -> (notes,stats)` T9 정의 → T14에서 언팩
일치. `ticks_to_length -> (label,err)` T10 → T13 `[0]` 라벨·`quantization_error`
`[1]` 사용 일치. `convert -> {"mml","report"}` T14 → `midi_to_mml` 래퍼 일치.
`validate -> {ok,tracks,violations,warnings,suggestions}` T6 일관, T4·T5 결과가
warnings로 합류. `track_tick_length` N-aware(T4) ↔ T15 레퍼런스 N 의미 일치 ↔
T13 round-trip 불변식이 동일 함수 사용. 상수 양 스크립트 동일. ✓

갭 없음. 인라인 수정 불필요.
