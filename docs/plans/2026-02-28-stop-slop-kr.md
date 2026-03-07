# stop-slop-kr 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 한국어 AI 말투 교정 스킬 생성 + rules 자동 배포 인프라 추가

**Architecture:** `shared/stop-slop-kr/`에 스킬 생성, Makefile에 rules 자동 발견/symlink 로직 추가, 기존 correction-protocol.md를 스킬 안으로 이동

**Tech Stack:** Makefile, Markdown (SKILL.md)

---

### Task 1: stop-slop-kr 스킬 파일 생성

**Files:**
- Create: `shared/stop-slop-kr/.claude-skill`
- Create: `shared/stop-slop-kr/SKILL.md`
- Create: `shared/stop-slop-kr/rules/tone-kr.md`
- Create: `shared/stop-slop-kr/references/phrases.md`
- Create: `shared/stop-slop-kr/references/examples.md`

**Step 1: .claude-skill 생성**

```json
{
  "name": "stop-slop-kr",
  "version": "1.0.0",
  "description": "한국어 AI 말투 교정 — 번역체, 아첨, 상투어 제거",
  "entrypoint": "SKILL.md"
}
```

**Step 2: SKILL.md 생성**

```markdown
---
name: stop-slop-kr
description: 한국어 AI 말투 교정 — 번역체, 아첨, 상투어 제거
---

# 한국어 AI Slop 교정

AI 특유의 번역체, 아첨, 상투어를 잡아서 자연스러운 한국어로 바꾼다.

## 모드

| 모드 | 언제 | 뭘 하나 |
|------|------|---------|
| **예방** | 스킬 로드 시 자동 | 아래 규칙을 따라서 처음부터 자연스럽게 씀 |
| **퇴고** | 사용자가 텍스트를 주면 | slop을 찾아서 교정본 제시 |

## 금지 표현

→ `{baseDir}/references/phrases.md` 참조

## 구조 패턴

쓰지 마라:
- 삼중 나열 (A, B, 그리고 C — 이 패턴 반복)
- 모든 답변에 리스트/볼드 남발
- 수사적 질문 직후 바로 답변 ("왜일까요? 바로 ~이기 때문입니다")
- 매 단락 첫 문장을 볼드로 시작

## 가독성

- 표로 정리할 수 있으면 표로
- 한 문장은 짧게. 2줄 넘기지 마
- 어려운 말 대신 쉬운 말
- 핵심 먼저, 배경은 나중에
- 군더더기 삭제 — "현 시점에서"→"지금", "~의 경우에는"→"~하면"

## 교정 원칙

- 정보는 유지하고 말투만 바꿈
- 과장을 빼고 사실만
- 번역체 → 자연스러운 한국어
- 길면 줄임

## 퇴고 모드

사용자가 텍스트를 주면:

1. slop 패턴을 찾는다
2. 교정본을 보여준다
3. 뭘 바꿨는지 간단히 설명한다

예방 모드보다 적극적으로 교정한다:
- 문장 구조 개선
- 표로 변환 가능한 내용은 표 제안
- 불필요한 접속사/부사 삭제
```

**Step 3: rules/tone-kr.md 생성**

```markdown
# 한국어 톤

한국어로 답변할 때 따르는 규칙.

## 하지 마라

- 과장 아첨: "좋은 질문이에요!", "핵심을 찌르셨네요", "정확한 통찰입니다"
- 마무리 상투어: "도움이 되셨길 바랍니다", "더 궁금한 점 있으시면"
- 번역체: "~를 탐색하다", "심층적으로 들여다보면", "~를 풀어서 설명하면"
- 후속 제안 남발: "원하시면 ~~~해드릴까요?"
- 불필요한 이모지

## 해라

- 바로 본론부터
- 짧고 직접적인 문장
- 자연스러운 한국어 종결어미
```

**Step 4: references/phrases.md 생성**

한국어 AI slop 표현 목록. 카테고리별로 금지 표현 + 대체어를 표로 정리.

카테고리: 아첨, 번역체, 상투어, 과장, 후속제안, 접속사/부사 남용

**Step 5: references/examples.md 생성**

Before/After 3~5개 예시.

**Step 6: 커밋**

```bash
git add shared/stop-slop-kr/
git commit -m "feat: add stop-slop-kr skill"
```

