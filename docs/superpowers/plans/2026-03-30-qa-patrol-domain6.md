# QA Patrol Domain 6: 메타 로그 완결성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 태스크 상태 이벤트 누락을 근본 수정하고, CLI 표면을 확장하고, qa-patrol Domain 6 체크를 추가하여 메타 로그 완결성을 검증한다.

**Architecture:** 3-part 순차 실행. Part 1은 `tasks.ts`의 `updateTaskStatus`와 `syncParentStatus`에 `logStatusEvent` 호출을 추가한다. Part 2는 Zod 스키마와 CLI에 누락 필드/명령을 추가한다. Part 3는 qa-patrol의 checks.md와 SKILL.md에 Domain 6을 추가한다. 대상 레포는 `/Users/dayejeong/dy-minions-squad/`.

**Tech Stack:** TypeScript, better-sqlite3, Zod, vitest, Commander.js

---

## File Structure

### Part 1 — 태스크 상태 이벤트 근본 수정

| File | Action | Responsibility |
|------|--------|---------------|
| `src/core/workspace/tasks.ts` | Modify | `syncParentStatus` 반환 타입 변경 + `updateTaskStatus`에 `logStatusEvent` 추가 + 9개 호출측 업데이트 |
| `tests/sync-parent-status-events.test.ts` | Create | `syncParentStatus` Map 반환 + 이벤트 기록 검증 |
| `tests/update-task-status-events.test.ts` | Create | `updateTaskStatus`의 `logStatusEvent` 호출 검증 |

### Part 2 — CLI 표면 확장

| File | Action | Responsibility |
|------|--------|---------------|
| `src/core/schemas/cron-run.ts` | Modify | `delivered_at`, `delivery_id` 필드 추가 |
| `src/core/workspace/cron-runs.ts` | Modify | `rowToCronRun`에 새 필드 매핑 |
| `src/core/schemas/thread.ts` | Modify | `job_id` 필드 추가 |
| `src/core/workspace/threads.ts` | Modify | `rowToThreadMessage`에 `job_id` 매핑 |
| `src/core/schemas/delivery.ts` | Modify | `job_id` 필드 추가 |
| `src/core/workspace/deliveries.ts` | Modify | `rowToDelivery`에 `job_id` 매핑 |
| `src/core/workspace/queue.ts` | Modify | `getAllJobs` 함수 추가 |
| `src/cli/queue.ts` | Modify | `queue list --all` 옵션 추가 |
| `src/cli/delivery.ts` | Modify | `delivery events <id> --json` 서브커맨드 추가 |
| `tests/cli-schema-surface.test.ts` | Create | 새 필드/명령 검증 |

### Part 3 — qa-patrol Domain 6

| File | Action | Responsibility |
|------|--------|---------------|
| `core-skills/qa-patrol/references/checks.md` | Modify | Domain 6 섹션 추가 |
| `core-skills/qa-patrol/SKILL.md` | Modify | Domain 6 요약 추가 |

---

## Part 1: 태스크 상태 이벤트 근본 수정

### Task 1: `syncParentStatus` 반환 타입 변경 + 테스트

**Files:**
- Modify: `src/core/workspace/tasks.ts:730-783`
- Create: `tests/sync-parent-status-events.test.ts`

- [ ] **Step 1: 테스트 파일 생성 — syncParentStatus가 Map을 반환하는지 검증**

