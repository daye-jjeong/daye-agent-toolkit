# QA Patrol Domain 6: 메타 로그 완결성

## 배경

dy-minions-squad는 크론/태스크/배달의 실행 기록을 여러 테이블에 분산 저장한다. 기존 qa-patrol은 "시스템이 동작했는가"(Domain 1-5)를 검증하지만, **"기록이 정확하게 남았는가"**는 검증하지 않는다.

### 문제

- `cron_runs.status='completed'`인데 `result_data`가 null — 에이전트가 `--result-data`를 안 넘겼거나 큐 fallback으로 완료됨
- 태스크 상태가 바뀌었는데 `thread_messages`에 이벤트가 안 남음 — status UPDATE와 이벤트 쓰기가 별도 호출이라 후자가 실패하면 삼켜짐
- `deliveries.status='sent'`인데 `delivery_events`에 `type='sent'` 행이 없음 — 같은 패턴
- `jobs` ↔ `cron_runs` ↔ `deliveries` 간 FK 체인이 끊김 — 디버깅 시 추적 불가

### 원인

대부분의 쓰기 경로에서 **상태 변경(UPDATE)과 감사 로그(INSERT)가 같은 트랜잭션이 아니다.** 감사 로그 쓰기가 try-catch로 감싸져 있어 실패해도 console.warn만 남기고 넘어간다. 이 구조적 취약점을 코드 수정 없이 사후 검증으로 보완한다.

## 설계 원칙

1. **Domain 6은 "기록의 정합성"만 본다.** "시스템이 동작했는가"는 기존 Domain 1-5의 영역.
2. **lookback은 12시간.** 기본 패트롤이 10:00/20:00에 돌므로, 이전 패트롤 이후 구간을 커버.
3. **디버깅 추적 체인을 보장한다.** 크론 실행 → job → 세션 → 배달까지 FK로 연결되어야 함.

## 변경 범위

| 대상 | 변경 |
|------|------|
| `core-skills/qa-patrol/references/checks.md` | Domain 6 섹션 추가 |
| `core-skills/qa-patrol/SKILL.md` | Domain 6 요약 한 줄 추가 |

기존 Domain 1-5, Deep patrol은 변경 없음.

---

## Domain 6: 메타 로그 완결성

### 데이터 소스

```
minions cron run list --format json
minions task list --format json --status IN_PROGRESS,REVIEW_READY,DONE
minions delivery list --format json
```

추가로 DB 직접 조회가 필요한 체크는 `minions db query` 또는 해당 CLI 서브커맨드 사용.

### 6-1. 크론 로그 완결성

| ID | 체크 | 조건 | 심각도 | 근거 |
|----|------|------|--------|------|
| 6-1a | result_data 누락 | `cron_runs.status='completed'` AND `result_data IS NULL` | P2 | 에이전트 프롬프트에서 `--result-data` 필수 안내. null이면 에이전트 미준수 또는 큐 fallback. |
| 6-1b | 배달 미처리 | `status='completed'` AND `crons.recipients` 비어있지 않음 AND `delivered_at IS NULL` AND `skipped_at IS NULL` AND `completed_at < now - 1h` | P2 | 완료 후 1시간 내 배달 또는 skip이 없으면 배달 파이프라인 정체. |
| 6-1c | 실행 메타 부분 누락 | `status='completed'` AND (`session_id IS NULL` OR `duration_ms IS NULL`) | P3 | 디버깅 시 세션/소요시간 추적 불가. |

#### 6-1a 원인 추정 로직

| summary | result_data | 추정 원인 |
|---------|-------------|-----------|
| NULL | NULL | 큐 fallback 완료 (에이전트가 `cron run complete` 미호출) |
| 있음 | NULL | 에이전트가 `--result-data` 생략 |

보고 시 추정 원인을 함께 표시.

### 6-2. 태스크 로그 완결성

| ID | 체크 | 조건 | 심각도 | 근거 |
|----|------|------|--------|------|
| 6-2a | 상태 이벤트 누락 | `tasks.status` IN (`DONE`, `IN_PROGRESS`, `REVIEW_READY`) AND 해당 상태로의 전이에 대한 `thread_messages`(tag=`status_change`) 없음 | P2 | `saveDirtyTasks`와 `logStatusEvent`가 별도 호출. 후자 실패 시 삼켜짐. |
| 6-2b | 부모 태스크 started_at 누락 | `status` IN (`IN_PROGRESS`, `REVIEW_READY`, `DONE`) AND `started_at IS NULL` | P3 | `syncParentStatus`가 부모를 IN_PROGRESS로 올릴 때 started_at을 안 건드림. depth > 0인 부모 태스크에서 발생. |
| 6-2c | 완료 태스크 session_id 누락 | `status='DONE'` AND `session_id IS NULL` | P2 | `updateTaskExecutionMeta`가 사후에 채우는데, 호출 안 되면 세션 추적 불가. |
| 6-2d | 성공인데 work_report 없음 | `status='DONE'` AND `outcome='success'` AND `work_report IS NULL` | P3 | `force: true` 또는 `batchChildren` 경로에서 발생 가능. 의도적일 수 있어 P3. |

