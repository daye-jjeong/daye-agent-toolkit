# Global Rules Slim Design (v6)

**Date**: 2026-04-09
**Goal**: 글로벌 룰 13개를 압축/통합/흡수하여 system prompt burn 절감
**Priority**: Burn reduction (1순위)
**Compression mode**: Pure compression (header/Why/duplicate 제거. concrete commands, retrieval cue 보존)
**Iteration**: v1 → v2 (Codex review) → v3-v5 (협의) → **v6 (현재)**

## 변경 이력 요약

| 버전 | 핵심 변경 |
|---|---|
| v1 | 모든 룰 in-place 압축 + review 통합 + 일반화 (Moderate) |
| v2 (Codex) | 통합/일반화 모두 거부, pure compression only |
| v3 | review-learning-loop, completion-and-commits를 superpowers에 흡수 |
| v4 (사용자: review 패턴) | review.md 신규 생성 (multipass + learning-loop), completion 흡수 유지 |
| v5 (사용자: 분리 추가) | + pre-work.md, verification.md (completion 흡수 취소) |
| **v6 (사용자: 흡수 vs 합치기 구분)** | learning-loop는 superpowers 흡수 (단일 트리거), pre-work만 합치기, verification 분리 유지 |

## 원칙

| 액션 | 기준 | 이유 |
|---|---|---|
| **흡수 (Absorb)** | 트리거가 단일 컨텍스트 (특히 superpowers 파이프라인) | 트리거-액션 같은 파일 → silent fail 없음 |
| **합치기 (Merge)** | 같은 토픽 + 다중 컨텍스트 룰들. 명시적 trigger 마커로 silent fail 회피 | 토픽 응집 + ad-hoc 컨텍스트 커버 |
| **분리 유지** | 단일 룰 + 합칠 짝 없음, 또는 다중 컨텍스트인데 관련 룰 없음 | 명료성 보존 |
| **압축** | 모든 룰. CC 본체 중복, header 계층, Why 섹션 제거 | 토큰 절감 |

