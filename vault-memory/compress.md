# vault-memory:compress

> 세션 종료 전 컨텍스트를 구조화하여 세션 로그에 저장한다.

**기록 규격**: `memory/format.md` 참조

## 트리거

- 세션 끝날 때: "compress", "세션 저장", "오늘 정리"
- 자동 제안: 긴 세션(30분+) 종료 시

## 워크플로우

### 1. 카테고리 선택

사용자에게 저장할 항목을 멀티셀렉트로 물어본다:

- [ ] 결정사항 — 이번 세션에서 내린 결정
- [ ] 핵심 배움 — 새로 알게 된 것
- [ ] 해결한 문제 — 디버깅, 트러블슈팅
- [ ] 수정된 파일 — 변경/생성한 파일 목록
- [ ] 미완료/대기 — 다음에 이어서 할 것
- [ ] 에러/이슈 — 미해결 에러, 알려진 이슈

기본값: 전체 선택. 해당 없는 카테고리는 자동 감지하여 생략 제안.

### 2. 내용 수집

선택된 카테고리별로 세션 대화를 분석하여 핵심 내용 추출.
각 항목 1-2줄로 간결하게. 코드 블록은 최소한으로.

### 3. Quick Reference 생성/업데이트

세션 전체를 요약:

```markdown
## Quick Reference
**Topics:** vault-memory, session-logging, hooks
**Projects:** mingming-ai
**Outcome:** 7개 스킬 구현 완료, format.md 규격 확정
- vault memory plugin 구조 설계
- SessionEnd hook 자동 기록 구현
```

규칙:
- 파일에 이미 Quick Reference가 있으면 기존 항목 아래에 추가
- 최대 10개 불릿 항목 (초과 시 오래된 것부터 제거)
- Topics/Projects/Outcome은 최신 세션 기준으로 통합

### 4. 파일 저장

**경로**: `memory/YYYY-MM-DD.md`

- 파일 없으면: frontmatter + Quick Reference + 세션 섹션 생성
- 파일 있으면: Quick Reference 업데이트 + 새 세션 섹션 append
- 세션 헤더: `## 세션 HH:MM (플랫폼, session-id-8자리)`

**SessionEnd hook이 이미 기본 세션 마커를 작성했을 수 있음:**
- 같은 session-id의 섹션이 있으면 → 해당 섹션을 카테고리 내용으로 보강(enrich)
- 없으면 → 새 세션 섹션 생성

### 5. 확인

저장 후 사용자에게:
- 저장 경로
- 카테고리별 항목 수
- Quick Reference 내용

## 자동 연계

### → tasks.yml (프로젝트 태스크 감지)
세션 중 수정된 파일을 `memory/projects/*/tasks.yml`의 repos/files_changed와 대조.
매칭되는 태스크가 있으면:
> "이 작업은 **t-ronik-001** (캘리봇 기획 재정리) 관련인 것 같아요. progress_log를 업데이트할까요?"
> → `vault-memory:task-update` 제안

매칭 로직:
1. 수정 파일 경로가 repos의 repo/branch와 겹치는지
2. 수정 파일이 기존 progress_log의 files_changed에 있었는지
3. 세션 주제(첫 메시지)에 태스크 ID나 프로젝트 키워드가 포함되는지

### → AGENTS.md (정책 감지)
결정사항 중 아래 키워드가 포함되면 `sync-agents` 제안:
- "항상", "규칙으로", "정책 추가", "매번", "금지", "필수"
> "이 결정을 AGENTS.md에 반영할까요?" → `vault-memory:sync-agents` 제안

### → MEMORY.md (장기 보관)
장기 보관 가치가 있는 결정/배움 발견 시:
> "이 항목을 MEMORY.md에 영구 저장할까요?" → `vault-memory:preserve` 제안

## 주의사항

- 민감 정보(API 키, 비밀번호)는 절대 저장하지 않음
- `updated_by` 필드는 실행 플랫폼에 맞게 (claude-code / openclaw)
- 빈 카테고리는 섹션 자체를 생략