```ts
// tests/sync-parent-status-events.test.ts
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/core/workspace/wake-push", () => ({
	pushWake: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@/core/workspace/immediate-spawn", () => ({
	triggerOrchestratorSpawn: vi.fn().mockResolvedValue(false),
}));

import { resetDb } from "@/core/db";
import { addTask, doneTask, loadTask, startTask } from "@/core/workspace/tasks";
import { listThreadMessages } from "@/core/workspace/threads";

describe("syncParentStatus logs status_change events", () => {
	let tmpDir: string;
	let origRoot: string | undefined;

	beforeEach(async () => {
		tmpDir = await mkdtemp(join(tmpdir(), "sync-parent-events-"));
		origRoot = process.env.MINIONS_ROOT;
		process.env.MINIONS_ROOT = tmpDir;
		resetDb();
		await mkdir(join(tmpDir, "minions"), { recursive: true });
		await writeFile(
			join(tmpDir, "minions", "config.json"),
			JSON.stringify({ agents: { kevin: { skills: [] }, stuart: { skills: [] } } }),
		);
	});

	afterEach(async () => {
		vi.restoreAllMocks();
		resetDb();
		if (origRoot !== undefined) process.env.MINIONS_ROOT = origRoot;
		else delete process.env.MINIONS_ROOT;
		await rm(tmpDir, { recursive: true, force: true });
	});

	it("parent IN_PROGRESS event is logged when child starts", async () => {
		// Create parent → child structure
		await addTask({
			ticketId: "t-parent-1",
			assignee: "kevin",
			priority: "high",
			goal: "Parent task",
		});
		await addTask({
			ticketId: "t-child-1",
			assignee: "stuart",
			priority: "high",
			goal: "Child task",
			parentId: "t-parent-1",
		});

		// Start child — triggers syncParentStatus → parent becomes IN_PROGRESS
		await startTask("t-child-1", { memo: "starting", force: true });

		// Verify parent status
		const parent = loadTask("t-parent-1");
		expect(parent?.status).toBe("IN_PROGRESS");

		// Verify parent has a status_change thread message
		const parentMessages = listThreadMessages("t-parent-1");
		const statusChangeMessages = parentMessages.filter(
			(m) => m.tags.includes("status_change") && m.content.includes("IN_PROGRESS"),
		);
		expect(statusChangeMessages.length).toBeGreaterThanOrEqual(1);
	});

	it("parent REVIEW_READY event is logged when all children done", async () => {
		await addTask({
			ticketId: "t-parent-2",
			assignee: "kevin",
			priority: "high",
			goal: "Parent task 2",
		});
		await addTask({
			ticketId: "t-child-2",
			assignee: "stuart",
			priority: "high",
			goal: "Only child",
			parentId: "t-parent-2",
		});

		await startTask("t-child-2", { memo: "go", force: true });
		await doneTask("t-child-2", {
			workReport: { summary: "done" },
			force: true,
		});

		const parent = loadTask("t-parent-2");
		expect(parent?.status).toBe("REVIEW_READY");

		const parentMessages = listThreadMessages("t-parent-2");
		const reviewReadyEvents = parentMessages.filter(
			(m) => m.tags.includes("status_change") && m.content.includes("REVIEW_READY"),
		);
		expect(reviewReadyEvents.length).toBeGreaterThanOrEqual(1);
	});
});
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/sync-parent-status-events.test.ts`
Expected: FAIL — 현재 `syncParentStatus`는 부모에 대해 `logStatusEvent`를 호출하지 않으므로 `status_change` 메시지가 없음.

- [ ] **Step 3: `syncParentStatus` 반환 타입을 Map으로 변경**

`src/core/workspace/tasks.ts`에서 `syncParentStatus` 함수를 수정:

```ts
type ParentStatusChange = { from: TaskStatus; to: TaskStatus };

function syncParentStatus(file: TasksFile, parentId?: string): Map<string, ParentStatusChange> {
	const changes = new Map<string, ParentStatusChange>();
	if (!parentId) return changes;

	const parent = file.tasks.find((t) => t.ticket_id === parentId);
	if (!parent) return changes;

	const children = file.tasks.filter((t) => t.parent_id === parentId);
	if (children.length === 0) return changes;

	const allDone = children.every((c) => isDepSatisfied(c));
	const allReviewable = children.every(
		(c) => c.status === "REVIEW_READY" || isDepSatisfied(c),
	);
	const anyActive = children.some((c) => c.status === "IN_PROGRESS" || c.status === "NEEDS_INPUT");
	const newStatus = allDone
		? "REVIEW_READY"
		: allReviewable
			? "REVIEW_READY"
			: anyActive
				? "IN_PROGRESS"
				: null;

	if (newStatus && newStatus !== parent.status) {
		const fromStatus = parent.status;
		const now = nowKST();

		const db = getDb();
		if (newStatus === "IN_PROGRESS") {
			db.prepare("UPDATE tasks SET status = ?, updated_at = ?, delivered_at = NULL WHERE ticket_id = ?").run(
				newStatus, now, parentId,
			);
			parent.delivered_at = undefined;
		} else {
			db.prepare("UPDATE tasks SET status = ?, updated_at = ? WHERE ticket_id = ?").run(
				newStatus,
				now,
				parentId,
			);
		}

		parent.status = newStatus as TaskStatus;
		parent.updated_at = now;
		changes.set(parent.ticket_id, { from: fromStatus, to: newStatus as TaskStatus });

		// Recurse up the tree
		for (const [id, change] of syncParentStatus(file, parent.parent_id)) {
			changes.set(id, change);
		}
	}

	return changes;
}
```

