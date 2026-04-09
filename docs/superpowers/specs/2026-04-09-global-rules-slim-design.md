# Global Rules Slim Design

**Date**: 2026-04-09
**Goal**: 글로벌 룰 13개를 압축/통합하여 system prompt burn 절감
**Priority**: Burn reduction (1순위)
**Compression mode**: Moderate (action 100% 보존, why 핵심만, 예시 1개)

## 배경

CC는 `~/.claude/rules/*.md`를 매 세션 system prompt에 자동 로드. 현재 13개 룰 = 약 9,950 bytes ≈ 2,490 토큰. Anthropic 가이드라인은 CLAUDE.md/룰 합산 < 2,000 토큰 권장. 우리 현재 약간 초과.

이 작업 전 burn 정리 누적: 58,632 → 45,105 (−23.1%). 본 작업으로 추가 −1k 토큰 (~−24.9%) 목표.

## Scope

**In scope**:
- toolkit `rules/global/`, `rules/correction/`, `rules/tone/` 12개 파일 in-place 압축
- `~/.claude/rules/correction-20260404-2100-checklist-before-impl.md` (standalone) 압축
- `review-multipass.md` + `review-learning-loop.md` → `review.md` 통합

**Out of scope**:
- 룰 파일 rename / restructure (B/C 접근 거부)
- 새 룰 추가
- toolkit 외 다른 프로젝트의 `.claude/rules/` 변경
- CC 본체나 superpowers plugin 수정

## 접근 (선택지 A)

각 룰을 자기 자리에서 압축. 카테고리화/리네임 없음. 단일 통합(review)만 실행.

기각된 대안:
- B (compress + restructure): 토큰 효과 없는 cosmetic. minimal-scope 위반
- C (mega-consolidation): discoverability 잃음, 룰 추가 시 어디 넣을지 혼선

## 설계

### 13개 룰 액션 매트릭스

| # | 룰 | 현재 | 액션 | 후 |
|---|---|---|---|---|
| 1 | `before-starting.md` | 658B | 압축 (item 1: CC 본체와 중복 제거) | ~280B |
| 2 | `completion-and-commits.md` | 404B | 압축 + tsc 일반화 | ~280B |
| 3 | `correction-20260404-...checklist-before-impl.md` | 427B | 압축 (사례 detail 트림) | ~220B |
| 4 | `correction-protocol.md` | 1724B | 압축 (verbose 예시 트림) | ~700B |
| 5 | `long-running-backoff.md` | 340B | 약간 압축 | ~220B |
| 6 | `memory-lifecycle.md` | 1077B | 압축 | ~450B |
| 7 | `minimal-scope.md` | 336B | 약간 압축 | ~200B |
| 8 | `review-multipass.md` + `review-learning-loop.md` | 1114B | **MERGE → `review.md`** + 예시 일반화 | ~600B |
| 9 | `session-split.md` | 346B | 약간 압축 | ~220B |
| 10 | `superpowers-workflow-gates.md` | 2032B | (이미 완료, 변경 없음) | 2032B |
| 11 | `tdd-on-new-functions.md` | 743B | 압축 | ~300B |
| 12 | `tone-kr.md` | 561B | 압축 (예시 줄임) | ~290B |

### 보정 사항

- **`completion-and-commits`의 `tsc`**: TS 한정 표현 → "타입 체커 (TS: tsc --noEmit, Python: mypy/pyright, Go: go vet 등)" 일반화
- **`review-learning-loop`의 예시**: dy-minions-squad 색채 ("workspace 시그니처, CLI cast") → universal 표현 ("타입/enum 추가 → 영향 받는 모든 레이어에 전파")

### 통합 결정 기록

| 후보 | 결정 | 이유 |
|---|---|---|
| review-multipass + review-learning-loop | **MERGE** | 같은 카테고리 (review의 how + after). 트리거 컨텍스트 일관성 |
| before-starting + correction-checklist | **별도 유지** | 트리거 시점 다름 (작업 시작 vs 조사→구현 전환) |
| long-running-backoff + session-split | **별도 유지** | 외부 작업 vs 내부 컨텍스트 |
| memory-lifecycle + correction-protocol | **별도 유지** | 메모리 파일 vs 룰 파일 |

### 압축 원칙 (Moderate)

- **유지**: 모든 action item, 핵심 트리거 조건, 단일 why 문장
- **제거**: 중복 설명, 다중 예시, CC 본체와 겹치는 항목, "Why" 섹션 헤더
- **단축**: 헤더 계층 (### → 인라인), 설명 문장 → 명령형, 마크다운 표 → 인라인 리스트

## 예상 효과

| 항목 | 현재 | 후 | Δ |
|---|---|---|---|
| 룰 개수 | 13 | 12 | −1 |
| 총 텍스트 | 9,950B | ~5,762B | −4,188B (−42%) |
| 토큰 추정 | ~2,490 | ~1,440 | −1,050 (−42%) |
| `/memory` listing | 13줄 | 12줄 | −1줄 |
| 첫 turn cache_creation | 45,105 | ~44,055 | −1,050 |
| baseline 대비 누적 | −23.1% | **−24.9%** | — |

## 위험과 완화

| 위험 | 완화 |
|---|---|
| 압축이 과도해서 룰 의미 잃음 | Moderate 압축 — action 100% 보존. self-review에서 검증 |
| 통합된 review.md가 두 원본만큼 명확하지 않음 | 두 섹션 명시적 분리 (`## Multipass`, `## Learning Loop`) |
| toolkit symlink 갱신 누락 | review 통합 시 한 번에 처리 (delete 2 + add 1) |
| Stale `~/.claude/rules/` 참조 | 작업 후 `ls -la ~/.claude/rules/` + broken symlink 검증 |
| toolkit 다른 dirty 파일과 섞임 | worktree 분리 (`fix/global-rules-slim`) |

## 검증

작업 후:
1. `~/.claude/rules/` ls = **12개 entries** (현재 13 → review-multipass + review-learning-loop 두 symlink 삭제 + review.md symlink 1개 추가 = −1)
2. broken symlink 없음 (`find -L ~/.claude/rules -maxdepth 1 -type l ! -exec test -e {} \; -print`)
3. 새 세션 측정: cache_creation ~44,055 도달 확인
4. 룰 작동 회귀 테스트: 다음 작업 시 워크플로우 정상 적용되는지 (eyeball)

## Out of scope (별건)

- 글로벌 룰 카테고리화/rename (B 접근)
- mega-consolidation (C 접근)
- toolkit 자체 CLAUDE.md (118줄) 슬림화
- `~/.claude/CLAUDE.md` 검토 (현재 없음)
- compact-state.json stale (24h+) 자동 cleanup
- 다른 프로젝트 `.claude/rules/` 정리
