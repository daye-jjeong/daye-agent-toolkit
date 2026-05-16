# mabinogi-mml — 마비노기 모바일 MML 작곡 보조 스킬 (설계)

**Date:** 2026-05-16
**Status:** Design approved (브레인스토밍 완료, 사용자 승인 "이대로 진행")
**Branch:** `feat/mabinogi-mml`

## 1. 목적

사용자가 곡명을 말하면 → 마비노기 모바일에 붙여넣을 수 있는 MML 악보를 만들어준다.
오디오 자동 채보는 불가능하므로, **기존 커뮤니티 소스 탐색 → 변환 → 모바일 제약 검증**을
자동화하는 것이 핵심 가치다. (사람이 마비꼬에서 손으로 하는 후처리를 텍스트 처리로 대체.)

## 2. 검증된 사실 (마비노기 모바일)

| 항목 | 내용 | 출처 |
|---|---|---|
| 기반 | MML(Mabinogi Music Language). 단 PC와 악보 구조·연주가 **완전히 다름** — PC 악보 그대로 못 씀 | mabicompose.com |
| 트랙/화음 | 최대 **6트랙(6화음)** | mabicompose.com/lecture02 |
| 글자수 | 파트당 제한 — 소스마다 **1200 / 2400** 상이 (게임 업데이트로 변동 추정) | inven, mabicompose |
| 명령 | `N` 명령어 사용 가능 (글자수 절약). 마비꼬 export 시 "N 명령 허용" 체크 | mabicompose/clipboard |
| 함정 | MIDI 자동 변환은 파트 섞임·박자 갭·글자수 초과 발생 → 후처리 필수. 모바일은 박자 갭에 PC보다 민감 | mabicompose/midi_1, mobile_bug_fix |
| 권장 | MIDI 임포트 시 `L64 (6tick)` 정렬로 오류 확률 감소 | mabicompose/midi_1 |

미해결 1건: 파트당 글자수(1200 vs 2400)는 상수로 분리하고 기본값 + 불확실성 주석.
사용자가 게임에서 실측 확인 후 조정. (스킬이 추정값을 단정하지 않음.)

## 3. 능력 경계 (SKILL.md에 명시)

- ❌ 오디오(유튜브 등) 듣고 채보 — Claude는 오디오 분석 능력 없음
- ❌ 마비꼬(데스크톱 Java 앱)/게임 직접 조작 — 사용자가 수행
- ✅ MIDI(SMF) 파일 파싱 → MML 변환 (Python stdlib)
- ✅ MML 모바일 제약 검증·압축 제안
- ✅ MML/MIDI 소스 웹검색 보조 + 마비꼬/게임 워크플로우 가이드
- ⚠️ 소스가 전무할 때 Claude 직접 작성은 **근사치** (멜로디 위주, 정확도 한계 명시)

## 4. 아키텍처: 플러그인 비소속 크로스 에이전트 스킬

기존 4개 CC 플러그인 어디에도 안 맞는 새 도메인이며, **Codex에서도 사용 필요**.
CC와 Codex는 스킬 포맷이 동일(`SKILL.md` + `name`/`description` frontmatter)하고
각자 사용자 레벨 스킬 디렉토리를 가짐(`~/.claude/skills/`, `~/.codex/skills/`).
→ 플러그인 없이 단일 소스를 양쪽에 심링크하면 두 에이전트 모두 네이티브 발견.

### 디렉토리 (단일 소스, 레포 루트 `skills/`)

```
skills/mabinogi-mml/
  SKILL.md                — name/description frontmatter, 워크플로우, 능력경계 (≤150줄)
  VERSION                 — 0.1.0
  CHANGELOG.md
  references/
    mml-syntax.md         — 마비노기 모바일 MML 문법 (음표/옥타브/길이/템포/볼륨/N명령/3+트랙)
    mobile-workflow.md    — 모바일 제약 + 마비꼬 export 설정 + 게임 내 단계
  scripts/
    midi_to_mml.py        — MIDI(SMF) 파싱 → 트랙→파트 매핑 → MML (stdlib only)
    validate_mml.py       — 모바일 제약 검증 + 압축 제안 리포트
  tests/
    test_midi_to_mml.py
    test_validate_mml.py
    fixtures/             — 최소 SMF 바이트 픽스처
```

### 설치 (`make install` 확장)

기존 `_symlink-rules` 루프와 동일 패턴으로 `_symlink-skills` 추가:

- `skills/mabinogi-mml/` → `~/.claude/skills/mabinogi-mml` (CC 네이티브)
- `skills/mabinogi-mml/` → `~/.codex/skills/mabinogi-mml` (Codex 네이티브)

