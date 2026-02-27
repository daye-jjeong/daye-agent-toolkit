# correction-memory 스킬 구현 + vault-memory 폐기

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Claude Code에서 교정 사항을 3계층(Rules/Register/Log)으로 자동 기록하는 correction-memory 스킬을 만들고, vault-memory를 삭제한다.

**Architecture:** SKILL.md + references/ 구조의 선언적 스킬. 코드 없이 Claude의 행동을 지시하는 프롬프트 기반. `.claude/rules/corrections.md`(git 공유)와 auto memory `corrections/`(로컬)에 저장.

**Tech Stack:** SKILL.md (마크다운), `.claude-skill` (JSON), `skills.json` 매니페스트

---

## Task 1: correction-memory 디렉토리 + 메타 생성

**Files:**
- Create: `correction-memory/.claude-skill`
- Create: `correction-memory/references/` (빈 디렉토리)

**Step 1: 디렉토리 생성**

```bash
mkdir -p correction-memory/references
```

**Step 2: .claude-skill 메타데이터 작성**

```json
{
  "name": "correction-memory",
  "version": "1.0.0",
  "description": "교정 기억 — 실수를 기억하고 반복하지 않게 하는 3계층 메모리",
  "entrypoint": "SKILL.md"
}
```

**Step 3: 커밋**

```bash
git add correction-memory/.claude-skill
git commit -m "feat(correction-memory): 스킬 디렉토리 + 메타 생성"
```

---

## Task 2: SKILL.md 작성 — 메인 스킬 파일

**Files:**
- Create: `correction-memory/SKILL.md`

**Step 1: SKILL.md 작성**

frontmatter + 스킬 개요 + 서브커맨드 테이블 + 3계층 아키텍처 요약 + 경로 규칙.
150줄 이내 유지 (CLAUDE.md 규칙).

```markdown
---
name: correction-memory
description: 교정 기억 — 실수를 3계층으로 기록하여 반복 방지
argument-hint: "save" 또는 "search <키워드>" 또는 "review" 또는 "stats"
---

# Correction Memory

교정 사항을 3계층(Rules → Register → Log)에 동시 저장하여,
같은 실수를 반복하지 않게 한다. Boris Cherny의 "Compounding Engineering" 패턴 기반.

## 모드 판단

$ARGUMENTS를 파싱하여 모드 결정:

| 키워드 | 모드 | 설명 |
|--------|------|------|
| `save`, `기억해`, `저장` | **저장** | 교정 사항을 3계층에 동시 저장 |
| `search`, `검색`, `찾아` | **검색** | 키워드로 교정 이력 검색 |
| `review`, `정리`, `리뷰` | **리뷰** | 현재 규칙 전체 리뷰 + 중복/모순 제거 |
| `stats`, `통계` | **통계** | 주제별 빈도, 최근 추세 |

키워드 없으면 `save` 모드로 동작.

## 3계층 아키텍처

| 계층 | 경로 | 공유 | 용도 |
|------|------|------|------|
| **Rules** | `{project}/.claude/rules/corrections.md` | git (팀) | Claude에게 적용할 행동 규칙 |
| **Register** | auto memory `corrections/{topic}.md` | 로컬 (나만) | 주제별 교정 이력 + 사유 |
| **Log** | auto memory `corrections/log/YYYY-MM-DD.md` | 로컬 (나만) | 교정 발생 타임라인 |

> auto memory 경로: `~/.claude/projects/{project-hash}/memory/corrections/`

## 모드별 상세

### 저장 (save)

교정 전파 프로토콜: [correction-propagation.md](references/correction-propagation.md)

### 검색 (search)

1. $ARGUMENTS에서 키워드 추출
2. Layer 1 (Rules) 검색 → 현재 적용 중인 관련 규칙
3. Layer 2 (Register) 검색 → 주제별 교정 이력
4. 결과를 구조적으로 보여주기

### 리뷰 (review)

1. Layer 1 (Rules) `corrections.md` 전체 읽기
2. 중복 규칙 식별 + 병합 제안
3. 모순 규칙 식별 + 해결 제안
4. 더 이상 유효하지 않은 규칙 제거 제안
5. 사용자 승인 후 업데이트

### 통계 (stats)

1. Layer 3 (Log) 전체 파싱
2. 주제별 교정 빈도 집계
3. 최근 7일/30일 추세
4. 가장 많이 교정되는 토픽 → "집중 개선 필요" 안내

## Write Gate

저장 가치 판단 기준: [write-gate.md](references/write-gate.md)

## Register 토픽

초기 토픽 분류: [register-topics.md](references/register-topics.md)
```

**Step 2: 커밋**

```bash
git add correction-memory/SKILL.md
git commit -m "feat(correction-memory): SKILL.md 메인 스킬 파일 작성"
```

---

