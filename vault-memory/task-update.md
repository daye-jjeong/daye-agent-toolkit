# vault-memory:task-update

> 태스크 시작/진행/완료 시 tasks.yml을 업데이트하고 progress_log + repos를 기록한다.

**기록 규칙**: `recording-rules.md` → 프로젝트 태스크 섹션 참조
**태스크 템플릿**: `memory/projects/config/task-template.yml` 참조

## 트리거

- "태스크 시작", "t-xxx-nnn 시작", "작업 시작"
- "태스크 완료", "t-xxx-nnn 끝", "작업 완료"
- "진행 기록", "progress 업데이트"
- "태스크 정의 채워줘", "description 채워", "태스크 내용 보강"
- compress 중 프로젝트 작업 감지 시 자동 제안

## 워크플로우

### 1. 태스크 식별

태스크 ID가 명시되지 않으면:
1. `memory/projects/*/tasks.yml`에서 `status: in_progress` 태스크 목록 표시
2. 사용자가 선택하거나 새 태스크 지정

태스크 ID가 명시되면:
1. 해당 프로젝트의 `tasks.yml` 읽기
2. 태스크 존재 확인

### 2. 액션 선택

| 액션 | 설명 | tasks.yml 변경 |
|------|------|---------------|
| **시작** | 태스크 작업 시작 | status → in_progress |
| **진행** | 중간 진행 기록 | progress_log append |
| **완료** | 태스크 완료 | status → done, completed 날짜 |
| **차단** | 블로커 기록 | status → blocked, progress_log에 사유 |
| **핸드오프** | 다른 플랫폼에 인수인계 | progress_log에 handoff 메모 |
| **정의(enrich)** | 태스크 내용 보강 | description, tags, links, linked_goals 채우기 |

### 3. 정보 수집

#### progress_log 항목 (필수)
```yaml
progress_log:
  - date: 2026-02-11
    by: claude-code          # 현재 플랫폼
    summary: "캘리 프로세스 as-is 정리 완료, 3단계 수동 프로세스 파악"
    files_changed:
      - memory/docs/cali-as-is.md
      - src/calibration/process.py
```

#### repos 항목 (코드 작업 시)
```yaml
repos:
  - repo: ronik-inc/cali-bot
    branch: feature/t-ronik-001
    prs: [42]
    commits: [abc1234, def5678]
```

자동 수집 가능한 정보:
- `by`: 현재 플랫폼 (claude-code / openclaw)
- `date`: 오늘 날짜
- `files_changed`: 세션 중 수정한 파일 (Edit/Write 추적)
- `branch`: 현재 git branch
- `commits`: 세션 중 생성한 커밋

사용자에게 물어봐야 하는 정보:
- `summary`: 작업 내용 1-2줄 요약

### 4. tasks.yml 업데이트

```yaml
# 시작 시
- id: t-ronik-001
  status: in_progress       # ← 변경
  # ... 기존 필드 유지

# 완료 시
- id: t-ronik-001
  status: done              # ← 변경
  completed: 2026-02-11     # ← 추가
  progress_log:              # ← append
    - date: 2026-02-11
      by: claude-code
      summary: "구현 완료, 테스트 통과"
  repos:                     # ← 추가/업데이트
    - repo: ronik-inc/cali-bot
      branch: feature/t-ronik-001
      prs: [42]
```

### 5. subtask 처리

subtask가 있으면 개별 완료 처리:
```yaml
subtasks:
  - title: "현재 캘리 프로세스 as-is 정리"
    status: done            # ← 변경
  - title: "봇 적용 시나리오 to-be 설계"
    status: todo            # 아직
```

모든 subtask가 done이면 → 태스크 자체도 done으로 제안.

### 6. 알림

태스크 상태 변경 시:
- **완료**: "t-ronik-001 완료됨 (by claude-code)" → 텔레그램 알림
- **핸드오프**: "t-ronik-001 핸드오프 → openclaw에서 이어서" → 텔레그램 알림
- **차단**: "t-ronik-001 blocked: {사유}" → 텔레그램 알림

알림 스크립트: `scripts/notify_task_update.py` (미구현 → 구현 필요)

### 7. 세션 로그 연동

tasks.yml 업데이트 후, 현재 세션 로그(`memory/YYYY-MM-DD.md`)에도 한 줄 기록:
```markdown
- **t-ronik-001**: 캘리 프로세스 as-is 정리 완료 (by claude-code)
```

## 핸드오프 프로토콜

다른 플랫폼에 작업을 넘길 때:

```yaml
progress_log:
  - date: 2026-02-11
    by: claude-code
    summary: |
      [HANDOFF → openclaw]
      as-is 정리 완료. to-be 설계는 Notion 데이터 접근이 필요해서 OpenClaw에서 진행.
      참고: memory/docs/cali-as-is.md
    files_changed:
      - memory/docs/cali-as-is.md
```

받는 쪽은 `vault-memory:resume` 또는 `task-brief`로 컨텍스트 확인.

## 정의(enrich) 워크플로우

description이 비어 있는 태스크에 내용을 채우는 작업.

### 트리거
- "태스크 정의 채워줘" / "description 채워" / "태스크 내용 보강"
- task-brief 시 description 누락 태스크 감지 → 자동 제안

### 채울 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `description` | Y | 이 태스크가 **무엇을 왜 하는지** 1-3줄. 완료 기준 포함 |
| `tags` | N | 분류 태그 (feature, bugfix, maintenance, research, infra) |
| `links` | N | 관련 문서/URL |
| `linked_goals` | N | 연결된 목표 (goals/ 파일의 `[[위키링크]]`) |

### description 작성 규칙

```yaml
description: |
  [무엇을] 현재 수동 캘리브레이션 프로세스를 분석하고 AI 봇 자동화 시나리오를 설계한다.
  [왜] 로닉 캘리 작업이 반복적이고 시간 소모가 크기 때문.
  [완료 기준] as-is 문서 + to-be 시나리오 3가지 + 입출력 포맷 정의 완료.
```

- **무엇을**: 구체적 행동 (동사로 시작)
- **왜**: 이 태스크의 배경/필요성
- **완료 기준**: 어떻게 되면 "끝"인지

### 배치 enrich

여러 태스크를 한 번에 채울 때:
1. 프로젝트 지정 또는 전체 스캔
2. description 없는 태스크 목록 출력
3. 각 태스크에 대해 title + subtasks + 프로젝트 컨텍스트로 description 초안 생성
4. 사용자 확인 후 tasks.yml 업데이트

## 주의사항

- tasks.yml 전체를 덮어쓰지 않음 — 해당 태스크의 필드만 업데이트
- progress_log는 append-only (최신이 위)
- repos의 commits는 주요 커밋만 (모든 커밋 나열 금지)
- 민감 정보(API 키, 비밀번호)는 summary에 포함 금지