`clean`/`status`에도 대칭 추가. `marketplace.json`·`plugin.json` **무수정**.
기존 심링크/실파일 충돌 시 rules 루프와 동일하게 SKIP 처리.

## 5. CLAUDE.md 규칙 변경 (플러그인 모델 폐기)

사용자 결정: 플러그인 강제 규칙 **완전 삭제**.

**범위 (minimal-scope 적용):**
- 프로젝트 `CLAUDE.md`에서 플러그인 모델 문서/강제를 제거하고 standalone 크로스
  에이전트 스킬 구조를 표준으로 재작성 (L3, 7, 12, 82–87, 98–101 등).
- 기존 18개 플러그인 스킬은 **물리적으로 건드리지 않음** — `plugins/`·`marketplace.json`
  유지, CC에서 계속 동작. 이들을 standalone으로 옮기는 마이그레이션은 **이번 범위 밖**
  (원하면 별도 작업으로 요청). `mabinogi-mml`이 첫 standalone 크로스 에이전트 스킬.

## 6. 워크플로우 (스킬 실행 시)

1. **곡명 입력** (예: "세븐틴 손오공")
2. **소스 탐색** (Claude, WebSearch):
   ① 마비노기 모바일 호환 MML 검색 → ② PC MML 검색(모바일 변환 안내)
   → ③ MIDI 검색(musescore/midi 사이트). 사용자가 파일 확보·제공.
3. **변환:**
   - MIDI 확보 → `midi_to_mml.py` (L64/6tick 양자화, 트랙→파트 매핑, N명령 옵션)
   - 소스 전무 → Claude 직접 작성 (폴백, 근사·멜로디 위주, 한계 명시)
4. **검증·수정** `validate_mml.py`: 파트당 글자수 / 최대 6트랙·6화음 / N명령 /
   템포 명령 위치 / 박자 갭 → 초과 시 압축 제안(옥타브·길이 디폴트 최적화, 트랙 정리).
5. **출력:** 붙여넣기용 `MML@t1,t2,...;` + 마비꼬 export 설정 체크리스트 +
   게임 내 단계 + 검증 리포트.

## 7. 컴포넌트 경계

- **`midi_to_mml.py`** — 입력: SMF 파일 경로(+옵션: 정렬 tick, N명령 on/off, 최대 트랙).
  출력: 파트별 MML 문자열 리스트. 의존: stdlib(`struct`)만. 게임/네트워크 무관, 순수 변환.
- **`validate_mml.py`** — 입력: MML 문자열(+제약 상수). 출력: 위반 리포트 +
  압축 제안. 의존: stdlib만. 순수 함수, 게임 호출 없음.
- **`SKILL.md`** — LLM이 읽는 프레임워크(소스 탐색 전략, 폴백 작곡 가이드, 출력 포맷,
  능력경계). 스크립트를 도구로 호출. LLM subprocess 호출 없음(레포 규칙 준수).
- **references/** — 정적 지식. SKILL.md에서 포인터로 참조.

## 8. 테스트 전략 (TDD)

새 함수는 RED→GREEN→REFACTOR.

- `test_midi_to_mml.py`: 최소 SMF 바이트 픽스처 → 음표/옥타브/길이 매핑, 트랙→파트
  분리, tick 양자화, N명령 토글, 트랙 수 초과 처리.
- `test_validate_mml.py`: 글자수 초과, 7트랙(초과), 잘못된 템포 위치, 박자 갭 검출,
  정상 케이스 통과, 압축 제안 정확성.

## 9. 저작권/스코프 노트

스킬은 **커뮤니티 공유 MML/MIDI를 항상 1순위**로 탐색한다(정확도·합법성 양면 유리).
직접 작성 폴백은 개인 인게임 플레이용 근사 멜로디이며 가사를 포함하지 않는다
(MML은 멜로디·음표만 표현). 상업적 재배포 용도가 아님을 SKILL.md에 명시.

## 10. 규모/리뷰 게이트

파일 8+개(SKILL/2 ref/2 script/2 test/fixtures/VERSION/CHANGELOG) + Makefile +
CLAUDE.md 수정 → L 사이즈. plan 단계에서 `/codex:adversarial-review` + `dev-tools:codex-cli`
프롬프트로 설계 검증. 구현 후 `/simplify` → `pr-review-toolkit:review-pr` 수렴.

## 11. 비목표 (YAGNI)

- 오디오/유튜브 자동 채보 — 불가, 시도 안 함
- 마비꼬/게임 자동 조작 — 범위 밖
- 기존 18개 플러그인 스킬 마이그레이션 — 별도 작업
- PC 마비노기 전용 기능 — 모바일에 집중
- MML→MIDI 역변환, 악보 이미지 OCR — 현 범위 밖
