---
name: skill-forge
description: SKILL.md 생성/최적화/감사/검증 도구
argument-hint: "create <name>" 또는 "optimize <path>" 또는 "audit" 또는 "verify"
---

# Skill Forge

SKILL.md 기반 스킬의 생성과 최적화를 담당합니다.
Claude Code + OpenClaw 양쪽 호환을 기본으로 합니다.

## 모드 판단

$ARGUMENTS를 파싱하여 모드를 결정:

| 키워드 | 모드 | 설명 |
|--------|------|------|
| `create`, `만들어`, `새` | **생성** | 새 스킬을 간결한 구조로 생성 |
| `optimize`, `최적화`, `줄여`, `리팩터` | **최적화** | 기존 SKILL.md를 분석하고 references/로 분리 |
| `audit`, `감사`, `점검` | **감사** | 크기/구조 점검 + git diff 드리프트 분석 |
| `verify`, `검증`, `확인` | **검증** | 매니페스트 정합성 + 참조 무결성 검증 |

키워드 없으면 사용자에게 모드를 물어보세요.

## 모드 1: 생성 (create)

### 사전 질문

1. 스킬 이름은?
2. 이 스킬이 자동화하는 반복 작업/워크플로우는?
3. 트리거 키워드는? (슬래시 커맨드 또는 자동 트리거)
4. 어떤 도구가 필요한가? (Read, Write, Edit, Bash, Web 등)

### 생성 구조

```
<skill-name>/
├── .claude-skill          # 메타데이터 (CC 대상만)
├── SKILL.md               # 핵심 지시 (150줄 이내 타겟)
└── references/            # 상세 예시, 테이블, 템플릿 (선택)
```

### SKILL.md 작성 규칙

**150줄 이내**를 타겟으로 다음만 포함:

1. **Frontmatter** — name, description, argument-hint
2. **개요** — 1-2문장으로 스킬이 하는 일
3. **트리거/모드** — 언제, 어떻게 동작하는지
4. **핵심 워크플로우** — 단계별 지시 (간결하게)
5. **참조 포인터** — 상세가 필요하면 `{baseDir}/references/` 가리킴
6. **출력 포맷** — 결과물 형태 명시

**SKILL.md에 넣지 않는 것** → references/로 분리:
긴 예시(3줄+), 큰 테이블(5행+), 템플릿 모음, 배경 지식/이론

**템플릿 및 frontmatter 상세**: `{baseDir}/references/templates.md` 참고

### 생성 후 자동 동기화

스킬 파일 생성 완료 시, 다음을 **자동으로 수행**:

1. **`.claude-skill` 생성** — CC 대상 스킬인 경우 (CC전용 또는 CC+OpenClaw)
2. **`skills.json` 업데이트** — `local_skills` 배열에 스킬 이름 추가 (CC 대상만)
3. **`CLAUDE.md` 업데이트** — 해당 분류 테이블에 행 추가
4. **`setup.sh` 안내** — 사용자에게 `./setup.sh` 실행을 안내하여 symlink 갱신

### 생성 후 체크리스트

- [ ] SKILL.md 150줄 이내?
- [ ] frontmatter에 name, description 있음?
- [ ] 핵심 워크플로우 명확?
- [ ] 상세 내용 references/ 분리?
- [ ] skills.json + CLAUDE.md 동기화 완료?

## 모드 2: 최적화 (optimize)

### 프로세스

1. **대상 SKILL.md 읽기** — 경로를 받거나, 레포 내 스킬 목록에서 선택
2. **분석** — 줄 수, 섹션별 크기, 이동 가능한 콘텐츠 식별
3. **분리 계획 제안** — 어떤 섹션을 references/로 이동할지 보여줌
4. **사용자 승인 후 실행** — SKILL.md 축소 + references/ 생성
5. **참조 포인터 추가** — `{baseDir}/references/`로의 포인터를 SKILL.md에 삽입

**이동 기준 및 포인터 패턴**: `{baseDir}/references/optimize-guide.md` 참고

### 최적화 후 검증

- [ ] SKILL.md 150줄 이내로 축소?
- [ ] 핵심 워크플로우 손상 없음?
- [ ] references/ 파일이 SKILL.md에서 적절히 참조?
- [ ] 원본 대비 누락 없음?

## 모드 3: 감사 (audit)

레포 내 모든 스킬을 점검하여 리포트 생성.

### 프로세스

1. 레포 루트에서 `*/SKILL.md` 패턴으로 스킬 검색
2. 각 스킬의 줄 수, references/ 유무, .claude-skill 유무 확인
3. **드리프트 분석** — `git diff main...HEAD --name-only`로 변경 파일 수집
4. 변경 파일이 어떤 스킬의 참조 경로/패턴에 영향을 주는지 매핑
5. 구조 점검 + 드리프트 리포트 출력

### 드리프트 탐지

변경된 파일과 스킬 간 영향도를 분석:

- 스킬이 참조하는 파일이 삭제/이동되었는가?
- 새 파일이 기존 스킬 도메인에 해당하지만 미커버인가?
- 새 스킬이 생성되었으나 매니페스트에 미등록인가?

**리포트 포맷 및 상태 기준**: `{baseDir}/references/audit-report.md` 참고

## 모드 4: 검증 (verify)

스킬의 구조적 정합성과 매니페스트 동기화 상태를 검증.

### 검증 항목

1. **구조 검증** — 각 스킬의 SKILL.md frontmatter 필수 필드 (name, description)
2. **매니페스트 동기화** — `skills.json` `local_skills` ↔ 실제 `.claude-skill` 보유 스킬
3. **CLAUDE.md 동기화** — CLAUDE.md 스킬 테이블 ↔ 실제 스킬 목록
4. **참조 무결성** — SKILL.md 내 `{baseDir}/references/` 포인터 → 실제 파일 존재 여부
5. **데드 스킬** — `.claude-skill`만 있고 SKILL.md 없음, 또는 반대

### 검증 프로세스

1. `*/SKILL.md`와 `*/.claude-skill` 패턴으로 전체 스캔
2. `skills.json`의 `local_skills` 읽기
3. `CLAUDE.md`의 스킬 테이블 파싱
4. 3개 소스 간 diff → 불일치 항목 리포트
5. 불일치 발견 시 `AskUserQuestion`으로 자동 수정 여부 확인

### 출력 포맷

```
=== Skill Verify Report ===

매니페스트 동기화: V (15/15)
CLAUDE.md 동기화:  W 2개 누락 (output-style-ko, check-quota)
참조 무결성:       V
데드 스킬:         없음

수정 필요:
- CLAUDE.md에 output-style-ko, check-quota 추가 필요
```

자동 수정 승인 시: skills.json, CLAUDE.md를 직접 Edit하여 동기화.