- [ ] **Step 4: 모든 호출측을 Map 인터페이스로 업데이트**

`syncParentStatus`를 호출하는 9개 함수를 전부 동일 패턴으로 수정한다. 각 호출측에서 기존 `Set<string>` → `Map<string, ParentStatusChange>` 사용으로 변경하고, `saveDirtyTasks` 후 `logStatusEvent`를 호출한다.

**헬퍼 함수 추가** (tasks.ts 내부, `syncParentStatus` 바로 아래):

```ts
async function applySyncParentChanges(
	file: TasksFile,
	changes: Map<string, ParentStatusChange>,
): Promise<void> {
	if (changes.size === 0) return;
	saveDirtyTasks(file, new Set(changes.keys()));
	for (const [id, { from, to }] of changes) {
		await logStatusEvent(id, from, to, "system", "child status sync");
	}
}
```

**`updateTaskStatus` (L631 부근)** — 기존:
```ts
const parentDirty = syncParentStatus(file, task.parent_id);
if (parentDirty.size > 0) saveDirtyTasks(file, parentDirty);
```
수정:
```ts
const parentChanges = syncParentStatus(file, task.parent_id);
await applySyncParentChanges(file, parentChanges);
```

**`unblockTask` (L706 부근)** — 기존:
```ts
const dirty = syncParentStatus(file, task.parent_id);
dirty.add(ticketId);
saveDirtyTasks(file, dirty);
```
수정:
```ts
const parentChanges = syncParentStatus(file, task.parent_id);
const dirty = new Set(parentChanges.keys());
dirty.add(ticketId);
saveDirtyTasks(file, dirty);
for (const [id, { from, to }] of parentChanges) {
	await logStatusEvent(id, from, to, "system", "child status sync");
}
```

**`startTask` (L809 부근)** — 기존:
```ts
const dirty = syncParentStatus(file, task.parent_id);
dirty.add(ticketId);
saveDirtyTasks(file, dirty);
```
수정:
```ts
const parentChanges = syncParentStatus(file, task.parent_id);
const dirty = new Set(parentChanges.keys());
dirty.add(ticketId);
saveDirtyTasks(file, dirty);
for (const [id, { from, to }] of parentChanges) {
	await logStatusEvent(id, from, to, "system", "child status sync");
}
```

**`doneTask` (L1022 부근)** — 기존:
```ts
const dirty = syncParentStatus(file, task.parent_id);
dirty.add(ticketId);
// ... batchedChildren 등 추가 dirty
saveDirtyTasks(file, dirty);
```
수정:
```ts
const parentChanges = syncParentStatus(file, task.parent_id);
const dirty = new Set(parentChanges.keys());
dirty.add(ticketId);
for (const child of batchedChildren) dirty.add(child.ticket_id);
for (const p of promoted) dirty.add(p.ticket_id);
saveDirtyTasks(file, dirty);
for (const [id, { from, to }] of parentChanges) {
	await logStatusEvent(id, from, to, "system", "child status sync");
}
```

**`submitTask` (L1153 부근)** — 기존:
```ts
const parentDirty = syncParentStatus(file, task.parent_id);
if (parentDirty.size > 0) saveDirtyTasks(file, parentDirty);
```
수정:
```ts
const parentChanges = syncParentStatus(file, task.parent_id);
await applySyncParentChanges(file, parentChanges);
```

**`needsInputTask` (L1213 부근)** — 기존:
```ts
const dirty = syncParentStatus(file, task.parent_id);
dirty.add(ticketId);
saveDirtyTasks(file, dirty);
```
수정:
```ts
const parentChanges = syncParentStatus(file, task.parent_id);
const dirty = new Set(parentChanges.keys());
dirty.add(ticketId);
saveDirtyTasks(file, dirty);
for (const [id, { from, to }] of parentChanges) {
	await logStatusEvent(id, from, to, "system", "child status sync");
}
```

**`resumeTask` (L1250 부근)** — 동일 패턴 적용.

**`resumeScheduledTask` (L1307 부근)** — 동일 패턴 적용.

**`archiveTask` (L1360 부근)** — 기존:
```ts
const dirty = syncParentStatus(file, task.parent_id);
```
수정:
```ts
const parentChanges = syncParentStatus(file, task.parent_id);
const dirty = new Set(parentChanges.keys());
```
그리고 `saveDirtyTasks` 호출 후:
```ts
for (const [id, { from, to }] of parentChanges) {
	await logStatusEvent(id, from, to, "system", "child status sync");
}
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/sync-parent-status-events.test.ts`
Expected: PASS

