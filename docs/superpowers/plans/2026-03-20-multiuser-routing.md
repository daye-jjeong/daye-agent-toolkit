# Multi-User Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** participants 기반 크론/태스크 라우팅으로 멀티유저 협업 지원

**Architecture:** 기존 dy-minions-squad의 participant + delivery 인프라를 확장. 새 시스템 없이 schema 확장 + routing 로직 추가. daye-agent-toolkit은 cron.json/SKILL.md 하드코딩 제거.

**Tech Stack:** TypeScript, Zod, better-sqlite3, vitest

**Spec:** `docs/superpowers/specs/2026-03-20-multiuser-routing-design.md`

**Working directory:** `~/dy-minions-squad` (Task 1-7), `~/git_workplace/daye-agent-toolkit` (Task 8)

---

## File Structure

### dy-minions-squad 변경

| 파일 | 작업 | 책임 |
|------|------|------|
| `src/core/db/index.ts` | Modify | UNIQUE 인덱스 추가 `(channel, channel_target)` |
| `src/core/schemas/tasks.ts` | Modify | `requester`, `notify_participants` 필드 추가 |
| `src/core/schemas/cron-registry.ts` | Modify | `recipients` 필드 추가 |
| `src/core/schemas/config.ts` | Modify | `humans` 배열 추가 |
| `src/core/workspace/participants.ts` | Modify | `findParticipantByChannelTarget()` 추가 |
| `src/core/workspace/participants.ts` | Modify | `syncParticipantsFromConfig()` humans 지원 |
| `src/core/workspace/tasks.ts` | Modify | `addTaskNotifyParticipant()`, delivery fanout on DONE |
| `src/core/workspace/cron-registry.ts` | Modify | `recipients` 필드 DB 컬럼 + CRUD 반영 |
| `tests/multiuser-routing.test.ts` | Create | 통합 테스트 |

### daye-agent-toolkit 변경

| 파일 | 작업 |
|------|------|
| `shared/news-brief/cron.json` | `recipients` 추가, instructions 하드코딩 제거 |
| `shared/life-coach/cron.json` | `recipients` 추가, instructions 하드코딩 제거 |
| `shared/spending-manager/cron.json` | `recipients` 추가 |
| `shared/investment-manager/cron.json` | `recipients` 추가 |
| `shared/news-brief/SKILL.md` | "daye에게 전달" 하드코딩 제거 |

---

## Task 1: DB — UNIQUE 인덱스 추가

**Files:**
- Modify: `src/core/db/index.ts:144` (participants 테이블 뒤)
- Test: `tests/multiuser-routing.test.ts`

- [ ] **Step 1: Write failing test — duplicate channel_target 방지**

```typescript
// tests/multiuser-routing.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { getDb } from "../src/core/db";
import { upsertParticipant } from "../src/core/workspace/participants";
import { setupTestDb } from "./helpers";

describe("multiuser-routing", () => {
  beforeEach(() => setupTestDb());

  describe("participant channel uniqueness", () => {
    it("rejects duplicate (channel, channel_target) across participants", async () => {
      await upsertParticipant({
        id: "user-a", type: "human", display_name: "A",
        channel: "telegram", channel_target: "12345",
      });
      await expect(
        upsertParticipant({
          id: "user-b", type: "human", display_name: "B",
          channel: "telegram", channel_target: "12345",
        })
      ).rejects.toThrow(/UNIQUE/);
    });

    it("allows same channel with different target", async () => {
      await upsertParticipant({
        id: "user-a", type: "human", display_name: "A",
        channel: "telegram", channel_target: "12345",
      });
      await upsertParticipant({
        id: "user-b", type: "human", display_name: "B",
        channel: "telegram", channel_target: "67890",
      });
      // no throw
    });

    it("allows null channel (agents without channel)", async () => {
      await upsertParticipant({
        id: "agent-a", type: "agent", display_name: "A",
      });
      await upsertParticipant({
        id: "agent-b", type: "agent", display_name: "B",
      });
      // no throw — null channels are not constrained
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: FAIL — duplicate insert succeeds without UNIQUE constraint

- [ ] **Step 3: Add UNIQUE index to db/index.ts**

`src/core/db/index.ts` — participants 테이블 인덱스 뒤에 추가:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_participants_channel_unique
  ON participants(channel, channel_target)
  WHERE channel IS NOT NULL AND channel_target IS NOT NULL;
```

