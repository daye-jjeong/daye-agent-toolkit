---
name: session-manager
description: 서브에이전트 세션 자동 fallback/retry — 429 rate limit 대응
user-invocable: false
---

# Session Manager Skill

## Purpose

서브에이전트 세션 spawn 시 rate limit, timeout, 모델 미가용 상황에서 자동 fallback/retry 로직 제공. Orchestrator 워크플로우의 연속성 보장.

## Core Workflow

1. 지정 모델로 세션 spawn 시도
2. 실패 시 에러 유형별 retry 전략 적용
3. retry 소진 시 fallback chain의 다음 모델로 전환
4. 모든 시도 결과를 `fallback_decisions.jsonl`에 기록

**Default Fallback Chain:**
```
gpt-5.2 → claude-sonnet-4-5 → gemini-3-pro → claude-haiku-4-5
```

## Retry Strategies

| Error Type | Strategy |
|------------|----------|
| Rate Limit (429) | 동일 모델 3회 retry (5s delay) → fallback |
| Timeout | 1회 retry → fallback |
| Model Unavailable | 즉시 fallback (retry 없음) |
| Unknown | 2회 exponential backoff → fallback |

## Key Features

- **Partial Substitution**: 실패한 worker만 fallback, 성공한 worker는 원래 모델 유지
- **Custom Fallback**: 태스크별 커스텀 fallback 순서 지정 가능
- **Comprehensive Logging**: `~/.clawdbot/agents/main/logs/fallback_decisions.jsonl`

## API Reference

### `spawn_subagent_with_retry(task, model, label, fallback_order=None, max_retries=3, retry_delay=5)`

단일 서브에이전트를 fallback 로직과 함께 spawn.

Returns: `{"success", "session_id", "model_used", "attempts", "fallback_chain", "error"}`

### `spawn_parallel_workers_with_fallback(tasks, fallback_order=None, partial_substitution=True)`

복수 worker를 병렬 spawn. 각 worker 독립적으로 fallback 적용.

- `tasks`: `[{"task", "model", "label"}, ...]` 형태의 리스트
- Returns: `{"success", "workers", "failed", "fallback_applied"}`

**상세**: `{baseDir}/references/api-details.md` 참고

## Integration

- **Orchestrator**: Phase 2 실행 시 `spawn_parallel_workers_with_fallback()` 호출
- **Task OS Guardrails**: `pre_work_gate()` 통과 후 fallback spawn 연결 가능

**상세**: `{baseDir}/references/integration-examples.md` 참고

## Operations

- **로그 조회**: `tail -n 20 ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl | jq`
- **설정 변경**: `spawn_with_fallback.py`의 `DEFAULT_FALLBACK_ORDER` 수정

**상세**: `{baseDir}/references/operations.md` 참고

## 스크립트

| 파일 | 용도 | 티어 |
|------|------|------|
| `scripts/subagent_watchdog_v2.js` | 서브에이전트 워치독 v2 (Node.js) | Tier 1 |
| `scripts/subagent_watchdog.js` | 서브에이전트 워치독 v1 (Node.js) | Tier 1 |
| `scripts/watchdog-subagent.py` | 서브에이전트 워치독 (Python) | Tier 1 |
| `scripts/watchdog-unresponsive.js` | 응답 없는 세션 감지/처리 (Node.js) | Tier 1 |
| `spawn_with_fallback.py` | 서브에이전트 fallback spawn 로직 | Tier 1 |
