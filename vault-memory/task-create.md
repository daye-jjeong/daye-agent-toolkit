# vault-memory:task-create

> 새 태스크를 tasks.yml에 생성한다. description 필수.

**태스크 템플릿**: `memory/projects/config/task-template.yml` 참조

## 트리거

- "태스크 추가", "새 작업 만들어", "task 생성"
- "t-xxx-nnn 만들어줘"
- goal-planner 플래닝 세션에서 태스크 도출 시

## 워크플로우

### 1. 프로젝트 선택

프로젝트가 명시되지 않으면:
1. `memory/projects/*/project.yml`에서 `status: active` 프로젝트 목록 표시
2. 사용자가 선택

프로젝트가 명시되면:
1. 해당 프로젝트의 `tasks.yml` 존재 확인
2. 없으면 `tasks.yml` 생성 (description 포함)

### 2. 필수 정보 수집

| 필드 | 필수 | 수집 방법 |
|------|------|-----------|
| `id` | Y | 자동 채번 (프로젝트 내 최대 번호 + 1) |
| `title` | Y | 사용자 입력 |
| `description` | **Y** | 사용자 입력 — 무엇을/왜/완료 기준 |
| `status` | Y | 기본값 `todo` |
| `priority` | Y | 사용자 선택 (high/medium/low) |
| `owner` | Y | 사용자 지정 또는 기본값 |
| `created` | Y | 오늘 날짜 (자동) |
| `deadline` | N | 사용자 입력 |

### 3. 선택 정보

| 필드 | 설명 |
|------|------|
| `subtasks` | 하위 작업 분해 (title + status: todo) |
| `tags` | 분류 태그 |
| `linked_goals` | 연결된 목표 (`[[2026-02]]` 등) |
| `links` | 관련 문서/URL |

### 4. description 작성 가이드

사용자에게 다음 3가지를 물어본다:

```
1. 무엇을 하나요? (구체적 행동)
2. 왜 필요한가요? (배경/동기)
3. 어떻게 되면 끝인가요? (완료 기준)
```

조합하여 description 생성:

```yaml
description: |
  현재 수동 캘리브레이션 프로세스를 분석하고 AI 봇 자동화 시나리오를 설계한다.
  로닉 캘리 작업이 반복적이고 시간 소모가 크기 때문.
  완료 기준: as-is 문서 + to-be 시나리오 3가지 + 입출력 포맷 정의.
```

사용자가 간단히 한 줄만 줘도 OK — 최소한 "이 태스크가 뭔지"는 있어야 한다.

### 5. ID 채번 규칙

```
t-{project약어}-{NNN}
```

- 프로젝트 약어: ronik, ming, career, health, invest, asset
- NNN: 해당 프로젝트 내 순번 (001, 002, ...)
- 기존 tasks.yml에서 최대 번호 + 1

### 6. tasks.yml에 추가

기존 tasks.yml의 `tasks:` 배열 끝에 append.

```yaml
tasks:
  # ... 기존 태스크들
  - id: t-ronik-007
    title: 새 태스크 제목
    description: |
      무엇을, 왜, 완료 기준.
    status: todo
    priority: high
    owner: daye
    created: 2026-02-12
    deadline: 2026-02-20
```

### 7. 배치 생성

여러 태스크를 한 번에 만들 때:
1. 프로젝트 + 태스크 목록을 사용자에게 받기
2. 각각에 대해 간단한 description 받기 (한 줄이라도)
3. 한 번에 tasks.yml에 추가
4. 결과 테이블 출력

## 주의사항

- **description 없이 생성 금지** — title만으로는 나중에 맥락을 잃음
- tasks.yml 전체를 덮어쓰지 않음 — append only
- 중복 ID 방지 (기존 ID 확인 후 채번)
- `updated_by: claude-code` + `updated_at` frontmatter 갱신 (VAULT.md 규칙)
