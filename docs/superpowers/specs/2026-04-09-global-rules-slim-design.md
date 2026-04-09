# Global Rules Slim Design (v2, post-Codex review)

**Date**: 2026-04-09
**Goal**: 글로벌 룰 13개를 압축하여 system prompt burn 절감
**Priority**: Burn reduction (1순위)
**Compression mode**: **Pure compression only** — redundancy/headers/duplicate why 제거. 행동 유도 디테일(concrete commands, retrieval cue 예시)은 보존
**Codex review**: `tmp/codex-rules-slim-review.md` 5건 모두 반영

## 배경

CC는 `~/.claude/rules/*.md`를 매 세션 system prompt에 자동 로드. 현재 13개 룰 = 약 9,950 bytes ≈ 2,490 토큰. Anthropic 가이드라인은 CLAUDE.md/룰 합산 < 2,000 토큰 권장. 살짝 초과.

이 작업 전 burn 정리 누적: 58,632 → 45,105 (−23.1%). 본 작업은 보수적으로 추가 −500~−700 토큰 목표.

## Scope

**In scope**:
- toolkit `rules/global/`, `rules/correction/`, `rules/tone/` 12개 파일 in-place 압축 (헤더/중복/Why 섹션 제거만)
- `~/.claude/rules/correction-20260404-2100-checklist-before-impl.md` (standalone) 압축

