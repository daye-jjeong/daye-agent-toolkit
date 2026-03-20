# Multi-User Routing Design

> participants 기반 크론/태스크 라우팅 — dy-minions-squad 확장

**Date**: 2026-03-20
**Status**: Draft
**Scope**: dy-minions-squad (primary), daye-agent-toolkit (cron.json 수정)

## Problem

현재 시스템은 단일 사용자(daye) 기준으로 설계되어 있다.

- 크론 산출물 수신자가 `instructions`에 "daye에게 전달하세요"로 하드코딩
- 태스크에 `created_by`(등록 주체)만 있고, 실제 요청자(requester) 개념 없음
- `config.minions.owner`가 단수 — 멀티 human 불가
- Telegram `chat_id` → participant 역방향 매핑 없음

멀티유저 협업 시 크론 산출물과 태스크 결과를 사용자별/채널별로 라우팅해야 한다.

## Decision: Central Routing via Participants

기존 participant + delivery 인프라를 확장한다. 새 시스템을 만들지 않는다.

핵심 원칙:
- **participant가 라우팅의 단위** — 모든 수신자는 participant ID로 표현
- **delivery가 전송의 단위** — 기존 라이프사이클(created → sent → replied → closed) 유지
- **크론과 태스크 모두 동일한 라우팅 경로** 사용

## Existing Infrastructure (변경 없음)

| 컴포넌트 | 위치 | 역할 |
|----------|------|------|
| `participants` 테이블 | `src/core/db` | id, type, channel, channel_target |
| `deliveries` 테이블 | `src/core/db` | 전체 전송 라이프사이클 + events 감사 로그 |
| `createDelivery()` | `src/core/workspace/deliveries.ts` | recipientParticipantId → 채널 resolve → 전송 |
| `sendDelivery()` | `src/core/workspace/deliveries.ts` | openclaw message send 실행 |
| `upsertParticipant()` | `src/core/workspace/participants.ts` | participant CRUD |

## Changes

### 1. Task Schema: `requester` + `notify_participants`

**File**: `src/core/schemas/tasks.ts`

```typescript
// 추가 필드
requester: z.string().optional(),
notify_participants: z.array(z.string()).default([]),
```

| 필드 | 용도 |
|------|------|
| `created_by` | 태스크를 시스템에 등록한 주체 (에이전트 포함, 기존 유지) |
| `requester` | 실제 요청자 (human participant ID) |
| `notify_participants` | 결과 수신자 목록. 기본값 = `[requester]` |

태스크 완료 시:
```
task DONE → notify_participants 순회 → createDelivery(각 participant) → 기존 delivery 파이프라인
```

### 2. Cron Schema: `recipients`

**File**: `src/core/schemas/cron.ts`

```typescript
// 추가 필드
recipients: z.array(z.string()).optional(),
```

크론 실행기가 `recipients`를 읽고 각 participant에 대해 delivery를 생성한다.
`recipients`가 없으면 기존 동작 유지 (owner에게 전달).

**cron.json 예시** (daye-agent-toolkit 쪽):
```jsonc
{
  "name": "daily-newspaper",
  "schedule": "0 8 * * *",
  "target": "daily-newspaper",
  "instructions": "news-brief 스킬의 'Quick Usage' 절차를 따르세요.",
  "recipients": ["daye", "teammate_a"]
}
```

`instructions`에서 "daye에게 전달하세요" 같은 하드코딩을 제거한다.

### 3. Participant: Telegram 역방향 매핑

**File**: `src/core/workspace/participants.ts`

```typescript
export async function findParticipantByChannelTarget(
  channel: string,
  target: string,
): Promise<Participant | null> {
  const db = getDb();
  const row = db.prepare(
    "SELECT * FROM participants WHERE channel = ? AND channel_target = ? AND active = 1"
  ).get(channel, target);
  return row ? rowToParticipant(row) : null;
}
```

Telegram에서 요청이 오면:
```
chat_id 수신 → findParticipantByChannelTarget("telegram", chat_id)
  → participant ID → task.requester에 자동 설정
```