- [ ] **Step 6: 기존 테스트 전체 실행 — 회귀 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run`
Expected: 기존 테스트 전부 PASS. `syncParentStatus` 반환 타입이 바뀌었으므로 기존 테스트에서 `.size`, `.has()`, `for...of` 등을 쓰는 곳이 있으면 Map 인터페이스와 호환되는지 확인. `Set`과 `Map` 모두 `.size`, `for...of`를 지원하므로 대부분 호환되지만 `.add()`, `.has()`가 쓰이면 컴파일 에러가 난다.

- [ ] **Step 7: 커밋**

```bash
git add src/core/workspace/tasks.ts tests/sync-parent-status-events.test.ts
git commit -m "feat: syncParentStatus returns Map with from/to status, logs status_change events via callers"
```

### Task 2: `updateTaskStatus`에 `logStatusEvent` 추가

**Files:**
- Modify: `src/core/workspace/tasks.ts:569-677`
- Create: `tests/update-task-status-events.test.ts`

- [ ] **Step 1: 테스트 파일 생성**

```ts
// tests/update-task-status-events.test.ts
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/core/workspace/wake-push", () => ({
	pushWake: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@/core/workspace/immediate-spawn", () => ({
	triggerOrchestratorSpawn: vi.fn().mockResolvedValue(false),
}));

import { resetDb } from "@/core/db";
import { addTask, startTask, updateTaskStatus } from "@/core/workspace/tasks";
import { listThreadMessages } from "@/core/workspace/threads";

describe("updateTaskStatus logs status_change events", () => {
	let tmpDir: string;
	let origRoot: string | undefined;

	beforeEach(async () => {
		tmpDir = await mkdtemp(join(tmpdir(), "update-status-events-"));
		origRoot = process.env.MINIONS_ROOT;
		process.env.MINIONS_ROOT = tmpDir;
		resetDb();
		await mkdir(join(tmpDir, "minions"), { recursive: true });
		await writeFile(
			join(tmpDir, "minions", "config.json"),
			JSON.stringify({ agents: { kevin: { skills: [] } } }),
		);
	});

	afterEach(async () => {
		vi.restoreAllMocks();
		resetDb();
		if (origRoot !== undefined) process.env.MINIONS_ROOT = origRoot;
		else delete process.env.MINIONS_ROOT;
		await rm(tmpDir, { recursive: true, force: true });
	});

	it("logs status_change when rejecting from REVIEW_READY", async () => {
		await addTask({
			ticketId: "t-reject-evt-1",
			assignee: "kevin",
			priority: "high",
			goal: "Test reject event",
		});
		await startTask("t-reject-evt-1", { memo: "go", force: true });
		// Manually set to REVIEW_READY for reject test
		await updateTaskStatus("t-reject-evt-1", "REVIEW_READY");

		// Now reject
		await updateTaskStatus("t-reject-evt-1", "IN_PROGRESS", {
			outcome: "rejected",
			outcomeReason: "test rejection",
			evaluation: {
				goal_met: "no",
				verdict: "reject",
				verdict_reason: "test",
				rework_scope: "small fix",
			},
		});

		const messages = listThreadMessages("t-reject-evt-1");
		const statusChangeToReviewReady = messages.filter(
			(m) => m.tags.includes("status_change") && m.content.includes("REVIEW_READY"),
		);
		expect(statusChangeToReviewReady.length).toBeGreaterThanOrEqual(1);

		const statusChangeToInProgress = messages.filter(
			(m) =>
				m.tags.includes("status_change") &&
				m.content.includes("REVIEW_READY → IN_PROGRESS"),
		);
		expect(statusChangeToInProgress.length).toBeGreaterThanOrEqual(1);
	});
});
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/update-task-status-events.test.ts`
Expected: FAIL — `updateTaskStatus`에서 `REVIEW_READY`로의 전이에 `logStatusEvent` 호출이 없음.

- [ ] **Step 3: `updateTaskStatus`에 `logStatusEvent` 추가**

`src/core/workspace/tasks.ts`의 `updateTaskStatus` 함수에서, `saveTask(task)` 호출 (L626) 직후에 추가:

```ts
	saveTask(task);

	// Log status change event for all transitions
	await logStatusEvent(ticketId, fromStatus, newStatus, opts?.caller ?? "system", "status update");
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/update-task-status-events.test.ts`
Expected: PASS

- [ ] **Step 5: 전체 테스트 실행**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run`
Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add src/core/workspace/tasks.ts tests/update-task-status-events.test.ts
git commit -m "feat: updateTaskStatus logs status_change event on all transitions"
```

---

## Part 2: CLI 표면 확장

### Task 3: `CronRun` 스키마에 `delivered_at`, `delivery_id` 추가

**Files:**
- Modify: `src/core/schemas/cron-run.ts`
- Modify: `src/core/workspace/cron-runs.ts:25-50` (`rowToCronRun`)

- [ ] **Step 1: `cronRunSchema`에 필드 추가**

`src/core/schemas/cron-run.ts`의 `cronRunSchema`에 추가:

```ts
	delivered_at: z.string().nullable().default(null),
	delivery_id: z.string().nullable().default(null),