**Out of scope** (Codex #2, #5):
- **룰 통합/머지** (review.md 통합 포함). 모든 룰 별도 유지
- **구체 → 일반화 변환** (`tsc --noEmit`, `workspace/CLI` 예시 등). 모두 그대로 유지
- 룰 파일 rename / restructure
- 새 룰 추가
- toolkit 외 다른 프로젝트의 `.claude/rules/`
- CC 본체나 superpowers plugin 수정
- `superpowers-workflow-gates.md` (이미 처리됨)

**Future options** (별건):
- **Compiled slim layer**: source verbose 유지 + install 단계에서 runtime artifact 생성. burn 문제는 전달 계층 문제이므로 SoT 직접 변형 대신 layer 분리가 더 깨끗 (Codex #2)
- 1차 압축 후에도 burn 목표 미달 시 재검토

## 접근 (Pure compression)

**압축 원칙**:
- 제거 가능: 헤더 계층 (`### Subheader` → 인라인), 중복 설명, `## Why` 섹션 헤더(문장은 1줄 인라인 유지), CC 본체와 명백히 중복되는 항목
- **보존**: 모든 action item, 실행 가능한 구체 명령(`tsc --noEmit` 등), 행동 retrieval cue 예시(`workspace 시그니처, CLI cast` 등), 단일 why 문장, 핵심 트리거 조건

**이유** (Codex #4): 룰은 API 문서가 아니라 행동 유도 장치. 구체 명령은 실행 cue, 구체 예시는 retrieval cue. 일반화하면 해석을 요구하게 되어 행동성 손실.

## 13개 룰 액션 매트릭스 (v2)

| # | 룰 | 현재 | 액션 | 후 (보수) |
|---|---|---|---|---|
| 1 | `before-starting.md` | 658B | 압축: header `## 확인 항목` 제거, 마지막 문장 보존, item 1 유지 | ~480B |
| 2 | `completion-and-commits.md` | 404B | 압축: header 정리, Why 인라인. **`tsc --noEmit` 그대로** | ~330B |
| 3 | `correction-20260404-...checklist-before-impl.md` | 427B | 압축: 사례 ("loop-audit") 한 줄로 | ~310B |
| 4 | `correction-protocol.md` | 1724B | 압축: Trigger 예시 절반, 저장 절차 detail 트림. 핵심 6단계 보존 | ~1100B |
| 5 | `long-running-backoff.md` | 340B | 약간 압축: 한 줄로 | ~250B |
| 6 | `memory-lifecycle.md` | 1077B | 압축: header 정리, 예외 섹션 인라인 | ~700B |
| 7 | `minimal-scope.md` | 336B | 약간 압축 | ~280B |
| 8 | `review-multipass.md` | 456B | 압축: Why 인라인. **별도 유지** (Codex #1) | ~340B |
| 9 | `review-learning-loop.md` | 658B | 압축: Why 인라인. **`workspace 시그니처/CLI cast` 예시 보존** | ~520B |
| 10 | `session-split.md` | 346B | 약간 압축 | ~280B |
| 11 | `superpowers-workflow-gates.md` | 2032B | (이미 처리됨, 변경 없음) | 2032B |
| 12 | `tdd-on-new-functions.md` | 743B | 압축: header 인라인, Exempt 단축 | ~550B |
| 13 | `tone-kr.md` | 561B | 압축: 예시 절반 | ~430B |

**합계**: 9,802B → 약 7,602B = **−2,200B (−22%)** ≈ **−550 토큰**

(v1 ~1,050 토큰 대비 절반. 보수적이지만 안전)

## 통합/일반화 결정 (모두 거부)

| 후보 | v1 결정 | v2 결정 | 이유 |
|---|---|---|---|
| review-multipass + review-learning-loop → review.md | MERGE | **거부** | Codex #1: 트리거 다름 (리뷰 중 vs 리뷰 후 2+ findings). silent fail 위험 |
| `tsc --noEmit` → "타입 체커 (TS/Python/Go)" | 일반화 | **거부, 그대로** | Codex #4: 실행 명령 → 해석 요구로 손실 |
| `workspace 시그니처/CLI cast` 예시 → 일반화 | 일반화 | **거부, 그대로** | Codex #4: retrieval cue. 구체 사례가 사고 패턴 trigger |
| before-starting + correction-checklist | 별도 | **별도** | 트리거 시점 다름 |
| long-running-backoff + session-split | 별도 | **별도** | 외부 작업 vs 내부 컨텍스트 |
| memory-lifecycle + correction-protocol | 별도 | **별도** | 메모리 파일 vs 룰 파일 |

## 검증 (강화, Codex #3)

작업 후 다음을 모두 통과해야 머지:

### 1. Symlink target 검증
```bash
for f in ~/.claude/rules/*.md; do
  echo "$f → $(readlink -f $f)"
done | grep -v "/daye-agent-toolkit/" || echo OK
```
→ 모든 symlink가 toolkit main 트리(머지 후) 가리키는지. **머지 전 측정은 무의미** — symlink는 main을 가리키므로 worktree 변경이 반영 안 됨. 머지 후에만 측정.

### 2. Broken symlink 없음
```bash
find -L ~/.claude/rules -maxdepth 1 -type l ! -exec test -e {} \; -print
```
→ empty output

### 3. Canary transcript regression (4개 시나리오)
머지 후 새 세션에서 다음 4개 케이스 각각 1턴 실행, 응답에 룰 작동 흔적이 있는지 확인:

| 시나리오 | 입력 | 기대 행동 | 룰 |
|---|---|---|---|
| A. 리뷰 1 finding | "이 코드 한 군데 review해줘" | 2 pass 수행 (per-file + cross-file) | review-multipass |
| B. 리뷰 2+ findings | "이 PR review해줘 (의도적으로 여러 이슈 있음)" | 2 pass + 패턴을 patterns.md에 기록 제안 | review-learning-loop |
| C. TS 프로젝트 done 주장 | "이 변경 다 됐어, 끝났지?" | 테스트 + `tsc --noEmit` 실행 후에만 확정 | completion-and-commits |
| D. 조사 → 구현 전환 | "이 시스템 조사하고 수정해줘" (긴 조사 후) | 발견사항을 체크리스트 테이블로 정리 + 사용자 확인 | correction-20260404 |

→ 4개 모두 룰 작동 흔적 있어야 함. 누락 시 해당 룰 압축이 과했다는 신호 → revert 후 재압축.

### 4. cache_creation 측정
머지 후 새 세션 첫 turn `cache_creation_input_tokens`이 45,105 → 약 44,500~44,600 떨어졌는지 확인. ~−500 토큰.

### 5. self-review (보조)
spec 작성자가 각 압축 파일을 fresh eyes로 한 번 더 읽고 action 보존 확인. **단독 검증으론 불충분** — 위 1~4가 main gate.

## 위험과 완화 (v2)

| 위험 | 완화 |
|---|---|
| 압축이 과해서 행동 손실 | (1) action item 100% 보존 원칙 (2) Canary regression A-D (3) 누락 시 revert |
| 측정 오류 (worktree symlink) | 머지 후에만 측정. 머지 전 측정 명시적으로 금지 |
| toolkit 다른 dirty 파일과 섞임 | worktree 분리 (`fix/global-rules-slim`) — 이미 만들어짐 |
| Codex가 못 본 함정 | 압축본 적용 후 실제 사용 1-2일 모니터링. 이상 징후 시 revert |

## 예상 효과 (v2, 보수적)

| 항목 | 현재 | 후 (보수) | Δ |
|---|---|---|---|
| 룰 개수 | 13 | 13 (변경 없음) | 0 |
| 총 텍스트 | 9,802B | ~7,602B | −2,200B (−22%) |
| 토큰 추정 | ~2,450 | ~1,900 | −550 (−22%) |
| `/memory` listing | 13줄 | 13줄 | 0 |
| 첫 turn cache_creation | 45,105 | ~44,555 | −550 |
| baseline 누적 | −23.1% | **−24.0%** | −0.9% |

## v1 대비 변경 요약

| 항목 | v1 | v2 |
|---|---|---|
| 통합 | review merge 1건 | 0건 |
| 일반화 | tsc, 예시 일반화 | 0건 |
| 압축 강도 | Moderate (~−42%) | Pure (~−22%) |
| 검증 | eyeball + cache_creation | symlink target + canary 4 케이스 + cache_creation |
| 예상 효과 | −1,050 토큰 | −550 토큰 |
| 위험 | 중간 | 낮음 |

## Codex 5건 반영 매트릭스

| # | Codex 지적 | v2 반영 |
|---|---|---|
| 1 | review.md 통합이 트리거 다른 두 룰 뭉갬 | review merge 취소, 별도 유지 |
| 2 | Compiled slim layer가 진짜 해법 | Out of scope에 future option으로 명시 |
| 3 | 검증 너무 약함, symlink target 미검증 | 검증 섹션 5단계로 강화. canary 4 케이스 추가. 머지 전 측정 금지 명시 |
| 4 | 구체 → 일반화 = retrieval cue 손실 | tsc/workspace 예시 그대로 유지. "구체 보존" 압축 원칙으로 |
| 5 | minimal-scope 위반, 작은 룰에 의미 리스크 | pure compression only로 축소 |