**Compression 보존 원칙** (Codex #4):
- 보존: action item, 실행 가능한 구체 명령(`tsc --noEmit`), 행동 retrieval cue 예시(`workspace 시그니처, CLI cast`)
- 제거: 헤더 계층, 중복 설명, Why 섹션 헤더(인라인 한 줄 유지), CC 본체와 명백히 중복되는 항목

## Scope

**In scope**:
- toolkit `rules/global/`, `rules/correction/`, `rules/tone/` 압축
- `~/.claude/rules/correction-20260404-...` 압축 (standalone, toolkit 외)
- 합치기 1건: `pre-work.md` ← `before-starting` + `checklist-before-impl`
- 흡수 1건: `review-learning-loop` → `superpowers-workflow-gates` step 7 인근
- 리네임 2건: `completion-and-commits` → `verification`, `review-multipass` → `review`

**Out of scope**:
- review-multipass와 review-learning-loop의 하나의 review.md 통합 (Codex #1: 트리거 다름)
- `tsc --noEmit`, `workspace/CLI` 예시의 일반화 (Codex #4: retrieval cue 손실)
- compiled slim layer (future option, Codex #2)
- 룰 카테고리 재정렬, 디렉토리 재구조화
- 새 룰 추가
- toolkit 외 다른 프로젝트 `.claude/rules/`
- CC 본체 / superpowers plugin 수정
- `superpowers-workflow-gates.md`의 추가 압축 (이미 v0에서 5405 → 2032B 처리)
- toolkit 자체 CLAUDE.md (118줄), `~/.claude/CLAUDE.md` 검토

## v6 액션 매트릭스

| # | 룰 | 현재 | v6 액션 | 결과 파일 |
|---|---|---|---|---|
| 1 | `before-starting.md` | 658B | **합치기 → pre-work.md** | (삭제) |
| 2 | `checklist-before-impl.md` (=`correction-20260404-...`) | 427B | **리네임 + 합치기 → pre-work.md** | (삭제) |
| 3 | `pre-work.md` | (신규) | 두 룰 합본 + 명시적 trigger 마커 | **신규 ~700B** |
| 4 | `completion-and-commits.md` | 404B | **리네임 → verification.md** + 압축 | `verification.md` ~330B |
| 5 | `correction-protocol.md` | 1724B | 압축 (Trigger 예시 절반, 절차 detail 트림) | ~1100B |
| 6 | `long-running-backoff.md` | 340B | 약간 압축 | ~250B |
| 7 | `memory-lifecycle.md` | 1077B | 압축 | ~700B |
| 8 | `minimal-scope.md` | 336B | 약간 압축 | ~280B |
| 9 | `review-multipass.md` | 456B | 압축 + 리네임 → `review.md` | `review.md` ~340B |
| 10 | `review-learning-loop.md` | 658B | **흡수 → superpowers step 7** | (삭제) |
| 11 | `session-split.md` | 346B | 약간 압축 | ~280B |
| 12 | `superpowers-workflow-gates.md` | 2032B | learning-loop section 흡수 (~+200B) | ~2230B |
| 13 | `tdd-on-new-functions.md` | 743B | 압축 | ~550B |
| 14 | `tone-kr.md` | 561B | 압축 (예시 절반) | ~430B |

(13번째 룰 `superpowers-workflow-gates`는 v0에서 이미 처리됨. 위는 v6 시점의 추가 변경)

## pre-work.md 초안 (확정)

```markdown
# Pre-Work

코드를 수정하거나 조사 결과를 구현으로 옮길 때 적용.

## Trigger 1: 코드 수정 직전
- 대상 시스템 현재 상태 확인 (설정, 환경변수, 브랜치, 배포 상태)
- 가정 명시 + 실제 값 검증 ("X가 Y일 것이다" → 확인)
- 이미 구현된 것 재발명 금지, 존재 패턴 무시 금지
- 확신 없으면 "이렇게 이해했는데 맞나요?"로 물어라

## Trigger 2: 조사 → 구현 전환 (긴 조사 후)
조사 결과를 구현할 때 기억에 의존하지 마라:
1. 구현 전: 발견사항을 체크리스트 테이블로 정리 + 사용자 확인
2. 구현 중: 체크리스트 referring하며 항목별 반영
3. 구현 후: 체크리스트 vs 산출물 1:1 대조

Why: 컨텍스트 길어지면 누락. 사례: loop-audit 4건 누락
```

(before-starting의 item 1 "관련 파일 먼저 읽어라"는 CC 본체와 중복으로 제거)

## superpowers-workflow-gates learning-loop 흡수 (확정)

step 7의 sub-bullet로 흡수 (trigger와 action 인접):

```markdown
## 파이프라인
...
7. `/simplify` → `pr-review-toolkit:review-pr` 순차 반복 (병렬 금지). 수렴 전 머지 옵션 금지
   - **학습 루프**: 수정 2개+ 발견 시 반복 패턴을 auto memory `patterns.md`에 `- [YYYY-MM-DD] {패턴}: {구현 시 해야 할 것}` 형식으로 기록. 대상: schema enum 추가 → 모든 레이어(workspace 시그니처, CLI cast)에 타입 전파, 헬퍼 추출 → 단위 테스트 함께, 필터/판단 로직 → 3곳+ 사용 시 헬퍼 추출, 기타 2회+ 반복된 리뷰 지적
8. 머지 게이트
...
```

## review.md (리네임 only, 압축)

`review-multipass.md` → `review.md`. 내용 압축:
```markdown
# Code Review

코드 리뷰는 최소 2 pass:
- Pass 1: per-file (logic, omission, style)
- Pass 2: cross-file (참조, 스케줄 시각, flag명, 분산 문서)

single-pass는 cross-file 불일치를 silently ship.
PR 머지엔 사용자 명시 승인 필수.
```

## verification.md (리네임 only, 압축)

`completion-and-commits.md` → `verification.md`. 내용 압축:
```markdown
# Done Verification

"done" 주장 전 필수:
1. 관련 테스트 실행 + 통과
2. `tsc --noEmit` (TypeScript 프로젝트)
3. Cross-file 일관성 (참조, 스케줄, 플래그명, 분산 문서)

검증 없는 완료 주장은 broken tests, type errors, cross-file 불일치를 숨긴다.
```

## 검증 (Codex #3 강화)

작업 후 다음을 모두 통과해야 머지:

### 1. Symlink 정합성
```bash
for f in ~/.claude/rules/*.md; do
  echo "$f → $(readlink -f $f)"
done
```
- 모든 link가 toolkit main을 가리켜야 함 (작업 머지 후)
- pre-work.md, review.md, verification.md symlink 추가됨
- before-starting, checklist-before-impl, review-learning-loop, review-multipass, completion-and-commits 옛 symlink는 삭제됨

```bash
find -L ~/.claude/rules -maxdepth 1 -type l ! -exec test -e {} \; -print
```
- empty (broken symlink 없음)

### 2. **머지 전 측정 금지**
~/.claude/rules/ symlink는 toolkit main을 가리키므로 worktree 변경은 머지 후에만 효과 측정 가능. 머지 전 cache_creation 비교는 무의미.

### 3. Canary transcript regression (3 시나리오)

| 시나리오 | 입력 | 기대 흔적 | 룰 |
|---|---|---|---|
| B | "이 PR review해줘 (의도적 여러 이슈)" | 2 pass + patterns.md 기록 제안 | review.md + superpowers learning section |
| C | (TS 프로젝트) "이 변경 다 됐어?" | 테스트 + `tsc --noEmit` + cross-file 검증 후 done 보고 | verification.md |
| D | 긴 조사 후 "이 시스템 조사하고 수정해줘" | 발견사항 체크리스트 테이블 작성 + 사용자 확인 | pre-work.md (Trigger 2) |

(A "한 군데 review" 시나리오는 인위적이라 제외)

3개 모두 룰 작동 흔적 있어야 함. 누락 시 해당 룰 압축이 과했다는 신호 → revert 후 재압축.

### 4. cache_creation 측정
머지 후 새 세션 첫 turn `cache_creation_input_tokens` 측정. 45,105 → 약 44,500~44,600 떨어졌는지 확인.

### 5. Self-review (보조)
Spec 작성자가 각 압축 파일을 fresh eyes로 한 번 더 읽고 action 보존 확인. **단독 검증으론 불충분** — 위 1~4가 main gate.

## 위험과 완화

| 위험 | 완화 |
|---|---|
| 압축이 과해서 행동 손실 | (1) action item 100% 보존 (2) Canary B/C/D (3) 누락 시 revert |
| 측정 오류 (worktree symlink) | 머지 후에만 측정. 머지 전 측정 명시적 금지 |
| pre-work merge silent fail | 명시적 `## Trigger 1:` `## Trigger 2:` 마커 |
| learning-loop 흡수로 ad-hoc 리뷰 시 학습 단계 누락 | 사용자가 ad-hoc 리뷰 거의 안 함. 손실 무시 |
| toolkit 다른 dirty 파일과 섞임 | worktree 분리 (`fix/global-rules-slim`) |
| Codex가 못 본 함정 | 머지 후 1-2일 모니터링. 이상 시 revert |

## 예상 효과 (v6, 보수적)

| 항목 | 현재 | 후 (보수) | Δ |
|---|---|---|---|
| 룰 파일 | 13 | **11** | −2 (3 삭제 + 1 신규) |
| 총 텍스트 | 9,802B | ~7,200B | −2,600B (−27%) |
| 토큰 추정 | ~2,450 | ~1,800 | **−650** |
| `/memory` listing | 13줄 | 11줄 | −2줄 |
| 첫 turn cache_creation | 45,105 | ~44,455 | −650 |
| baseline 누적 | −23.1% | **−24.2%** | −1.1% |

## v6 vs 다른 버전

| 항목 | v2 (Codex) | v3 | v4 | v5 | **v6** |
|---|---|---|---|---|---|
| review-multipass | 별도 | 별도 | review.md 통합 | review.md 통합 | **별도** (rename only) |
| review-learning-loop | 별도 | superpowers 흡수 | review.md 통합 | review.md 통합 | **superpowers 흡수** |
| completion-and-commits | 별도 | superpowers 흡수 | superpowers 흡수 | verification 분리 | **verification 분리** |
| before-starting + checklist | 별도 | 별도 | 별도 | pre-work 합치기 | **pre-work 합치기** |
| 룰 파일 | 13 | 11 | 12 | 11 | **11** |
| 효과 (토큰) | −550 | −800 | −900 | −1,000 | **−650** |
| 위험 | 낮음 | 낮음 | 중간 (silent fail) | 중간 | **낮음** (구조적 해결) |

## 요약

- v6 = 사용자 원칙 ("흡수 if 단일 컨텍스트, 합치기 if 다중 컨텍스트") 정확 적용
- review-learning-loop만 흡수 (단일 컨텍스트)
- pre-work만 합치기 (multi-context, 같은 토픽)
- review-multipass, verification은 분리 유지 (multi-context, 단일 룰)
- 나머지 8개는 in-place pure compression
- 위험 낮음, 효과 ~−650 토큰