```

- [ ] **Step 2: `rowToCronRun`에 매핑 추가**

`src/core/workspace/cron-runs.ts`의 `rowToCronRun` 함수 (L25-50)에 추가:

```ts
		delivered_at: row.delivered_at ?? null,
		delivery_id: row.delivery_id ?? null,
```

- [ ] **Step 3: tsc 타입 체크**

Run: `cd /Users/dayejeong/dy-minions-squad && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 4: 커밋**

```bash
git add src/core/schemas/cron-run.ts src/core/workspace/cron-runs.ts
git commit -m "feat: expose delivered_at, delivery_id in CronRun JSON output"
```

### Task 4: `ThreadMessage` 스키마에 `job_id` 추가

**Files:**
- Modify: `src/core/schemas/thread.ts`
- Modify: `src/core/workspace/threads.ts`

- [ ] **Step 1: `threadMessageSchema`에 `job_id` 추가**

`src/core/schemas/thread.ts`의 `threadMessageSchema`에:

```ts
	job_id: z.string().nullable().default(null),
```

- [ ] **Step 2: `threads.ts`의 row → schema 매핑에서 `job_id` 포함 확인**

`src/core/workspace/threads.ts`에서 `threadMessageSchema.parse(row)` 호출이 DB row를 파싱하는 곳을 찾아 `job_id`가 row에서 전달되는지 확인. DB 컬럼은 이미 존재 (`safeAddColumn("thread_messages", "job_id", "TEXT")`). Zod 스키마에 필드를 추가하면 `.parse(row)` 시 자동으로 매핑된다.

- [ ] **Step 3: tsc 타입 체크**

Run: `cd /Users/dayejeong/dy-minions-squad && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 4: 커밋**

```bash
git add src/core/schemas/thread.ts src/core/workspace/threads.ts
git commit -m "feat: expose job_id in ThreadMessage JSON output"
```

### Task 5: `Delivery` 스키마에 `job_id` 추가

**Files:**
- Modify: `src/core/schemas/delivery.ts`

- [ ] **Step 1: `deliverySchema`에 `job_id` 추가**

`src/core/schemas/delivery.ts`의 `deliverySchema`에:

```ts
	job_id: z.string().nullable().default(null),
```

DB 컬럼은 이미 존재 (`safeAddColumn("deliveries", "job_id", "TEXT")`). Zod `.parse(row)` 시 자동 매핑.

- [ ] **Step 2: tsc 타입 체크**

Run: `cd /Users/dayejeong/dy-minions-squad && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: 커밋**

```bash
git add src/core/schemas/delivery.ts
git commit -m "feat: expose job_id in Delivery JSON output"
```

### Task 6: `delivery events <id> --json` CLI 서브커맨드 추가

**Files:**
- Modify: `src/cli/delivery.ts`
- Create: `tests/cli-delivery-events.test.ts`

- [ ] **Step 1: 테스트 작성**