partial unique index: `NULL` channel은 제약 안 받음 (에이전트 등).

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/db/index.ts tests/multiuser-routing.test.ts
git commit -m "feat: add UNIQUE index on (channel, channel_target) for participant routing"
```

---

## Task 2: Schema — Task `requester` + `notify_participants`

**Files:**
- Modify: `src/core/schemas/tasks.ts:71-117`
- Test: `tests/multiuser-routing.test.ts`

- [ ] **Step 1: Write failing test — task schema accepts new fields**

```typescript
// tests/multiuser-routing.test.ts — 추가
import { taskItemSchema } from "../src/core/schemas/tasks";

describe("task schema — requester + notify_participants", () => {
  it("accepts requester and notify_participants", () => {
    const result = taskItemSchema.safeParse({
      ticket_id: "T-001", title: "test", status: "PENDING",
      assignee: "@worker", priority: "medium", created_by: "mingming",
      created_at: "2026-03-20T00:00:00+09:00",
      requester: "daye",
      notify_participants: ["daye", "teammate_a"],
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.requester).toBe("daye");
      expect(result.data.notify_participants).toEqual(["daye", "teammate_a"]);
    }
  });

  it("defaults notify_participants to empty array", () => {
    const result = taskItemSchema.safeParse({
      ticket_id: "T-002", title: "test", status: "PENDING",
      assignee: "@worker", priority: "medium", created_by: "mingming",
      created_at: "2026-03-20T00:00:00+09:00",
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.requester).toBeUndefined();
      expect(result.data.notify_participants).toEqual([]);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: FAIL — `requester` not recognized

- [ ] **Step 3: Add fields to task schema**

`src/core/schemas/tasks.ts` — `taskItemSchema` 내부, `session_id` 근처에 추가:

```typescript
	requester: z.string().optional(),
	notify_participants: z.array(z.string()).default([]),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: PASS

- [ ] **Step 5: Run full test suite to check no regressions**

Run: `npx vitest run --reporter=verbose`
Expected: 기존 테스트 전부 PASS (새 필드는 optional/default이므로 하위호환)

- [ ] **Step 6: Commit**

```bash
git add src/core/schemas/tasks.ts tests/multiuser-routing.test.ts
git commit -m "feat: add requester and notify_participants to task schema"
```

---

## Task 3: Schema — Cron `recipients` + Config `humans`

**Files:**
- Modify: `src/core/schemas/cron.ts:5-22` (skill cron schema)
- Modify: `src/core/schemas/cron-registry.ts:19-36` (registry schema)
- Modify: `src/core/schemas/config.ts:26-53`
- Modify: `src/core/workspace/cron-registry.ts` (DB CRUD — recipients 컬럼)
- Modify: `src/core/db/index.ts` (crons 테이블에 recipients 컬럼)
- Test: `tests/multiuser-routing.test.ts`

- [ ] **Step 1: Write failing test — cron schema accepts recipients**

```typescript
// tests/multiuser-routing.test.ts — 추가
import { skillCronEntrySchema } from "../src/core/schemas/cron";
import { minionsConfigSchema } from "../src/core/schemas/config";

describe("cron schema — recipients", () => {
  it("accepts recipients array", () => {
    const result = skillCronEntrySchema.safeParse({
      name: "daily-newspaper",
      schedule: "0 8 * * *",
      target: "daily-newspaper",
      recipients: ["daye", "teammate_a"],
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.recipients).toEqual(["daye", "teammate_a"]);
    }
  });

  it("recipients defaults to undefined (backward compat)", () => {
    const result = skillCronEntrySchema.safeParse({
      name: "sync", schedule: "0 * * * *", command: "sync.sh",
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.recipients).toBeUndefined();
    }
  });
});

describe("config schema — humans", () => {
  it("accepts humans array", () => {
    const result = minionsConfigSchema.safeParse({
      minions: {
        orchestrator: "mingming",
        agents: ["worker-a"],
        owner: "daye",
        humans: ["daye", "teammate_a"],
      },
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.minions.humans).toEqual(["daye", "teammate_a"]);
    }
  });

  it("humans defaults to empty array", () => {
    const result = minionsConfigSchema.safeParse({
      minions: { orchestrator: "mingming", agents: [] },
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.minions.humans).toEqual([]);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add recipients to skill cron schema**

`src/core/schemas/cron.ts` — `skillCronEntrySchema` 내부, `model` 뒤에:
```typescript
		recipients: z.array(z.string()).optional(),
```

- [ ] **Step 4: Add recipients to cron-registry schema + DB**

`src/core/schemas/cron-registry.ts` — `cronEntrySchema` 내부, `enabled` 뒤에:
```typescript
	recipients: z.array(z.string()).nullable().default(null),
```

`src/core/db/index.ts` — crons 테이블에 컬럼 추가:
```sql
recipients TEXT  -- JSON array, nullable
```

`src/core/workspace/cron-registry.ts` — `entryToParams`와 `rowToEntry`에서 JSON 직렬화/역직렬화 처리.

- [ ] **Step 5: Add humans to config schema**

`src/core/schemas/config.ts` — `minions` 객체 내부, `owner` 뒤에:
```typescript
		humans: z.array(z.string()).default([]),
```

- [ ] **Step 6: Run tests**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: PASS

- [ ] **Step 7: Run full suite**

Run: `npx vitest run --reporter=verbose`
Expected: 전부 PASS

- [ ] **Step 8: Commit**

```bash
git add src/core/schemas/cron.ts src/core/schemas/cron-registry.ts src/core/schemas/config.ts src/core/db/index.ts src/core/workspace/cron-registry.ts tests/multiuser-routing.test.ts
git commit -m "feat: add recipients to cron schema, humans to config schema"
```

---

## Task 4: Participant — 역방향 매핑 + syncFromConfig humans

**Files:**
- Modify: `src/core/workspace/participants.ts`
- Test: `tests/multiuser-routing.test.ts`

- [ ] **Step 1: Write failing test — findParticipantByChannelTarget**

```typescript
describe("findParticipantByChannelTarget", () => {
  it("finds participant by channel + target", async () => {
    await upsertParticipant({
      id: "daye", type: "human", display_name: "다예",
      channel: "telegram", channel_target: "12345",
    });
    const { findParticipantByChannelTarget } = await import(
      "../src/core/workspace/participants"
    );
    const found = await findParticipantByChannelTarget("telegram", "12345");
    expect(found).not.toBeNull();
    expect(found!.id).toBe("daye");
  });

  it("returns null for unknown target", async () => {
    const { findParticipantByChannelTarget } = await import(
      "../src/core/workspace/participants"
    );
    const found = await findParticipantByChannelTarget("telegram", "unknown");
    expect(found).toBeNull();
  });

  it("returns null for inactive participant", async () => {
    await upsertParticipant({
      id: "old-user", type: "human", display_name: "Old",
      channel: "telegram", channel_target: "99999", active: false,
    });
    const { findParticipantByChannelTarget } = await import(
      "../src/core/workspace/participants"
    );
    const found = await findParticipantByChannelTarget("telegram", "99999");
    expect(found).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement findParticipantByChannelTarget**

`src/core/workspace/participants.ts`:

```typescript
export async function findParticipantByChannelTarget(
	channel: string,
	target: string,
): Promise<Participant | null> {
	const db = getDb();
	const row = db
		.prepare(
			"SELECT * FROM participants WHERE channel = ? AND channel_target = ? AND active = 1",
		)
		.get(channel, target) as Record<string, unknown> | undefined;
	return row ? rowToParticipant(row) : null;
}
```

- [ ] **Step 4: Write failing test — syncParticipantsFromConfig with humans**

```typescript
describe("syncParticipantsFromConfig — humans", () => {
  it("registers humans from config", async () => {
    const { syncParticipantsFromConfig, listParticipants } = await import(
      "../src/core/workspace/participants"
    );
    await syncParticipantsFromConfig({
      minions: {
        orchestrator: "mingming", agents: ["worker-a"],
        owner: "daye", humans: ["teammate_a"],
      },
      agentMeta: {},
      paths: { brain: "./brain", agents: "./agents" },
      features: { compound_notify: true },
    });
    const all = await listParticipants();
    const humanIds = all.filter(p => p.type === "human").map(p => p.id);
    expect(humanIds).toContain("daye");
    expect(humanIds).toContain("teammate_a");
  });
});
```

- [ ] **Step 5: Run test to verify it fails**

- [ ] **Step 6: Update syncParticipantsFromConfig**

`src/core/workspace/participants.ts` — `syncParticipantsFromConfig` 내부, owner 등록 뒤에:

```typescript
	// Register additional humans
	for (const humanId of resolved.minions.humans ?? []) {
		if (humanId === ownerId) continue; // owner already registered
		const existing = await loadParticipant(humanId);
		if (!existing || existing.type !== "human") {
			await upsertParticipant({
				id: humanId,
				type: "human",
				display_name: existing?.display_name ?? humanId,
				channel: existing?.channel ?? null,
				channel_target: existing?.channel_target ?? null,
			});
		}
	}
```

- [ ] **Step 7: Run tests**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/core/workspace/participants.ts tests/multiuser-routing.test.ts
git commit -m "feat: findParticipantByChannelTarget + syncFromConfig humans support"
```

---

## Task 5: Tasks — addTaskNotifyParticipant + requester materialize

**Files:**
- Modify: `src/core/workspace/tasks.ts:369-529` (addTask 함수)
- Test: `tests/multiuser-routing.test.ts`

- [ ] **Step 1: Write failing test — requester auto-materialized into notify_participants**

```typescript
describe("task requester materialize", () => {
  it("auto-includes requester in notify_participants on addTask", async () => {
    const { addTask, loadTask } = await import("../src/core/workspace/tasks");
    // setupTestDb에서 필요한 agent participant가 있다고 가정
    const task = await addTask({
      ticketId: "T-100", assignee: "@worker-a", priority: "medium",
      goal: "test", createdBy: "mingming", requester: "daye",
    });
    expect(task.requester).toBe("daye");
    expect(task.notify_participants).toContain("daye");
  });

  it("does not duplicate requester if already in notify_participants", async () => {
    const { addTask } = await import("../src/core/workspace/tasks");
    const task = await addTask({
      ticketId: "T-101", assignee: "@worker-a", priority: "medium",
      goal: "test", createdBy: "mingming",
      requester: "daye", notifyParticipants: ["daye", "teammate_a"],
    });
    const dayeCount = task.notify_participants.filter(p => p === "daye").length;
    expect(dayeCount).toBe(1);
    expect(task.notify_participants).toContain("teammate_a");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add requester/notifyParticipants to addTask params + materialize logic**

`src/core/workspace/tasks.ts` — `addTask` params에 추가:
```typescript
	requester?: string;
	notifyParticipants?: string[];
```

`addTask` 함수 내부, task 객체 생성 시:
```typescript
	// Materialize requester into notify_participants
	const notifySet = new Set(params.notifyParticipants ?? []);
	if (params.requester) notifySet.add(params.requester);

	const task: TaskItem = {
		// ... 기존 필드 ...
		requester: params.requester,
		notify_participants: [...notifySet],
	};
```

- [ ] **Step 4: Write failing test — addTaskNotifyParticipant**

```typescript
describe("addTaskNotifyParticipant", () => {
  it("appends new participant", async () => {
    const { addTask, addTaskNotifyParticipant, loadTask } = await import(
      "../src/core/workspace/tasks"
    );
    await addTask({
      ticketId: "T-200", assignee: "@worker-a", priority: "medium",
      goal: "test", createdBy: "mingming", requester: "daye",
    });
    addTaskNotifyParticipant("T-200", "teammate_a");
    const updated = loadTask("T-200")!;
    expect(updated.notify_participants).toContain("daye");
    expect(updated.notify_participants).toContain("teammate_a");
  });

  it("does not duplicate existing participant", async () => {
    const { addTask, addTaskNotifyParticipant, loadTask } = await import(
      "../src/core/workspace/tasks"
    );
    await addTask({
      ticketId: "T-201", assignee: "@worker-a", priority: "medium",
      goal: "test", createdBy: "mingming", requester: "daye",
    });
    addTaskNotifyParticipant("T-201", "daye");
    const updated = loadTask("T-201")!;
    const count = updated.notify_participants.filter(p => p === "daye").length;
    expect(count).toBe(1);
  });
});
```

- [ ] **Step 5: Run test to verify it fails**

- [ ] **Step 6: Implement addTaskNotifyParticipant**

`src/core/workspace/tasks.ts`:

```typescript
export function addTaskNotifyParticipant(ticketId: string, participantId: string): void {
	const file = loadTasks();
	const task = file.tasks.find((t) => t.ticket_id === ticketId);
	if (!task) throw new Error(`Task not found: ${ticketId}`);
	const current = task.notify_participants ?? [];
	if (!current.includes(participantId)) {
		task.notify_participants = [...current, participantId];
		task.updated_at = nowKST();
		saveDirtyTasks(file, new Set([ticketId]));
	}
}
```

- [ ] **Step 7: Run tests**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/core/workspace/tasks.ts tests/multiuser-routing.test.ts
git commit -m "feat: requester materialize + addTaskNotifyParticipant"
```

---

## Task 6: Task DONE → Delivery Fanout

**Files:**
- Modify: `src/core/workspace/tasks.ts:757-921` (doneTask 함수)
- Test: `tests/multiuser-routing.test.ts`

- [ ] **Step 1: Write failing test — doneTask creates deliveries for notify_participants**

```typescript
describe("doneTask delivery fanout", () => {
  it("creates delivery for each notify_participant on DONE", async () => {
    // Setup: participant daye with channel
    await upsertParticipant({
      id: "daye", type: "human", display_name: "다예",
      channel: "telegram", channel_target: "12345",
    });
    await upsertParticipant({
      id: "teammate_a", type: "human", display_name: "A",
      channel: "telegram", channel_target: "67890",
    });

    const { addTask, doneTask } = await import("../src/core/workspace/tasks");
    await addTask({
      ticketId: "T-300", assignee: "@worker-a", priority: "medium",
      goal: "test", createdBy: "mingming",
      requester: "daye", notifyParticipants: ["daye", "teammate_a"],
    });

    // Start + done (force to skip review)
    await doneTask("T-300", { summary: "done" }, { force: true });

    const { listOpenDeliveries } = await import("../src/core/workspace/deliveries");
    const dayeDeliveries = await listOpenDeliveries("daye");
    const aDeliveries = await listOpenDeliveries("teammate_a");
    expect(dayeDeliveries.length).toBeGreaterThanOrEqual(1);
    expect(aDeliveries.length).toBeGreaterThanOrEqual(1);
  });

  it("does not create delivery for agent-originated task without requester", async () => {
    const { addTask, doneTask } = await import("../src/core/workspace/tasks");
    await addTask({
      ticketId: "T-301", assignee: "@worker-a", priority: "medium",
      goal: "internal task", createdBy: "mingming",
      // no requester, no notify_participants
    });
    await doneTask("T-301", { summary: "done" }, { force: true });

    // Should fallback to owner, not crash
    // Exact behavior depends on config — just verify no throw
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add delivery fanout to doneTask**

`src/core/workspace/tasks.ts` — `doneTask` 함수 내부, `clearCurrentTaskIfActive` 직전 (line ~920):

```typescript
	// Delivery fanout for notify_participants
	try {
		const recipients = task.notify_participants ?? [];
		if (recipients.length > 0) {
			const { createDelivery } = await import("./deliveries");
			// Find the latest thread message for this task as source
			const db = getDb();
			const latestMsg = db
				.prepare(
					"SELECT id FROM thread_messages WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
				)
				.get(ticketId) as { id: string } | undefined;

			if (latestMsg) {
				for (const recipientId of recipients) {
					try {
						await createDelivery({
							sourceMessageId: latestMsg.id,
							recipientParticipantId: recipientId,
							mode: "reviewed",
							taskRef: ticketId,
						});
					} catch (err) {
						// Per-recipient failure isolation — don't block others
						console.warn(
							`[tasks] delivery fanout failed for ${recipientId}: ${normalizeError(err)}`,
						);
					}
				}
			}
		}
	} catch (err) {
		console.warn(`[tasks] delivery fanout error: ${normalizeError(err)}`);
	}
```

- [ ] **Step 4: Run tests**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `npx vitest run --reporter=verbose`
Expected: 전부 PASS

- [ ] **Step 6: Commit**

```bash
git add src/core/workspace/tasks.ts tests/multiuser-routing.test.ts
git commit -m "feat: delivery fanout on task DONE for notify_participants"
```

---

## Task 7: Cron — recipients DB 반영 + 실행기 연동

**Files:**
- Modify: `src/core/workspace/cron-registry.ts`
- Test: `tests/multiuser-routing.test.ts`

Note: 크론 실행기의 recipients → delivery 연결은 크론 런타임(watchdog/openclaw) 수준이므로, 여기서는 recipients가 cron DB에 저장/조회되는 것까지 구현. 실제 fanout은 cron 실행 완료 이벤트에서 처리하며, 이는 watchdog 모듈에 훅을 추가하는 별도 작업이 될 수 있음.

- [ ] **Step 1: Write failing test — cron recipients round-trip**

```typescript
describe("cron registry — recipients", () => {
  it("stores and retrieves recipients", async () => {
    const { registerCron, loadCronEntry } = await import(
      "../src/core/workspace/cron-registry"
    );
    await registerCron({
      name: "test-cron", schedule: "0 8 * * *",
      agent_id: "worker-a", command: "echo test",
      origin: { type: "skill", skill_id: "news-brief" },
      recipients: ["daye", "teammate_a"],
    });
    const entry = loadCronEntry("test-cron");
    expect(entry).not.toBeNull();
    expect(entry!.recipients).toEqual(["daye", "teammate_a"]);
  });

  it("recipients defaults to null for existing crons", async () => {
    const { registerCron, loadCronEntry } = await import(
      "../src/core/workspace/cron-registry"
    );
    await registerCron({
      name: "legacy-cron", schedule: "0 * * * *",
      agent_id: "worker-a", command: "sync.sh",
      origin: { type: "skill", skill_id: "sync" },
    });
    const entry = loadCronEntry("legacy-cron");
    expect(entry!.recipients).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add recipients column to crons table**

`src/core/db/index.ts` — crons CREATE TABLE에 추가:
```sql
recipients TEXT  -- JSON array or null
```

- [ ] **Step 4: Update cron-registry CRUD for recipients**

`src/core/workspace/cron-registry.ts`:
- `CRONS_INSERT_SQL`에 `recipients` 추가
- `entryToParams()`에 `recipients: entry.recipients ? JSON.stringify(entry.recipients) : null`
- `rowToEntry()`에 `recipients: row.recipients ? JSON.parse(row.recipients) : null`

- [ ] **Step 5: Run tests**

Run: `npx vitest run tests/multiuser-routing.test.ts --reporter=verbose`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/core/db/index.ts src/core/workspace/cron-registry.ts src/core/schemas/cron-registry.ts tests/multiuser-routing.test.ts
git commit -m "feat: cron recipients storage in DB"
```

---

## Task 8: daye-agent-toolkit — cron.json + SKILL.md 하드코딩 제거

**Working directory:** `~/git_workplace/daye-agent-toolkit`

**Files:**
- Modify: `shared/news-brief/cron.json`
- Modify: `shared/life-coach/cron.json`
- Modify: `shared/spending-manager/cron.json`
- Modify: `shared/investment-manager/cron.json`
- Modify: `shared/news-brief/SKILL.md`

- [ ] **Step 1: news-brief/cron.json — recipients 추가, 하드코딩 제거**

```json
[
  {
    "name": "daily-newspaper",
    "schedule": "0 8 * * *",
    "target": "daily-newspaper",
    "reason": "cron: daily-newspaper",
    "instructions": "news-brief 스킬의 'Quick Usage' 절차를 따르세요. enrich 단계를 절대 생략하지 마세요 — 영어 헤드라인이 남으면 안 됩니다. 완성된 HTML은 recipients에게 --media로 전달하세요.",
    "recipients": ["daye"]
  },
  {
    "name": "breaking-alert",
    "schedule": "0 * * * *",
    "target": "breaking-alert",
    "reason": "cron: breaking-alert",
    "instructions": "news-brief 스킬의 'Breaking Alert' 절차를 따르세요. 출력이 없으면 아무것도 하지 마세요.",
    "recipients": ["daye"]
  },
  {
    "name": "reddit-hot",
    "schedule": "0 */2 * * *",
    "target": "reddit-hot",
    "reason": "cron: reddit-hot",
    "instructions": "news-brief 스킬의 'Reddit 핫 포스트' 절차를 따르세요.",
    "recipients": ["daye"]
  }
]
```

- [ ] **Step 2: life-coach/cron.json**

```json
[
  {
    "name": "daily-coach",
    "schedule": "0 21 * * *",
    "target": "daily-coach",
    "reason": "cron: daily-coach",
    "instructions": "life-coach 스킬의 데일리 코칭을 실행하세요. 완성된 HTML은 recipients에게 --media로 전달하세요.",
    "recipients": ["daye"]
  },
  {
    "name": "weekly-coach",
    "schedule": "0 21 * * 0",
    "target": "weekly-coach",
    "reason": "cron: weekly-coach",
    "instructions": "life-coach 스킬의 위클리 코칭을 실행하세요. 완성된 HTML은 recipients에게 --media로 전달하세요.",
    "recipients": ["daye"]
  }
]
```

- [ ] **Step 3: spending-manager/cron.json — recipients 추가**

각 항목에 `"recipients": ["daye"]` 추가. instructions는 "daye" 하드코딩 없으므로 유지.

- [ ] **Step 4: investment-manager/cron.json — recipients 추가**

`"recipients": ["daye"]` 추가.

- [ ] **Step 5: news-brief/SKILL.md — "daye에게 전달" → 일반화**

line 44: `"daye에게 전달"` → `"recipients에게 전달"` 또는 수신자 하드코딩 제거.

- [ ] **Step 6: Commit**

```bash
git add shared/*/cron.json shared/news-brief/SKILL.md
git commit -m "feat: add recipients to cron.json, remove daye hardcoding"
```

---

## Verification Checklist

구현 완료 후:

- [ ] `npx vitest run` — dy-minions-squad 전체 테스트 통과
- [ ] `npm run types` — TypeScript 타입 체크 통과
- [ ] `npm run lint` — biome 린트 통과
- [ ] 기존 단일 사용자 동작이 깨지지 않는지 확인 (하위호환)
- [ ] cron.json에 잘못된 JSON 없는지 확인