---

### Task 2: Makefile에 rules 자동 배포 추가

**Files:**
- Modify: `Makefile`

**Step 1: RULES_DIR 변수 추가**

`SKILLS_DIR` 아래에:

```makefile
RULES_DIR := $(HOME)/.claude/rules
```

**Step 2: install-cc에 rules symlink 로직 추가**

기존 스킬 symlink 루프 다음에, rules 발견 + symlink 루프 추가:

```makefile
@echo ""
@echo "=== Rules symlink ==="
@mkdir -p $(RULES_DIR)
@for rule_file in $$(find shared/*/rules cc/*/rules -name '*.md' 2>/dev/null); do \
    name=$$(basename $$rule_file); \
    dest="$(RULES_DIR)/$$name"; \
    if [ -L "$$dest" ]; then rm "$$dest"; \
    elif [ -e "$$dest" ]; then echo "  ⚠ SKIPPED $$name (exists, not symlink)"; continue; \
    fi; \
    ln -s "$(REPO_DIR)/$$rule_file" "$$dest"; \
    echo "  ✓ $$name → $$rule_file"; \
done
```

**Step 3: clean에 rules symlink 제거 추가**

```makefile
@echo ""
@echo "=== Removing rules symlinks ==="
@for rule_file in $$(find shared/*/rules cc/*/rules -name '*.md' 2>/dev/null); do \
    name=$$(basename $$rule_file); \
    dest="$(RULES_DIR)/$$name"; \
    if [ -L "$$dest" ]; then \
        rm "$$dest"; \
        echo "  ✓ removed rule $$name"; \
    fi; \
done
```

**Step 4: status에 rules 상태 표시 추가**

CC Symlinks 섹션 다음에:

```makefile
@echo "=== Rules ==="
@for rule_file in $$(find shared/*/rules cc/*/rules -name '*.md' 2>/dev/null); do \
    name=$$(basename $$rule_file); \
    dest="$(RULES_DIR)/$$name"; \
    if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
    else echo "  ✗ $$name (not installed)"; \
    fi; \
done
```

**Step 5: 커밋**

```bash
git add Makefile
git commit -m "feat: add rules auto-discovery to install-cc"
```

---

### Task 3: correction-protocol.md를 스킬 안으로 이동

**Files:**
- Move: `.claude/rules/correction-protocol.md` → `cc/correction-memory/rules/correction-protocol.md`

**Step 1: 디렉토리 생성 + 파일 이동**

```bash
mkdir -p cc/correction-memory/rules
mv .claude/rules/correction-protocol.md cc/correction-memory/rules/correction-protocol.md
```

**Step 2: correction-memory SKILL.md 업데이트**

자동 트리거 섹션의 경로 설명 수정:

```
기존: 교정 감지 → 자동 저장은 `.claude/rules/correction-protocol.md`가 담당.
변경: 교정 감지 → 자동 저장은 `{baseDir}/rules/correction-protocol.md`가 담당.
      `make install-cc` 시 `~/.claude/rules/`에 자동 symlink됨.
```

**Step 3: 커밋**

```bash
git add cc/correction-memory/rules/ .claude/rules/
git commit -m "refactor: move correction-protocol into correction-memory skill"
```

---

### Task 4: 검증

**Step 1: make install-cc 실행**

```bash
make install-cc
```

기대 출력에 rules symlink 포함:
```
=== Rules symlink ===
  ✓ tone-kr.md → shared/stop-slop-kr/rules/tone-kr.md
  ✓ correction-protocol.md → cc/correction-memory/rules/correction-protocol.md
```

**Step 2: symlink 확인**

```bash
ls -la ~/.claude/rules/tone-kr.md
ls -la ~/.claude/rules/correction-protocol.md
```

둘 다 레포 안 파일을 가리키는 symlink이어야 함.

**Step 3: make status 확인**

rules 섹션에 두 파일 모두 ✓로 표시되는지 확인.

**Step 4: make clean 후 재확인**

```bash
make clean
ls ~/.claude/rules/tone-kr.md 2>/dev/null && echo "FAIL: not removed" || echo "OK: removed"
```

**Step 5: 최종 커밋 (필요시)**

검증 중 수정사항 있으면 커밋.