```ts
// tests/cli-delivery-events.test.ts
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Command } from "commander";
import { resetDb } from "@/core/db";
import { createDelivery } from "@/core/workspace/deliveries";
import { upsertParticipant } from "@/core/workspace/participants";
import { addThreadMessage } from "@/core/workspace/threads";
import { registerDeliveryCommands } from "@/cli/delivery";

describe("delivery events CLI", () => {
	let tmpDir: string;
	let origRoot: string | undefined;
	let logSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(async () => {
		tmpDir = await mkdtemp(join(tmpdir(), "delivery-events-cli-"));
		origRoot = process.env.MINIONS_ROOT;
		process.env.MINIONS_ROOT = tmpDir;
		resetDb();
		await mkdir(join(tmpDir, "minions"), { recursive: true });
		await writeFile(
			join(tmpDir, "minions", "config.json"),
			JSON.stringify({ agents: { kevin: { skills: [] } } }),
		);
		logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
	});

	afterEach(async () => {
		vi.restoreAllMocks();
		resetDb();
		if (origRoot !== undefined) process.env.MINIONS_ROOT = origRoot;
		else delete process.env.MINIONS_ROOT;
		await rm(tmpDir, { recursive: true, force: true });
	});

	it("outputs events as JSON", async () => {
		await upsertParticipant({
			id: "p-test",
			type: "human",
			displayName: "Test",
		});
		const msg = await addThreadMessage({
			author: "system",
			content: "test message",
			taskId: "t-test",
			tags: ["report"],
		});
		const delivery = await createDelivery({
			sourceMessageId: msg.id,
			recipientParticipantId: "p-test",
			mode: "reviewed",
		});

		const program = new Command();
		program.option("--json", "JSON output");
		registerDeliveryCommands(program);
		await program.parseAsync(
			["delivery", "events", delivery.id, "--json"],
			{ from: "user" },
		);

		const jsonCall = logSpy.mock.calls.find((call) => {
			try {
				const parsed = JSON.parse(call[0] as string);
				return Array.isArray(parsed);
			} catch {
				return false;
			}
		});
		expect(jsonCall).toBeDefined();
		const events = JSON.parse(jsonCall![0] as string);
		expect(events.length).toBeGreaterThanOrEqual(1);
		expect(events[0].type).toBe("created");
	});
});
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/cli-delivery-events.test.ts`
Expected: FAIL — `delivery events` 서브커맨드가 없음.

- [ ] **Step 3: `delivery events` 서브커맨드 추가**

`src/cli/delivery.ts`에서 기존 서브커맨드들 아래에 추가:

```ts
	delivery
		.command("events <delivery-id>")
		.description("배달 이벤트 이력 조회")
		.option("--json", "JSON 출력")
		.action(async (deliveryId: string, opts: { json?: boolean }) => {
			const events = await listDeliveryEvents(deliveryId);
			if (isJsonOutput({ ...opts, ...program.opts() })) {
				outputJson(events);
			} else {
				if (events.length === 0) {
					console.log("이벤트 없음");
					return;
				}
				for (const e of events) {
					const parts = [e.created_at, e.type];
					if (e.attempt) parts.push(`attempt=${e.attempt}`);
					if (e.error) parts.push(`error=${e.error}`);
					if (e.status_from || e.status_to) parts.push(`${e.status_from ?? "?"} → ${e.status_to ?? "?"}`);
					console.log(`- ${parts.join(" ")}`);
				}
			}
		});
```

`isJsonOutput`와 `outputJson`은 이미 `delivery.ts` 상단에서 import되어 있다. `listDeliveryEvents`도 이미 import되어 있다 (delivery show에서 사용).

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/cli-delivery-events.test.ts`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/cli/delivery.ts tests/cli-delivery-events.test.ts
git commit -m "feat: add 'delivery events <id> --json' CLI subcommand"
```

### Task 7: `queue list --all` 옵션 추가

**Files:**
- Modify: `src/core/workspace/queue.ts`
- Modify: `src/cli/queue.ts`
- Create: `tests/cli-queue-list-all.test.ts`

- [ ] **Step 1: 테스트 작성**