### 6-3. 배달 이벤트 완결성

| ID | 체크 | 조건 | 심각도 | 근거 |
|----|------|------|--------|------|
| 6-3a | 이벤트 체인 끊김 | `deliveries.status='sent'` AND `delivery_events`에 `type='sent'` 행이 없음 | P2 | `updateDeliveryStatus`와 `appendDeliveryEvent`가 별도 호출. 후자 실패 시 삼켜짐. |
| 6-3b | 장기 pending | `deliveries.status='pending_review'` AND `created_at < now - 3h` AND 현재 시각이 08:00~23:00 | P2 | `reviewed` 모드 배달은 오케스트레이터 wake에 의존. 야간(23:00~08:00)은 정상 지연이므로 제외. |
| 6-3c | 실패 방치 | `deliveries.status='failed'` AND 마지막 `delivery_events.type='send_failed'`의 `created_at < now - 2h` AND 이후 `retry_requested` 이벤트 없음 | P3 | 자동 재시도 메커니즘 없음. 오케스트레이터가 처리 안 하면 영구 방치. |

### 6-4. 크로스 테이블 추적 체인

| ID | 체크 | 조건 | 심각도 | 근거 |
|----|------|------|--------|------|
| 6-4a | job ↔ cron_run 불일치 | `jobs.status` IN (`completed`, `failed`) AND 연결된 `cron_runs.status='running'` (job_id FK로 조인) | P2 | 큐 fallback(`reapOrphanedCronRuns`)이 실패하면 cron_run이 영원히 running. |
| 6-4b | cron_run.job_id 누락 | `cron_runs.status='completed'` AND `job_id IS NULL` | P2 | job을 거치지 않고 완료된 크론. 추적 체인 첫 링크 끊김. |
| 6-4c | session_id 불일치 | `cron_runs.session_id` AND `jobs.spawn_session_id` 둘 다 non-null인데 값이 다름 (job_id FK로 조인) | P3 | 두 곳에 기록된 세션 ID가 다르면 어느 쪽이 맞는지 알 수 없음. |
| 6-4d | thread_messages.job_id 누락 | `thread_messages.tags` LIKE `%status_change%` AND `job_id IS NULL` | P3 | 태스크 이벤트를 job으로 역추적 불가. |
| 6-4e | deliveries.job_id 누락 | `deliveries.status='sent'` AND `job_id IS NULL` | P3 | 배달을 실행 잡으로 역추적 불가. |
| 6-4f | current_tasks stale | `current_tasks.task_id`가 가리키는 `tasks.status` IN (`DONE`, `ARCHIVED`) | P2 | 정리 안 되면 해당 에이전트의 다음 태스크 시작 불가. |

### 보고 형식

기존 qa-patrol 보고 형식을 따른다:

```
## Domain 6: 메타 로그 완결성

[P2] cron result_data 누락 (2건)
- bob/qa-patrol: 완료 2026-03-30 14:02, 원인 추정: agent 누락 (summary 있음)
- phil/compound-review: 완료 2026-03-30 10:15, 원인 추정: queue-fallback (summary null)

[P2] 태스크 상태 이벤트 누락 (1건)
- t-bob-cleanup-003: DONE인데 status_change thread_messages 없음

[P3] cron 실행 메타 부분 누락 (1건)
- phil/meditation: session_id null

이상 없음: 6-1b, 6-2b, 6-2c, 6-2d, 6-3a, 6-3b, 6-3c, 6-4a~f
```

### Lookback 및 실행 주기

- **Lookback**: 12시간 (이전 패트롤 이후 구간)
- **실행 주기**: 기존 기본 패트롤과 동일 (10:00, 20:00 KST)
- **별도 크론 불필요**: checks.md에 Domain 6을 추가하면 기존 패트롤이 자동으로 포함

### 트렌드 연동

기존 trend.md 규칙을 그대로 적용:
- 같은 target + 같은 체크 ID가 2회 연속 → `[RECURRING]`, P 레벨 1단계 상승
- 3회 연속 → `[CHRONIC]`, 구조 개선 제안 필수
- 이전에 감지됐다가 사라짐 → `[RESOLVED]`
