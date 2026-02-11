# vault-memory:inbox-process

> `~/mingming-vault/+inbox/` 미분류 항목을 스캔하고 적절한 위치로 분류한다.

**기록 규격**: `~/mingming-vault/memory/format.md` 참조

## 트리거

- "인박스 정리", "inbox", "+inbox 처리"

## 워크플로우

### 1. 스캔

`~/mingming-vault/+inbox/` 모든 파일을 읽는다.
파일명, 내용, frontmatter(있으면) 분석.

### 2. 분류 제안

| 키워드/패턴 | 분류 대상 |
|------------|----------|
| 프로젝트명 (ronik, mingming, saju...) | `projects/work/{name}/` 또는 `projects/personal/{name}/` |
| meeting, 회의, 미팅 | `memory/reports/` |
| policy, 정책, 규칙 | `memory/policy/` |
| research, 리서치, 분석 | `memory/reports/` |

키워드 매칭 없으면 내용 기반으로 추천.

### 3. 사용자 확인

```markdown
| # | 파일 | → 이동 대상 | 이유 |
|---|------|-----------|------|
| 1 | meeting-notes.md | memory/reports/ | 미팅 키워드 |
| 2 | ronik-api-issue.md | projects/work/ronik/ | 프로젝트명 |
| 3 | random-idea.md | ??? | 분류 불확실 |
```

선택지:
- **전체 승인** — 모두 이동
- **N번 수정** — 특정 항목의 대상 변경
- **N번 보류** — 해당 항목 인박스에 유지

### 4. 이동

승인된 항목만 이동.
이동 시 frontmatter에 `moved_from: +inbox/`, `updated_at` 추가.

### 5. 요약

이동/보류/잔여 파일 수 출력.