## Task 3: references/correction-propagation.md — 교정 전파 프로토콜

**Files:**
- Create: `correction-memory/references/correction-propagation.md`

**Step 1: 교정 전파 프로토콜 작성**

교정 발생 시 3곳 동시 업데이트하는 상세 절차.
각 계층별 포맷, superseded 마커, 토픽 자동 분류 규칙 포함.

핵심 내용:

```markdown
# 교정 전파 프로토콜

## 트리거

사용자가 Claude의 행동을 교정할 때 자동 감지:
- 명시적: "이거 기억해", "다시는 하지 마", "항상 ~해"
- 암시적: 같은 지시를 2회 이상 반복할 때

## 전파 절차

### 1단계: Write Gate 통과 확인
→ [write-gate.md](write-gate.md) 기준으로 저장 가치 판단

### 2단계: 토픽 분류
→ [register-topics.md](register-topics.md) 기준으로 자동 분류
→ 기존 토픽에 안 맞으면 새 토픽 파일 생성

### 3단계: 3계층 동시 저장

#### Layer 1 — Rules
파일: `{project}/.claude/rules/corrections.md`

포맷:
- 한 줄에 하나의 규칙
- `- ` 접두사 (마크다운 리스트)
- 영어로 작성 (Claude가 가장 잘 따름)
- DO/DON'T 명확히 구분
- 최대 50개 규칙 유지 (초과 시 review 모드 제안)

예시:
- ALWAYS use bun, NEVER use npm for package management
- NEVER use TypeScript enum, use string literal unions instead
- ALWAYS run typecheck before committing

#### Layer 2 — Register
파일: `~/.claude/projects/{hash}/memory/corrections/{topic}.md`

포맷:
## {소제목}
- [{날짜}] {이전} → {이후} (사유: {사유})
- [superseded] {이전 규칙} ({날짜} 폐기)

새 교정이 기존 규칙을 대체하면 이전 항목에 [superseded] 마커 추가.

#### Layer 3 — Log
파일: `~/.claude/projects/{hash}/memory/corrections/log/YYYY-MM-DD.md`

포맷:
{HH:MM} | {토픽} | {요약} | {트리거 유형}

트리거 유형: 사용자 직접 교정 | 반복 지시 감지 | 코드 리뷰 결과

### 4단계: 확인 메시지

저장 완료 후 사용자에게 요약 보고:
규칙 추가: "{규칙 내용}"
토픽: {토픽명}
적용 범위: 이 프로젝트의 모든 세션
```

**Step 2: 커밋**

```bash
git add correction-memory/references/correction-propagation.md
git commit -m "feat(correction-memory): 교정 전파 프로토콜 상세 작성"
```

---

## Task 4: references/write-gate.md — 저장 기준

**Files:**
- Create: `correction-memory/references/write-gate.md`

**Step 1: Write Gate 규칙 작성**

```markdown
# Write Gate — 저장 가치 판단 기준

교정이 감지되면 저장 전에 이 기준을 적용한다.
모든 교정을 저장하면 노이즈가 되어 규칙의 가치가 떨어진다.

## 저장 O (통과)

| 기준 | 예시 |
|------|------|
| 행동 변경을 유발하는 교정 | "npm 말고 bun 써" |
| 반복된 실수 (2회 이상 같은 교정) | 같은 패턴 2번째 교정 |
| 아키텍처 결정 사항 | "이 프로젝트에서는 Repository 패턴 써" |
| 프로젝트 컨벤션 | "함수명은 camelCase" |
| 도구/라이브러리 선호 | "date-fns 대신 dayjs 써" |
| 보안/안전 관련 | "API 키 하드코딩하지 마" |

## 저장 X (차단)

| 기준 | 예시 |
|------|------|
| 일회성 오타/단순 실수 | "여기 세미콜론 빠졌어" |
| 컨텍스트 의존적 판단 | "이번에는 A 방식으로 해" (다음엔 B일 수 있음) |
| 이미 CLAUDE.md에 있는 규칙 | 중복 저장 방지 |
| 이미 .claude/rules/에 있는 규칙 | 중복 저장 방지 |
| 취향/미관 관련 (코드 무관) | "이모지 넣어줘" |

## 판단 어려울 때

확신이 없으면 사용자에게 물어본다:
"이 교정을 영구 규칙으로 저장할까요? (이 프로젝트의 모든 세션에 적용됩니다)"
```

**Step 2: 커밋**

```bash
git add correction-memory/references/write-gate.md
git commit -m "feat(correction-memory): Write Gate 저장 기준 작성"
```

---

## Task 5: references/register-topics.md — 토픽 분류

**Files:**
- Create: `correction-memory/references/register-topics.md`

**Step 1: Register 토픽 분류 작성**