```ts
// tests/cli-queue-list-all.test.ts
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Command } from "commander";
import { resetDb } from "@/core/db";
import { registerQueueCommands } from "@/cli/queue";

vi.mock("@/core/workspace/wake-push", () => ({
	pushWake: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@/core/workspace/immediate-spawn", () => ({
	triggerOrchestratorSpawn: vi.fn().mockResolvedValue(false),
	triggerAgentScan: vi.fn().mockResolvedValue(false),
}));

import { completeQueueJob, pushQueueJob } from "@/core/workspace/queue";

describe("queue list --all", () => {
	let tmpDir: string;
	let origRoot: string | undefined;
	let logSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(async () => {
		tmpDir = await mkdtemp(join(tmpdir(), "queue-list-all-"));
		origRoot = process.env.MINIONS_ROOT;
		process.env.MINIONS_ROOT = tmpDir;
		resetDb();
		await mkdir(join(tmpDir, "minions"), { recursive: true });
		await writeFile(
			join(tmpDir, "minions", "config.json"),
			JSON.stringify({ agents: { kevin: { skills: [] } } }),
		);
		logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
	});

	afterEach(async () => {
		vi.restoreAllMocks();
		resetDb();
		if (origRoot !== undefined) process.env.MINIONS_ROOT = origRoot;
		else delete process.env.MINIONS_ROOT;
		await rm(tmpDir, { recursive: true, force: true });
	});

	it("includes completed jobs when --all is passed", async () => {
		const job = await pushQueueJob({
			agentId: "kevin",
			targetId: "test-target",
			scanReason: "test",
			policyVersion: "v1",
		});
		await completeQueueJob(job.id, "completed");

		const program = new Command();
		program.option("--json", "JSON output");
		registerQueueCommands(program);
		await program.parseAsync(
			["queue", "list", "--all", "--json"],
			{ from: "user" },
		);

		const jsonCall = logSpy.mock.calls.find((call) => {
			try {
				JSON.parse(call[0] as string);
				return true;
			} catch {
				return false;
			}
		});
		expect(jsonCall).toBeDefined();
		const jobs = JSON.parse(jsonCall![0] as string);
		expect(jobs.some((j: any) => j.status === "completed")).toBe(true);
	});
});
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/cli-queue-list-all.test.ts`
Expected: FAIL — `--all` 옵션이 없음.

- [ ] **Step 3: `getAllJobs` 함수 추가**

`src/core/workspace/queue.ts`에 `getQueuedJobs` 함수 근처에 추가:

```ts
export async function getAllJobs(agentId?: string): Promise<QueueJob[]> {
	const db = getDb();
	const rows = agentId
		? (db
				.prepare("SELECT * FROM jobs WHERE agent_id = ? ORDER BY created_at DESC")
				.all(agentId) as Record<string, unknown>[])
		: (db
				.prepare("SELECT * FROM jobs ORDER BY created_at DESC")
				.all() as Record<string, unknown>[]);
	return rows.map(rowToJob);
}
```

- [ ] **Step 4: `queue list` CLI에 `--all` 옵션 추가**

`src/cli/queue.ts`의 `queue list` 명령에서:

```ts
	queue
		.command("list")
		.description("대기 중인 job 목록")
		.option("--agent <id>", "에이전트 필터")
		.option("--all", "완료/실패 포함 전체 job 목록")
		.action(async (opts) => {
			const { getQueuedJobs, getAllJobs } = await import("../core/workspace/queue");
			const jobs = opts.all
				? await getAllJobs(opts.agent)
				: await getQueuedJobs(opts.agent);
			if (isJsonOutput(program.opts())) {
				outputJson(jobs);
			} else {
				// 기존 text 출력 유지
				for (const job of jobs) {
					console.log(`${job.target_id} — ${job.scan_reason} (priority: ${job.priority}, status: ${job.status})`);
				}
			}
		});
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run tests/cli-queue-list-all.test.ts`
Expected: PASS

- [ ] **Step 6: 전체 테스트 실행**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run`
Expected: ALL PASS

- [ ] **Step 7: 커밋**

```bash
git add src/core/workspace/queue.ts src/cli/queue.ts tests/cli-queue-list-all.test.ts
git commit -m "feat: add 'queue list --all' to include completed/failed jobs"
```

---

## Part 3: qa-patrol Domain 6

### Task 8: checks.md에 Domain 6 추가

**Files:**
- Modify: `core-skills/qa-patrol/references/checks.md`

- [ ] **Step 1: checks.md 끝에 Domain 6 섹션 추가**

`core-skills/qa-patrol/references/checks.md` 파일 끝 (Domain 5 메타 검증 섹션 이후)에 추가:

```markdown

## 6. 메타 로그 완결성

기록 자체의 정합성을 검증한다. "시스템이 동작했는가"(Domain 1-5)와 달리, "기록이 정확하게 남았는가"를 본다.

```bash
minions cron run list --format json
minions task list --json
minions task current --json
minions thread list --task-id <task-id> --json
minions delivery list --json
minions delivery events <id> --json
minions queue list --all --json
```

### 6-1. 크론 로그 완결성

