# vault-memory:task-create

> 새 태스크를 `t-{project}-NNN.md` 파일로 생성한다. description 필수.

**태스크 템플릿**: `memory/.obsidian/templates/task-template.md` 참조

## 트리거

- "태스크 추가", "새 작업 만들어", "task 생성"
- "t-xxx-nnn 만들어줘"
- goal-planner 플래닝 세션에서 태스크 도출 시

## 워크플로우

### 1. 프로젝트 선택

프로젝트가 명시되지 않으면:
1. `memory/projects/*/_project.md`에서 `status: active` 프로젝트 목록 표시
2. 사용자가 선택

프로젝트가 명시되면:
1. 해당 프로젝트 디렉토리 존재 확인
2. 없으면 디렉토리 + `_project.md` 생성

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
| `linked_goals` | 연결된 목표 (`[[2026-02]]` 등) |
| `repos` | 관련 코드 저장소 |
| `branch` | 작업 브랜치명 |

### 4. description 작성 가이드

사용자에게 다음 3가지를 물어본다:

```
1. 무엇을 하나요? (구체적 행동)
2. 왜 필요한가요? (배경/동기)
3. 어떻게 되면 끝인가요? (완료 기준)
```

조합하여 `## 컨텍스트` 섹션 생성:

```markdown
## 컨텍스트
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
- 기존 `t-*.md` 파일에서 최대 번호 + 1

### 6. t-*.md 파일 생성

프로젝트 디렉토리에 개별 파일 생성:

```markdown
---
id: t-ronik-007
title: "새 태스크 제목"
status: todo
priority: high
owner: daye
created: 2026-02-12
updated_by: claude-code
updated_at: 2026-02-12T15:30
deadline: 2026-02-20
---

## 컨텍스트
무엇을, 왜, 완료 기준.

## 서브태스크
- [ ] 서브태스크 1
- [ ] 서브태스크 2

## 코드 변경

## 진행 로그
- 2026-02-12 (claude-code): 태스크 생성

## 산출물
```

### 7. 배치 생성

여러 태스크를 한 번에 만들 때:
1. 프로젝트 + 태스크 목록을 사용자에게 받기
2. 각각에 대해 간단한 description 받기 (한 줄이라도)
3. 한 번에 t-*.md 파일들 생성
4. 결과 테이블 출력

## 주의사항

- **description 없이 생성 금지** — title만으로는 나중에 맥락을 잃음
- 중복 ID 방지 (기존 t-*.md 파일 확인 후 채번)
- `updated_by: claude-code` + `updated_at` frontmatter 갱신 (VAULT.md 규칙)