```markdown
# Register 토픽 분류

교정 사항을 주제별로 분류하여 `corrections/{topic}.md`에 저장한다.

## 기본 토픽

| 토픽 | 파일명 | 포함 내용 |
|------|--------|----------|
| 도구/런타임 | `tooling.md` | 패키지 매니저, CLI, 빌드 도구, 런타임 설정 |
| 아키텍처 | `architecture.md` | 디자인 패턴, 파일 구조, 모듈 구성 |
| 테스팅 | `testing.md` | 테스트 프레임워크, 테스트 작성 규칙, 커버리지 |
| 코딩 스타일 | `style.md` | 네이밍, 포매팅, 언어별 관습, 코드 구조 |
| API/외부 연동 | `integrations.md` | API 사용법, 인증, 외부 서비스 연동 |
| 일반 | `general.md` | 위 카테고리에 속하지 않는 교정 |

## 토픽 자동 분류 규칙

키워드 기반으로 자동 분류:
- npm, bun, node, python, docker, CLI → `tooling.md`
- pattern, structure, module, layer, DI → `architecture.md`
- test, jest, vitest, mock, assert → `testing.md`
- name, format, lint, prettier, indent → `style.md`
- API, auth, fetch, endpoint, webhook → `integrations.md`
- 그 외 → `general.md`

## 새 토픽 생성

기존 토픽에 맞지 않는 교정이 3개 이상 `general.md`에 쌓이면:
1. 공통 주제를 식별
2. 새 토픽 파일 생성을 사용자에게 제안
3. 승인 시 해당 항목을 새 토픽으로 이동
```

**Step 2: 커밋**

```bash
git add correction-memory/references/register-topics.md
git commit -m "feat(correction-memory): Register 토픽 분류 기준 작성"
```

---

## Task 6: skills.json 업데이트

**Files:**
- Modify: `skills.json`

**Step 1: local_skills에 correction-memory 추가**

`skills.json`의 `local_skills` 배열에 `"correction-memory"` 추가.
알파벳순 삽입 → `banksalad-import` 다음, `goal-planner` 앞.

```json
"local_skills": [
    "banksalad-import",
    "correction-memory",
    "goal-planner",
    ...
]
```

**Step 2: 커밋**

```bash
git add skills.json
git commit -m "feat(correction-memory): skills.json에 등록"
```

---

## Task 7: vault-memory 삭제

**Files:**
- Delete: `vault-memory/` 디렉토리 전체
- Modify: `skills.json` — `local_skills`에서 `"vault-memory"` 제거

**Step 1: skills.json에서 vault-memory 제거**

`local_skills` 배열에서 `"vault-memory"` 항목 삭제.

**Step 2: vault-memory 디렉토리 삭제**

```bash
rm -rf vault-memory/
```

**Step 3: 커밋**

```bash
git add -A vault-memory/ skills.json
git commit -m "chore: vault-memory 스킬 삭제 — dy-minions-squad가 대체"
```

---

## Task 8: CLAUDE.md 업데이트

**Files:**
- Modify: `CLAUDE.md`

**Step 1: 스킬 분류 테이블 업데이트**

CLAUDE.md의 "Claude Code + OpenClaw 양쪽" 테이블에서 vault-memory 행 제거.
"Claude Code 전용" 테이블에 correction-memory 행 추가.

변경 전:
```
| vault-memory | Obsidian vault 메모리 관리 |
```

변경 후: vault-memory 행 삭제.

"Claude Code 전용 (3개)" → "Claude Code 전용 (4개)" 로 변경하고 추가:
```
| correction-memory | 교정 기억 — 실수 반복 방지 3계층 메모리 |
```

"Claude Code + OpenClaw 양쪽 (12개)" → "(11개)"로 변경.

**Step 2: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md에 correction-memory 추가, vault-memory 제거"
```

---

## Task 9: setup.sh 실행 + 기능 검증

**Step 1: setup.sh 실행**

```bash
./setup.sh
```

symlink 생성 확인: `~/.claude/skills/correction-memory` → 이 레포의 `correction-memory/`

**Step 2: 스킬 인식 확인**

새 Claude Code 세션에서 correction-memory 스킬이 목록에 보이는지 확인.
`/correction-memory:save` 서브커맨드가 호출 가능한지 확인.

**Step 3: 기능 테스트**

테스트 시나리오:
1. "npm 말고 bun 써. 이거 기억해" → save 모드 트리거 → 3계층 저장 확인
2. `/correction-memory:search bun` → 검색 모드 → 방금 저장한 규칙 찾기
3. `/correction-memory:stats` → 통계 모드 → 교정 1건 표시
4. `.claude/rules/corrections.md` 파일 생성 확인
5. auto memory `corrections/tooling.md` 파일 생성 확인

**Step 4: 최종 커밋 (필요 시)**

```bash
git add -A
git commit -m "chore: setup 후 정리"
```
