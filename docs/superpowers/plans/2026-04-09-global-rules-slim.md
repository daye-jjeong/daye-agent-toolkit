# Global Rules Slim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 글로벌 룰 13개를 pure compression + 1 merge + 1 absorb로 정리하여 system prompt burn 절감

**Architecture:** toolkit `rules/global/` 파일 직접 편집. pre-work.md 신규 생성, review-learning-loop을 superpowers에 흡수, completion-and-commits/review-multipass를 rename+compress. 나머지 7개 in-place compress. 후속으로 `~/.claude/rules/` symlink 갱신.

**Tech Stack:** Markdown, bash (symlink)

**Spec:** `docs/superpowers/specs/2026-04-09-global-rules-slim-design.md`

---

### Task 1: Create pre-work.md + delete before-starting.md

**Files:**
- Create: `rules/global/pre-work.md`
- Delete: `rules/global/before-starting.md`

- [ ] **Step 1: Create pre-work.md**

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

- [ ] **Step 2: Delete before-starting.md**

```bash
rm rules/global/before-starting.md
```

- [ ] **Step 3: Verify**

```bash
test -f rules/global/pre-work.md && ! test -f rules/global/before-starting.md && echo OK
```

### Task 2: Absorb review-learning-loop into superpowers-workflow-gates

**Files:**
- Modify: `rules/global/superpowers-workflow-gates.md` (step 7 sub-bullet 추가)
- Delete: `rules/global/review-learning-loop.md`

- [ ] **Step 1: Add learning-loop sub-bullet to step 7**

`rules/global/superpowers-workflow-gates.md`의 step 7 라인을:

```
7. `/simplify` → `pr-review-toolkit:review-pr` 순차 반복 (병렬 금지). 수렴 전 머지 옵션 금지
```

다음으로 교체:

```
7. `/simplify` → `pr-review-toolkit:review-pr` 순차 반복 (병렬 금지). 수렴 전 머지 옵션 금지
   - **학습 루프**: 수정 2개+ 발견 시 반복 패턴을 auto memory `patterns.md`에 `- [YYYY-MM-DD] {패턴}: {구현 시 해야 할 것}` 형식으로 기록. 대상: schema enum 추가 → 모든 레이어(workspace 시그니처, CLI cast)에 타입 전파, 헬퍼 추출 → 단위 테스트 함께, 필터/판단 로직 → 3곳+ 사용 시 헬퍼 추출, 기타 2회+ 반복된 리뷰 지적
```

- [ ] **Step 2: Delete review-learning-loop.md**

```bash
rm rules/global/review-learning-loop.md
```

- [ ] **Step 3: Verify**

```bash
grep "학습 루프" rules/global/superpowers-workflow-gates.md && ! test -f rules/global/review-learning-loop.md && echo OK
```

### Task 3: Rename + compress completion-and-commits, review-multipass

**Files:**
- Create: `rules/global/verification.md` (from completion-and-commits.md)
- Create: `rules/global/review.md` (from review-multipass.md)
- Delete: `rules/global/completion-and-commits.md`
- Delete: `rules/global/review-multipass.md`

- [ ] **Step 1: Create verification.md**

```markdown
# Done Verification

"done" 주장 전 필수:
1. 관련 테스트 실행 + 통과
2. `tsc --noEmit` (TypeScript 프로젝트)
3. Cross-file 일관성 (참조, 스케줄, 플래그명, 분산 문서)

검증 없는 완료 주장은 broken tests, type errors, cross-file 불일치를 숨긴다.
```

- [ ] **Step 2: Create review.md**

```markdown
# Code Review

코드 리뷰는 최소 2 pass:
- Pass 1: per-file (logic, omission, style)
- Pass 2: cross-file (참조, 스케줄 시각, flag명, 분산 문서)

single-pass는 cross-file 불일치를 silently ship.
PR 머지엔 사용자 명시 승인 필수.
```

- [ ] **Step 3: Delete originals**

```bash
rm rules/global/completion-and-commits.md rules/global/review-multipass.md
```

- [ ] **Step 4: Verify**

```bash
test -f rules/global/verification.md && test -f rules/global/review.md && \
! test -f rules/global/completion-and-commits.md && ! test -f rules/global/review-multipass.md && echo OK
```

### Task 4: Compress remaining 7 rule files

**Files:**
- Modify: `rules/global/minimal-scope.md`
- Modify: `rules/global/long-running-backoff.md`
- Modify: `rules/global/session-split.md`
- Modify: `rules/global/memory-lifecycle.md`
- Modify: `rules/global/tdd-on-new-functions.md`
- Modify: `rules/global/tone-kr.md` (rules/tone/ 위치)
- Modify: `rules/correction/correction-protocol.md`

각 파일에 대해: header 계층 축소, Why 섹션 인라인, CC 본체 중복 제거. 구체 명령/예시 보존.

- [ ] **Step 1: Compress minimal-scope.md**

