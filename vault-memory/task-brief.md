# vault-memory:task-brief

> 전체 프로젝트/태스크 현황을 빠르게 브리핑한다.

## 트리거

- "태스크 현황", "뭐 하고 있었지", "task status"
- "프로젝트 현황", "진행 상황"
- 세션 시작 시 resume과 함께 자동 실행 가능

## 파라미터

| 형식 | 예시 | 동작 |
|------|------|------|
| (없음) | `task-brief` | 전체 활성 프로젝트의 in_progress + blocked 태스크 |
| 프로젝트명 | `task-brief ronik` | 해당 프로젝트만 상세 |
| 태스크ID | `task-brief t-ronik-001` | 해당 태스크 상세 + progress_log |

## 워크플로우

### 1. 프로젝트 스캔

`memory/projects/*/project.yml`에서 `status: active` 프로젝트 목록 수집.

### 2. 태스크 수집

각 프로젝트의 `tasks.yml`에서:
- `status: in_progress` — 진행 중
- `status: blocked` — 차단됨
- `status: todo` + `deadline` 임박 (3일 이내) — 마감 주의

### 3. 브리핑 출력

```markdown
## 태스크 브리핑

### work--ronik (로닉)
| ID | 태스크 | 상태 | 담당 | 마감 | 마지막 작업 |
|----|--------|------|------|------|------------|
| t-ronik-001 | 캘리봇 기획 재정리 | 🔄 진행중 | daye | 2/14 | 2/11 claude-code |
| t-ronik-004 | PM봇 태스크 형식 검증 | 🔄 진행중 | daye | 2/12 | 2/11 openclaw |

### work--mingming-ai (밍밍이)
| ID | 태스크 | 상태 | 담당 | 마감 | 마지막 작업 |
|----|--------|------|------|------|------------|
| t-ming-001 | 로컬 YAML 프로젝트 관리 | 🔄 진행중 | mingming | 2/14 | 2/11 claude-code |
| t-ming-005 | goal-planner 크론 연동 | ⏳ todo | mingming | 2/12 | — |

### ⚠️ 마감 임박
- **t-ronik-004** (PM봇 검증): 내일 마감, subtask 1/2 완료
- **t-ming-005** (goal-planner 크론): 내일 마감, 미시작
```

### 4. 상세 모드 (프로젝트/태스크 지정 시)

```markdown
## t-ronik-001: 캘리봇 기획 재정리

**상태:** 🔄 진행중 | **담당:** daye | **마감:** 2026-02-14

### Subtasks
- [x] 현재 캘리 프로세스 as-is 정리
- [ ] 봇 적용 시나리오 to-be 설계
- [ ] 입출력 데이터 포맷 정의

### 최근 진행 (progress_log)
| 날짜 | 플랫폼 | 내용 |
|------|--------|------|
| 2/11 | claude-code | as-is 정리 완료, 3단계 수동 프로세스 파악 |
| 2/11 | openclaw | to-be 설계 초안, 3가지 시나리오 제안 |

### Repo
- **ronik-inc/cali-bot** → `feature/t-ronik-001`
- PR #42 (open)
```

### 5. 크로스 플랫폼 컨텍스트

마지막 작업이 다른 플랫폼이었으면 하이라이트:
```markdown
> 💡 t-ronik-001의 마지막 작업은 **openclaw**에서 수행됨.
> to-be 설계 초안이 있으니 확인 후 이어서 작업하세요.
> `vault-memory:resume ronik` 으로 상세 컨텍스트 확인 가능.
```

## 주의사항

- tasks.yml을 읽기만 함 (수정 안 함)
- 완료된 태스크(done)는 기본 표시 안 함 (옵션으로 `--all`)
- 아카이브된 프로젝트는 제외
