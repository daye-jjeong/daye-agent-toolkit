---
name: skill-forge
description: SKILL.md 스킬을 간결하게 생성하고 기존 스킬을 최적화합니다. 새 스킬 만들기, 긴 SKILL.md 리팩터링, 스킬 감사에 사용하세요.
argument-hint: "create <name>" 또는 "optimize <skill-path>" 또는 "audit"
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
| `audit`, `감사`, `점검` | **감사** | 레포 내 모든 스킬의 크기/구조 점검 |

키워드 없으면 사용자에게 모드를 물어보세요.

---

## 모드 1: 생성 (create)

### 사전 질문

1. 스킬 이름은?
2. 이 스킬이 자동화하는 반복 작업/워크플로우는?
3. 트리거 키워드는? (슬래시 커맨드 또는 자동 트리거)
4. 어떤 도구가 필요한가? (Read, Write, Edit, Bash, Web 등)

### 생성 구조

```
<skill-name>/
├── .claude-skill          # 메타데이터
├── SKILL.md               # 핵심 지시 (150줄 이내 타겟)
└── references/            # 상세 예시, 테이블, 템플릿 (선택)
    └── examples.md
```

### SKILL.md 작성 규칙

**150줄 이내**를 타겟으로 다음만 포함:

1. **Frontmatter** — name, description, argument-hint
2. **개요** — 1-2문장으로 스킬이 하는 일
3. **트리거/모드** — 언제, 어떻게 동작하는지
4. **핵심 워크플로우** — 단계별 지시 (간결하게)
5. **참조 포인터** — 상세가 필요하면 `{baseDir}/references/` 가리킴
6. **출력 포맷** — 결과물 형태 명시

**SKILL.md에 넣지 않는 것:**
- 긴 예시 (3줄 이상) → references/
- 큰 테이블 (5행 이상) → references/
- 템플릿 모음 → references/
- 배경 지식/이론 → references/

### .claude-skill 포맷

```json
{
  "name": "<skill-name>",
  "version": "1.0.0",
  "description": "<한줄 설명>",
  "entrypoint": "SKILL.md"
}
```

### 생성 후 체크리스트

- [ ] SKILL.md가 150줄 이내인가?
- [ ] frontmatter에 name, description이 있는가?
- [ ] 핵심 워크플로우가 명확한가?
- [ ] 상세 내용은 references/로 분리했는가?
- [ ] .claude-skill 파일이 있는가?

생성 완료 후 skills.json의 `local_skills`에 이름 추가를 안내하세요.

---

## 모드 2: 최적화 (optimize)

### 프로세스

1. **대상 SKILL.md 읽기** — 경로를 받거나, 레포 내 스킬 목록에서 선택
2. **분석** — 줄 수, 섹션별 크기, 이동 가능한 콘텐츠 식별
3. **분리 계획 제안** — 어떤 섹션을 references/로 이동할지 보여줌
4. **사용자 승인 후 실행** — SKILL.md 축소 + references/ 생성
5. **참조 포인터 추가** — `{baseDir}/references/`로의 포인터를 SKILL.md에 삽입

### 이동 기준

| 콘텐츠 유형 | 판단 |
|-------------|------|
| 핵심 워크플로우 단계 | **유지** |
| 트리거/모드 설명 | **유지** |
| 출력 포맷 (간략) | **유지** |
| 상세 예시 (3줄+) | **이동** |
| 큰 테이블 (5행+) | **이동** |
| 템플릿 모음 | **이동** |
| 배경 지식/이론 | **이동** |
| 도구 사용법 상세 | **이동** |

### 참조 포인터 패턴

이동한 콘텐츠 자리에 다음 포맷으로 포인터를 남김:

```markdown
**상세 예시**: `{baseDir}/references/examples.md` 참고
```

### 최적화 후 검증

- [ ] SKILL.md가 150줄 이내로 줄었는가?
- [ ] 핵심 워크플로우가 손상되지 않았는가?
- [ ] references/ 파일이 SKILL.md에서 적절히 참조되는가?
- [ ] 원본 대비 누락된 내용이 없는가?

---

## 모드 3: 감사 (audit)

레포 내 모든 스킬을 점검하여 리포트 생성.

### 프로세스

1. 레포 루트에서 `*/SKILL.md` 패턴으로 스킬 검색
2. 각 스킬의 줄 수, references/ 유무, .claude-skill 유무 확인
3. 리포트 출력

### 리포트 포맷

```
=== Skill Audit Report ===

| 스킬 | SKILL.md | refs/ | .claude-skill | 상태 |
|------|----------|-------|---------------|------|
| mermaid-diagrams | 217줄 | 7개 | ✓ | ⚠ 최적화 권장 |
| skill-forge | 98줄 | 0개 | ✓ | ✓ 양호 |

권장 사항:
- mermaid-diagrams: 217줄 → 최적화 필요 (타겟: 150줄)
```

상태 기준:
- **✓ 양호**: 150줄 이내 + .claude-skill 존재
- **⚠ 최적화 권장**: 150줄 초과
- **✗ 구조 문제**: .claude-skill 누락 또는 frontmatter 미비