| 조건 | 심각도 | 근거에 포함할 것 |
|------|--------|----------------|
| `completed` AND `result_data` null | P2 | cron_id, agent_id, 완료 시각, 원인 추정 (summary null → queue-fallback / summary 있음 → agent 누락) |
| `completed` AND recipients 비어있지 않음 AND `delivered_at` null AND `skipped_at` null AND 완료 후 1시간+ | P2 | cron_id, agent_id, 완료 시각, 경과 시간 |
| `completed` AND (`session_id` null OR `duration_ms` null) | P3 | cron_id, agent_id, 누락 필드명 |

### 6-2. 태스크 로그 완결성

| 조건 | 심각도 | 근거에 포함할 것 |
|------|--------|----------------|
| `DONE`/`IN_PROGRESS`/`REVIEW_READY` AND 해당 전이의 `thread_messages`(tag=`status_change`) 없음 | P2 | ticket_id, 현재 status, 누락된 전이 |
| `IN_PROGRESS`/`REVIEW_READY`/`DONE` AND `started_at` null | P3 | ticket_id, status |
| `DONE` AND `session_id` null | P2 | ticket_id, completed_at |
| `DONE` AND `outcome='success'` AND `work_report` null | P3 | ticket_id |

### 6-3. 배달 이벤트 완결성

| 조건 | 심각도 | 근거에 포함할 것 |
|------|--------|----------------|
| `status='sent'` AND `delivery_events`에 `type='sent'` 없음 | P2 | delivery_id, sent_at, 이벤트 목록 |
| `status='pending_review'` AND 생성 후 3시간+ AND 08:00~23:00 | P2 | delivery_id, 생성 시각, 경과 시간 |
| `status='failed'` AND 마지막 실패 후 2시간+ AND 재시도 이벤트 없음 | P3 | delivery_id, 실패 시각, 경과 시간 |

### 6-4. 크로스 테이블 추적 체인

| 조건 | 심각도 | 근거에 포함할 것 |
|------|--------|----------------|
| `jobs.status` completed/failed AND `cron_runs.status='running'` (job_id 조인) | P2 | job_id, cron_run_id, 양쪽 status |
| `cron_runs.status='completed'` AND `job_id` null | P2 | cron_id, run_id, 완료 시각 |
| `cron_runs.session_id` ≠ `jobs.spawn_session_id` (둘 다 non-null) | P3 | cron_run_id, job_id, 양쪽 session_id |
| `thread_messages` status_change AND `job_id` null | P3 | message_id, task_id |
| `deliveries.status='sent'` AND `job_id` null | P3 | delivery_id, task_ref |
| `current_tasks.task_id`가 `DONE`/`ARCHIVED` 태스크를 가리킴 | P2 | agent_id, task_id, task status |
```

- [ ] **Step 2: 커밋**

```bash
git add core-skills/qa-patrol/references/checks.md
git commit -m "feat: add Domain 6 meta-log completeness checks to qa-patrol"
```

### Task 9: SKILL.md에 Domain 6 요약 추가

**Files:**
- Modify: `core-skills/qa-patrol/SKILL.md`

- [ ] **Step 1: SKILL.md의 실행 절차 섹션에 Domain 6 언급 추가**

`core-skills/qa-patrol/SKILL.md`에서 `1. 검증: 5개 영역을 순서대로 검사` 부분을 수정:

```
1. 검증: 6개 영역을 순서대로 검사 → references/checks.md
```

- [ ] **Step 2: 커밋**

```bash
git add core-skills/qa-patrol/SKILL.md
git commit -m "feat: update qa-patrol SKILL.md to reference Domain 6"
```

### Task 10: 전체 검증

- [ ] **Step 1: 전체 테스트 실행**

Run: `cd /Users/dayejeong/dy-minions-squad && npx vitest run`
Expected: ALL PASS

- [ ] **Step 2: tsc 타입 체크**

Run: `cd /Users/dayejeong/dy-minions-squad && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: 크로스 파일 일관성 체크**

확인 사항:
- `ParentStatusChange` 타입이 `tasks.ts` 내에서만 사용되고 export되지 않는지 확인
- `applySyncParentChanges` 헬퍼가 `tasks.ts` 내에서만 사용되는지 확인
- `CronRun` 타입에 `delivered_at`, `delivery_id`가 추가되었고 `cron run list --format json` 출력에 포함되는지 확인
- `ThreadMessage` 타입에 `job_id`가 추가되었고 `thread list --json` 출력에 포함되는지 확인
- `Delivery` 타입에 `job_id`가 추가되었고 `delivery list --json` 출력에 포함되는지 확인
- `checks.md`의 Domain 6 섹션에서 참조하는 CLI 명령이 전부 존재하는지 확인
