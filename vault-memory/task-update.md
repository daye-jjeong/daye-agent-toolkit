# vault-memory:task-update

> 태스크 시작/진행/완료 시 t-*.md 파일을 업데이트하고 진행 로그를 기록한다.

**기록 규칙**: `recording-rules.md` → 프로젝트 태스크 섹션 참조
**태스크 템플릿**: `memory/.obsidian/templates/task-template.md` 참조

## 트리거

- "태스크 시작", "t-xxx-nnn 시작", "작업 시작"
- "태스크 완료", "t-xxx-nnn 끝", "작업 완료"
- "진행 기록", "progress 업데이트"
- "태스크 정의 채워줘", "description 채워", "태스크 내용 보강"
- compress 중 프로젝트 작업 감지 시 자동 제안

## 워크플로우

### 1. 태스크 식별

태스크 ID가 명시되지 않으면:
1. `memory/projects/*/t-*.md`에서 `status: in_progress` 태스크 목록 표시
2. 사용자가 선택하거나 새 태스크 지정

태스크 ID가 명시되면:
1. `memory/projects/` 하위에서 `{task_id}.md` 파일 검색
2. 파일 존재 확인

### 2. 액션 선택

| 액션 | 설명 | t-*.md 변경 |
|------|------|-------------|
| **시작** | 태스크 작업 시작 | frontmatter status → in_progress |
| **진행** | 중간 진행 기록 | `## 진행 로그`에 append |
| **완료** | 태스크 완료 | status → done, completed 날짜 추가 |
| **차단** | 블로커 기록 | status → blocked, 진행 로그에 사유 |
| **핸드오프** | 다른 플랫폼에 인수인계 | 진행 로그에 handoff 메모 |
| **정의(enrich)** | 태스크 내용 보강 | 컨텍스트, linked_goals 등 채우기 |

### 3. 정보 수집

#### 진행 로그 항목 (필수)

`## 진행 로그` 섹션에 append:
```markdown
## 진행 로그
- 2026-02-11 (claude-code): 캘리 프로세스 as-is 정리 완료, 3단계 수동 프로세스 파악
```

#### 코드 변경 (코드 작업 시)

`## 코드 변경` 섹션 업데이트:
```markdown
## 코드 변경
- repo: ronik-inc/cali-bot
- branch: feature/t-ronik-001
- PR: #42
```

자동 수집 가능한 정보:
- `updated_by`: 현재 플랫폼 (claude-code / openclaw)
- `updated_at`: 현재 시각
- `branch`: 현재 git branch

사용자에게 물어봐야 하는 정보:
- 진행 로그 내용: 작업 내용 1-2줄 요약

### 4. frontmatter 업데이트

```yaml
# 시작 시
status: in_progress       # ← 변경
updated_by: claude-code
updated_at: 2026-02-12T15:30

# 완료 시
status: done              # ← 변경
completed: 2026-02-12     # ← 추가
updated_by: claude-code
updated_at: 2026-02-12T15:30
```

### 5. subtask 처리

`## 서브태스크` 섹션의 체크박스 업데이트:
```markdown
## 서브태스크
- [x] 현재 캘리 프로세스 as-is 정리
- [ ] 봇 적용 시나리오 to-be 설계
```

모든 서브태스크가 완료되면 → 태스크 자체도 done으로 제안.

### 6. 알림

태스크 상태 변경 시:
- **완료**: "t-ronik-001 완료됨 (by claude-code)" → 텔레그램 알림
- **핸드오프**: "t-ronik-001 핸드오프 → openclaw에서 이어서" → 텔레그램 알림
- **차단**: "t-ronik-001 blocked: {사유}" → 텔레그램 알림

### 7. 세션 로그 연동

t-*.md 업데이트 후, 현재 세션 로그(`memory/YYYY-MM-DD.md`)에도 한 줄 기록:
```markdown
- **t-ronik-001**: 캘리 프로세스 as-is 정리 완료 (by claude-code)
```

## 핸드오프 프로토콜

다른 플랫폼에 작업을 넘길 때 진행 로그에 기록:

```markdown
## 진행 로그
- 2026-02-11 (claude-code): [HANDOFF → openclaw] as-is 정리 완료. to-be 설계는 Notion 데이터 접근이 필요해서 OpenClaw에서 진행. 참고: memory/docs/cali-as-is.md
```

받는 쪽은 `vault-memory:resume` 또는 `task-brief`로 컨텍스트 확인.

## 정의(enrich) 워크플로우

description이 비어 있는 태스크에 내용을 채우는 작업.

### 트리거
- "태스크 정의 채워줘" / "description 채워" / "태스크 내용 보강"
- task-brief 시 컨텍스트 누락 태스크 감지 → 자동 제안

### 채울 영역

| 영역 | 필수 | 설명 |
|------|------|------|
| `## 컨텍스트` | Y | 이 태스크가 **무엇을 왜 하는지** 1-3줄. 완료 기준 포함 |
| `linked_goals` | N | 연결된 목표 (frontmatter) |

## 주의사항

- frontmatter 수정 시 `updated_by` + `updated_at` 필수 갱신
- 진행 로그는 append-only (최신이 아래)
- 코드 변경의 commits는 주요 커밋만 (모든 커밋 나열 금지)
- 민감 정보(API 키, 비밀번호)는 기록 금지
