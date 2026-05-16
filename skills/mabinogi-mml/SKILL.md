---
name: mabinogi-mml
description: 마비노기 모바일 작곡(MML 악보) 보조 — 곡명으로 커뮤니티 MML/MIDI 탐색, MIDI→MML 변환(손실 리포트), 모바일 제약 검증·압축. "마비노기 악보", "MML 만들어", "마비노기 작곡", "마비노기 모바일 작곡" 요청에 사용.
---

## 능력 경계

| 기능 | 상태 |
|------|------|
| 오디오(유튜브) 채보 | ❌ 불가 |
| 마비꼬·게임 직접 조작 | ❌ 불가 |
| 커뮤니티 MML/MIDI 탐색 | ✅ WebSearch 활용 |
| MIDI → MML 변환 | ✅ (손실 리포트 포함) |
| MML 검증 · 압축 | ✅ |
| 폴백 직접 작곡 | ⚠ 근사 멜로디(가사 없음) |

변환 손실은 리포트로 표시하며 숨기지 않는다.

---

## 워크플로우 5단계

**① 곡명 입력** — 사용자에게 곡명(아티스트 포함) 확인.

**② 소스 탐색** (WebSearch, 우선순위 순)
1. 마비노기 모바일 호환 MML (커뮤니티 공유)
2. PC MML — 발견 시 모바일 변환 불가 안내 후 MIDI로 우회 유도
3. MIDI 파일 (MuseScore, Khinsider, freemidi 등)

**③ 변환**
- MIDI 확보 시: `python3 scripts/midi_to_mml.py <파일.mid> --report`
- 소스 전무 시: Claude 직접 작성 (폴백, 근사·멜로디만, 가사 없음)

**④ 검증**
```
python3 scripts/validate_mml.py "@파일" --json [--strict]
```

**⑤ 출력**
- 붙여넣기용 `MML@...;` 블록
- 마비꼬 export 체크리스트 (N명령 허용, 6트랙 이내, 클립보드 출력)
- 게임 단계 안내 (빈 악보 구입 → 가방>편집 → 붙여넣기 → 미리듣기 → 곡 만들기)
- 검증/변환 리포트

---

## 리포트 해석

### 변환 리포트 (midi_to_mml.py --report)

| 항목 | 값이 크면 |
|------|----------|
| `skipped_chunks` | 음표 없는 청크 건너뜀 — 마비꼬 수동 확인 |
| `unmatched` | 음표 매핑 실패 — 옥타브 범위 초과 가능성 |
| `quant_error` | 양자화 오차 합계(tick) 큼 — L64 정렬 후 재변환 권장 |
| `notes_dropped_polyphony` | 화음 제거 — 중요 선율 손실 여부 확인 |
| `tracks_dropped` | 6트랙 초과로 잘림 — --max-tracks로 조정 |

### 검증 리포트 (validate_mml.py)

| 종류 | 항목 | 처리 |
|------|------|------|
| violations (hard) | 글자수 초과, 트랙 수 초과 | 반드시 수정 |
| warnings (soft) | 트랙 길이 디싱크, 템포 위치 | `--strict` 시 `ok=false`·exit 1 (단, `violations` 배열에는 추가되지 않고 `warnings`에 유지) |

---

## 폴백 직접 작곡 가이드

커뮤니티 공유 소스를 **항상 1순위**로 탐색한다. 정확도·합법성 면에서 우선한다.

소스를 끝내 찾지 못한 경우에만 Claude가 직접 작성:
- **개인 인게임 플레이 전용 근사 멜로디**
- MML은 멜로디·음표만 — **가사 포함 불가**
- 상업적 재배포 용도 아님

---

## 스크립트 레퍼런스

**`scripts/midi_to_mml.py`** — SMF → MML 변환. 손상/비표준 입력은 조용히 통과시키지 않고 ValueError 또는 리포트로 노출(fail-closed).

| 옵션 | 설명 |
|------|------|
| `--report` | 변환 손실 리포트 출력 |
| `--max-tracks N` | 출력 트랙 수 상한 (기본 6) |
| `--ppq N` | MIDI PPQ 오버라이드 |

**`scripts/validate_mml.py`** — MML 제약 검증.

| 옵션 | 설명 |
|------|------|
| `--json` | JSON 형식 출력 |
| `--strict` | 소프트 경고를 위반으로 승격 |
| `--max-chars N` | 파트당 글자수 상한 (기본 1200) |
| `--max-tracks N` | 트랙 수 상한 (기본 6) |
| `--ppq N` | tick 계산용 PPQ |

---

## References

- [`references/mml-syntax.md`](references/mml-syntax.md) — MML 문법 전체 레퍼런스
- [`references/mobile-workflow.md`](references/mobile-workflow.md) — 모바일 제약 + 마비꼬 + 게임 단계
