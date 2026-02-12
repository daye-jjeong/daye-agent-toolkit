# vault-memory:goal-create

> 목표 YAML 파일을 `memory/goals/`에 생성한다.

**YAML 포맷**: goal-planner 스킬의 `references/yaml-formats.md` 참조
**계획 방법론**: goal-planner 스킬의 SKILL.md 참조

## 트리거

- goal-planner 플래닝 세션 결과를 파일로 저장할 때
- "목표 파일 만들어줘", "이번주 목표 저장"
- 크론 자동 생성 (`create_goal.py daily --auto`)

## 파일 경로 규칙

| 계층 | 파일명 | 예시 |
|------|--------|------|
| 월간 | `memory/goals/monthly/YYYY-MM.yml` | `2026-02.yml` |
| 주간 | `memory/goals/weekly/YYYY-Www.yml` | `2026-W07.yml` |
| 일간 | `memory/goals/daily/YYYY-MM-DD.yml` | `2026-02-12.yml` |

## 워크플로우

### 1. 계층 + 기간 결정

명시되지 않으면:
- 월초(1-3일) → 월간 제안
- 월요일 → 주간 제안
- 그 외 → 일간 제안

### 2. 상위 목표 읽기

| 생성 대상 | 참조 |
|-----------|------|
| 월간 | 이전 월간 회고, 프로젝트 현황 |
| 주간 | 현재 월간 목표 (`goals/monthly/`) |
| 일간 | 현재 주간 목표 (`goals/weekly/`) + 활성 태스크 (`projects/*/tasks.yml`) |

### 3. 필수 필드

#### 월간
```yaml
month: "2026-02"
status: active
theme: "테마 한 줄"
goals:
  - title: 목표 제목
    project: work--ronik          # projects/ 폴더명
    priority: high
    key_results:
      - description: KR 설명
        target: "100%"
        current: "0%"
```

#### 주간
```yaml
week: "2026-W07"
period: "2026-02-09 ~ 2026-02-15"
status: active
goals:
  - title: 주간 목표
    project: work--ronik
    priority: high
    status: todo
    key_results:
      - KR 항목
```

#### 일간
```yaml
date: "2026-02-12"
day_of_week: "수"
status: active
top3:
  - title: 핵심 목표
    project: work--ronik
    status: todo
checklist:
  - task: 할 일
    done: false
```

### 4. 태스크 ↔ 목표 연결

목표 생성 시 관련 태스크가 있으면:
- 목표의 `project` 필드로 프로젝트 연결
- 해당 tasks.yml의 태스크에 `linked_goals` 필드 추가 제안

```yaml
# goals/weekly/2026-W07.yml
goals:
  - title: 캘리봇 기획 완성
    project: work--ronik

# projects/work/ronik/tasks.yml
- id: t-ronik-001
  linked_goals:
    - "[[2026-W07]]"
```

### 5. 기존 파일 처리

- 같은 기간 파일이 이미 있으면 → **덮어쓰지 않고** 차이점 표시 + 사용자 확인
- `status: active`인 기존 파일이 있으면 → 업데이트로 전환 (goal-update)

### 6. 회고 섹션

모든 계층에 빈 `retrospective:` 섹션 포함. 기간 종료 후 채움.

## 주의사항

- goal-planner가 "뭘 목표로 할지" 결정 → 이 커맨드가 "파일로 기록"
- 목표 내용 자체를 이 커맨드가 결정하지 않음 — 입력을 받아서 기록만
- `updated_by` + `updated_at` frontmatter 갱신
- goals/ 하위 디렉토리 없으면 자동 생성 (`daily/`, `weekly/`, `monthly/`)