함수명을 `findParticipantByChatId`가 아닌 `findParticipantByChannelTarget`으로 일반화.
Slack 등 다른 채널에서도 동일하게 사용 가능.

### 4. Config: 멀티 Human

**File**: `src/core/schemas/config.ts`

```typescript
minions: z.object({
  orchestrator: z.string().min(1),
  agents: z.array(z.string().min(1)),
  owner: z.string().min(1).default("daye"),
  humans: z.array(z.string()).default([]),  // 추가
}),
```

`syncParticipantsFromConfig()`에서 `humans` 배열도 순회하여 participant로 등록.
`owner`는 primary human으로 유지 (하위호환).

### 5. 동적 수신자 변경

**File**: `src/core/workspace/tasks.ts`

```typescript
export function addTaskNotifyParticipant(ticketId: string, participantId: string): void {
  const task = loadTask(ticketId);
  if (!task) throw new Error(`Task not found: ${ticketId}`);
  const current = task.notify_participants ?? [];
  if (!current.includes(participantId)) {
    updateTask(ticketId, { notify_participants: [...current, participantId] });
  }
}
```

에이전트가 대화 중 "A한테도 보내줘"를 인식하면 이 함수를 호출하여 수신자를 추가한다.

### 6. Task 완료 시 Delivery 생성

**File**: `src/core/workspace/tasks.ts` (기존 상태 전이 로직에 추가)

태스크가 DONE 상태로 전이될 때:
1. `notify_participants`가 비어있으면 → `[requester]` fallback
2. `requester`도 없으면 → `config.minions.owner` fallback
3. 각 participant에 대해 `createDelivery()` 호출
4. delivery의 `source_message_id`는 태스크의 최종 thread message

### 7. Cron 실행기에서 Recipients → Delivery 연결

**File**: `src/core/workspace/cron-registry.ts` 또는 실행기 모듈

크론 실행 완료 시:
1. `cron.recipients`가 있으면 → 각 participant에 대해 `createDelivery()`
2. `cron.recipients`가 없으면 → `config.minions.owner`에게 전달 (기존 동작)

## Data Flow

```
[Telegram 요청]                    [Cron 실행 (공유서버)]
      │                                  │
 chat_id → findParticipantBy...     cron.recipients 읽기
      │                                  │
 task.requester = participant_id    에이전트 작업 실행
 task.notify_participants = [자신]       │
      │                             산출물 thread message 생성
 에이전트 작업                           │
      │                             recipients 순회
 (동적: "B한테도 보내줘")                │
      │                             createDelivery(각 participant)
 notify_participants += B                │
      │                             sendDelivery() → 각 채널
 task DONE
      │
 notify_participants 순회
      │
 createDelivery(각 participant)
      │
 sendDelivery() → 각 채널
```

## Migration

1. **하위호환**: 모든 새 필드는 optional/default — 기존 태스크/크론이 깨지지 않음
2. **cron.json 수정** (daye-agent-toolkit): `recipients` 추가, `instructions`에서 수신자 하드코딩 제거
3. **participant 등록**: 새 human 사용자는 `config.json`의 `humans` 배열에 추가 후 `syncParticipantsFromConfig()` 실행
4. **participant channel 설정**: `minions participant update <id> --channel telegram --target <chat_id>` 등으로 채널 매핑

## Out of Scope

- 채널 그룹/토픽 전송 (현재 participant는 1:1 채널만, 추후 확장)
- 수신자 권한 관리 (누가 어떤 크론을 구독 가능한지)
- 크론 구독/해지 UI
- 다중 채널 per participant (현재 channel 1개만)

## Affected Repos

| 레포 | 변경 |
|------|------|
| **dy-minions-squad** | schemas, participants, tasks, cron-registry, config — 핵심 구현 전부 |
| **daye-agent-toolkit** | cron.json 파일들에 `recipients` 추가, instructions 하드코딩 제거 |