```markdown
# 범위 최소주의

요청 범위만 변경. 추가 개선/리팩토링은 묻고 나서.
문서는 소유 파일에만. 분산 금지.
"이것도 할까요?" 제안 한 번만.
의심되면 덜 하라 — 더 필요하면 사용자가 요청.
```

- [ ] **Step 2: Compress long-running-backoff.md**

```markdown
# 장시간 작업 대기

CI/CD, Docker, 배포 대기 시:
- `gh run watch` 등 연속 출력 대신 지수 백오프 (1m→2m→4m→8m max)
- 확인은 한 줄 (`gh run view <id> | grep <job>`)
- 토큰 낭비 최소화
```

- [ ] **Step 3: Compress session-split.md**

```markdown
# 세션 분할

태스크 수만으로 분할 제안 금지. 1M 컨텍스트에서 10개+ 처리 가능.
실제 컨텍스트 사용량 높을 때만 제안.
70%+ 사용 시 진행 상태를 plan 파일에 기록.
```

- [ ] **Step 4: Compress memory-lifecycle.md**

```markdown
# Memory Lifecycle

## project 메모리 금지
`type: project` 생성 금지. 프로젝트 상태는 코드/커밋/docs/에 남긴다.
허용 타입: `feedback`, `user`, `reference`만.

## project 메모리 정리
기존 project 메모리는 작업 완료 시 삭제 (master 머지 + 후속 없음).
삭제: 파일 + MEMORY.md 인덱스.

Why: project 메모리 누적 → 시스템 프롬프트 비대.

예외: 후속 작업 명시된 건 유지. feedback/user/reference는 대상 아님.
```

- [ ] **Step 5: Compress tdd-on-new-functions.md**

```markdown
# TDD on New Functions

새 함수는 테스트 먼저: RED → GREEN → REFACTOR.

Scope: 새 exported 함수, 새 분기/동작, 리팩토링 추출 함수.
Exempt: 단순 re-export/타입/상수, 기존 테스트가 커버, S 사이즈 trivial 1줄 함수.
```

- [ ] **Step 6: Compress tone-kr.md** (at `rules/tone/tone-kr.md`)

```markdown
# 한국어 톤

## 하지 마라
- 과장 아첨 ("좋은 질문!", "핵심을 찌르셨네요")
- 마무리 상투어 ("도움이 되셨길", "더 궁금하시면")
- 번역체 ("~를 탐색", "심층적으로", "풀어서 설명")
- 후속 제안 남발 ("원하시면 ~해드릴까요?")
- 불필요한 이모지

## 해라
- 본론부터, 짧고 직접적, 자연스러운 종결
```

- [ ] **Step 7: Compress correction-protocol.md** (at `rules/correction/correction-protocol.md`)

```markdown
# Correction Protocol

사용자가 행동을 교정하면 즉시 적용 + 저장.

## Trigger
명시적("always X", "never Y"), 반복(2회+), 방향 전환("이건 아니야"), 선호("이게 더 낫다"), 좌절("왜 또 이래").

## 저장
1. 즉시 행동 변경
2. `.claude/rules/correction-{YYYYMMDD}-{HHmm}-{slug}.md` — `{rule}. Why: {reason}`. 1건/파일. 중복 확인
3. Auto memory `corrections/{topic}.md`: `- [YYYY-MM-DD] {before} -> {after} (reason)`
4. Auto memory log `corrections/log/YYYY-MM-DD.md`: `{HH:MM} | {topic} | {summary}`
5. 보고: `Correction saved: Rule: "..." | Topic: ... | Scope: ...`
6. 같은 topic 3+ 반복 → `/enforce` 훅 전환 제안

## Write Gate
기본 저장. Skip: 이미 존재 또는 확실한 1회성. 확신 없으면 저장.
프로젝트 관습 영향 → CLAUDE.md 업데이트 제안. 글로벌 → ~/.claude/CLAUDE.md.
```

- [ ] **Step 8: Verify all compressions**

```bash
for f in rules/global/minimal-scope.md rules/global/long-running-backoff.md \
         rules/global/session-split.md rules/global/memory-lifecycle.md \
         rules/global/tdd-on-new-functions.md rules/tone/tone-kr.md \
         rules/correction/correction-protocol.md; do
  echo "$f: $(wc -c < $f) bytes"
done
```

### Task 5: Commit toolkit changes

- [ ] **Step 1: Stage and review**

```bash
git add -A
git diff --staged --stat
```

Expected: ~14 files changed (creates, deletes, modifications).

- [ ] **Step 2: Commit**

```bash
git commit -m "rules: global rules slim v6

- Create pre-work.md (merge before-starting + checklist-before-impl)
- Absorb review-learning-loop into superpowers step 7
- Rename completion-and-commits -> verification, review-multipass -> review
- Pure compress 7 remaining rules (correction-protocol, memory-lifecycle, etc)
- 13 -> 11 rules, ~-650 tokens estimated"
```

### Task 6: Symlink housekeeping (~/.claude/rules/)

이 task는 toolkit **머지 후**에만 실행. worktree가 아닌 main을 가리키는 symlink이므로.

**Files:**
- Delete symlinks: `~/.claude/rules/{before-starting,completion-and-commits,review-multipass,review-learning-loop}.md`
- Create symlinks: `~/.claude/rules/{pre-work,verification,review}.md`
- Delete standalone: `~/.claude/rules/correction-20260404-2100-checklist-before-impl.md`

- [ ] **Step 1: Merge toolkit worktree to main**

```bash
cd ~/git_workplace/daye-agent-toolkit && \
git stash push -u -m pre-merge -- plugins/dev-tools/skills/codex-cli/SKILL.md plugins/dev-tools/skills/codex-cli/scripts/call.sh && \
git merge --ff-only fix/global-rules-slim && \
git stash pop
```

- [ ] **Step 2: Delete old symlinks**

```bash
rm ~/.claude/rules/before-starting.md \
   ~/.claude/rules/completion-and-commits.md \
   ~/.claude/rules/review-multipass.md \
   ~/.claude/rules/review-learning-loop.md
```

- [ ] **Step 3: Create new symlinks**

```bash
ln -s ~/git_workplace/daye-agent-toolkit/rules/global/pre-work.md ~/.claude/rules/pre-work.md
ln -s ~/git_workplace/daye-agent-toolkit/rules/global/verification.md ~/.claude/rules/verification.md
ln -s ~/git_workplace/daye-agent-toolkit/rules/global/review.md ~/.claude/rules/review.md
```

- [ ] **Step 4: Delete standalone correction file** (merged into pre-work)

```bash
rm ~/.claude/rules/correction-20260404-2100-checklist-before-impl.md
```

- [ ] **Step 5: Cleanup worktree**

```bash
cd ~/git_workplace/daye-agent-toolkit && \
git worktree remove ../daye-agent-toolkit-rules-slim && \
git branch -d fix/global-rules-slim
```

### Task 7: Verification

- [ ] **Step 1: Count rules**

```bash
ls ~/.claude/rules/*.md | wc -l
```

Expected: **11**

- [ ] **Step 2: Broken symlink scan**

```bash
find -L ~/.claude/rules -maxdepth 1 -type l ! -exec test -e {} \; -print
```

Expected: empty output

- [ ] **Step 3: Symlink target check**

```bash
for f in ~/.claude/rules/*.md; do
  if [ -L "$f" ]; then
    target=$(readlink "$f")
    echo "$(basename $f) → $target"
  else
    echo "$(basename $f) [standalone]"
  fi
done
```

Expected: 모든 symlink가 `~/git_workplace/daye-agent-toolkit/rules/` 하위를 가리킴. standalone 없음 (correction-20260404 삭제됨).

- [ ] **Step 4: Total size check**

```bash
total=0; for f in ~/.claude/rules/*.md; do s=$(wc -c < "$f"); total=$((total + s)); done; echo "Total: $total bytes"
```

Expected: ~7,200B 이하.

### Task 8: Post-merge measurement

- [ ] **Step 1: 새 CC 세션 띄워서 cache_creation 측정**

```bash
cd /Users/dayejeong/dy-minions-squad && claude
```

새 세션에서 한 줄 입력 후, 이 세션에서:

```bash
f=$(ls -lt ~/.claude/projects/-Users-dayejeong-dy-minions-squad/*.jsonl | grep -v <현재세션ID> | head -1 | awk '{print $NF}')
grep -m1 '"type":"assistant"' "$f" | python3 -c "import json,sys;d=json.loads(sys.stdin.read());print('cache_creation:',d['message']['usage']['cache_creation_input_tokens'])"
```

Expected: ~44,455 (45,105 − ~650)

- [ ] **Step 2: Canary B 시나리오**

새 세션에서 여러 이슈 있는 PR/코드 리뷰 요청. 확인:
- 2 pass (per-file + cross-file) 수행됨
- 2개+ 발견 시 patterns.md 기록 제안 나옴

- [ ] **Step 3: Canary C 시나리오**

TS 프로젝트 작업 후 "다 됐어" 응답 시 확인:
- 테스트 실행 + `tsc --noEmit` + cross-file 검증 후에만 done

- [ ] **Step 4: Canary D 시나리오**

긴 조사 작업 후 구현 전환 시 확인:
- 발견사항 체크리스트 테이블 작성 + 사용자 확인 요청

---

## 참고: dy-minions-squad broken symlinks (별건)

`dy-minions-squad/.claude/rules/`에 다음 symlink가 있을 수 있음:
- `review-learning-loop.md` → toolkit 옛 경로 (`cc/global-rules/...`)
- `tdd-on-new-functions.md` → toolkit 옛 경로

이 작업 후 review-learning-loop.md가 삭제되므로 broken될 수 있음. 본 plan 범위 밖이지만 별건으로 정리 필요. `dy-minions-squad/.claude/rules/` 검사 후 broken symlink 삭제하라.
