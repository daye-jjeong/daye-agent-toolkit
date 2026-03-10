# Codex Work Digest Design

**Date:** 2026-03-10
**Status:** Approved

## Goal

Codex CLI 세션에서 다음 두 가지를 자동화한다.

1. 작업 완료 또는 사용자 확인이 필요한 순간에 Telegram 알림을 보낸다.
2. context compaction 시점과 세션 종료 시점에 세션 내용을 요약하여 markdown work log로 저장한다.

이 기능은 Claude Code용 `cc/work-digest`와 유사한 운영 경험을 제공하되, Codex의 세션 저장 방식과 이벤트 모델에 맞게 별도 구현한다.

## Scope

이번 설계는 Codex CLI를 `codex` 명령으로 실행하는 사용 흐름을 전제로 한다.

포함 범위:
- Codex 전용 `notify.sh`
- Codex 전용 `session_logger.py`
- Codex 실행을 감싸는 wrapper
- Codex 전용 work log 경로와 state 파일
- `~/.codex/config.toml` 연결

제외 범위:
- Claude용 `cc/work-digest` 구조 변경
- Claude/Codex 로그 통합 파서 작성
- 일일/주간 digest 통합 리포트

## Directory Layout

Codex 전용 구조는 레포 안에 다음처럼 둔다.

```text
codex/work-digest/
├── scripts/
│   ├── codex-wrapper.sh
│   ├── notify.sh
│   └── session_logger.py
├── state/
└── work-log/
    └── YYYY-MM-DD.md
```

이 구조를 쓰는 이유:
- Claude 쪽과 역할 분리를 유지하면서도 운영 패턴은 비슷하게 맞출 수 있다.
- Codex 전용 코드와 상태 파일을 명확히 분리할 수 있다.
- 레포 안에 있으므로 스크립트 수정과 버전 관리가 쉽다.

## Architecture

### 1. Wrapper

`codex-wrapper.sh`는 사용자가 실행하는 `codex` 진입점이 된다.

흐름:
1. 실제 Codex 바이너리(`/opt/homebrew/bin/codex`)를 실행한다.
2. 현재 실행과 연결된 세션 JSONL 파일을 식별한다.
3. 실행 중 세션 파일을 가볍게 감시한다.
4. `compacted` 또는 `context_compacted` 이벤트가 나오면 `session_logger.py --event compaction`을 호출한다.
5. Codex 프로세스가 종료되면 `session_logger.py --event session_end`를 호출한다.

wrapper를 쓰는 이유:
- Codex에는 Claude처럼 명시적인 `SessionEnd` hook이 확인되지 않았다.
- CLI 사용이 고정돼 있으므로 종료 시점은 wrapper가 가장 단순하고 정확하게 잡을 수 있다.
- background watcher나 `codex-tui.log` 후처리보다 구현과 운영이 단순하다.

### 2. Notify

`notify.sh`는 `~/.codex/config.toml`의 `notify` 설정으로 연결한다.

사용 이벤트:
- `approval-requested`
- `agent-turn-complete`

알림 정책:
- `approval-requested`: 항상 즉시 Telegram 알림
- `agent-turn-complete`: 마지막 agent 메시지가 아래 둘 중 하나일 때만 Telegram 알림
  - 작업 완료 메시지
  - 사용자 확인/결정 요청 메시지

중간 진행상황, 단순 commentary, 반복 완료 메시지는 보내지 않는다.

### 3. Session Logger

`session_logger.py`는 wrapper가 명시적으로 호출하는 세션 기록기다.

입력:
- `session_id`
- `transcript_path`
- `cwd`
- `event` (`compaction` 또는 `session_end`)

출력:
- `codex/work-digest/work-log/YYYY-MM-DD.md`에 세션 섹션 append
- `codex/work-digest/state/session_logger_state.json`에 dedupe 상태 저장
- `session_end`일 때만 Telegram 요약 메시지 전송

## Trigger Model

### Notify trigger

Codex 설정에서 `notify` 스크립트를 연결하고, TUI 알림 필터를 최소 범위로 둔다.

- `approval-requested` -> notify
- `agent-turn-complete` -> notify

`notify.sh`는 입력 payload와 메시지 내용을 보고 실제 전송 여부를 최종 판단한다.

### Session log trigger

wrapper가 두 시점에만 logger를 호출한다.

- `compaction`
  세션 JSONL에서 `compacted` 또는 `context_compacted` 감지 시 1회 기록
- `session_end`
  실제 Codex 프로세스 종료 후 1회 기록

이벤트별 중복 기록 방지는 `session_id:event` 키로 처리한다.

## Transcript Parsing

Codex 세션 JSONL에서 우선 LLM 없이 다음 데이터를 추출한다.

- 세션 시작 시각
- 마지막 시각
- 첫 user 메시지
- 마지막 agent 메시지
- `task_complete`의 최종 메시지
- 실행한 명령/툴 호출 수
- token usage
- 승인 요청 횟수
- compaction 여부

이 데이터는 markdown 섹션의 본문과 요약 프롬프트 모두에 사용한다.

## Compaction Handling

compaction은 Claude의 `PreCompact`와 유사한 의미로 취급한다.

기록 원칙:
- 이 시점은 최종 종료가 아니므로 Telegram은 보내지 않는다.
- work-log에는 중간 백업 성격의 섹션을 남긴다.
- LLM 요약은 생략하거나 최소화한다.
- 세션 JSONL의 `replacement_history`와 직전 대화 흐름을 기반으로 “어디까지 진행됐는지”를 2-3줄로 적는다.

## Session End Handling

세션 종료 시에는 최종 기록으로 취급한다.

처리 원칙:
- 세션 전체 transcript를 바탕으로 태그 + 2-3줄 요약 생성
- 최종 작업 결과, 사용자에게 남긴 메시지, 검증 여부를 가능한 범위에서 반영
- Telegram에 요약 전송

LLM 호출은 Claude가 아니라 실제 Codex 바이너리의 `codex exec --ephemeral`을 사용한다.

중요한 제약:
- `session_logger.py` 내부에서 요약용 Codex 호출 시 wrapper 경로를 쓰지 않는다.
- 반드시 실제 바이너리 `/opt/homebrew/bin/codex`를 직접 사용해 재귀 로그/알림을 막는다.

## Tagging

Claude 쪽 태그 체계를 그대로 유지한다.

- `코딩`
- `디버깅`
- `리서치`
- `리뷰`
- `ops`
- `설정`
- `문서`
- `설계`
- `리팩토링`
- `기타`

이렇게 맞추면 나중에 Claude/Codex 통합 집계가 필요해졌을 때 태그 체계를 재설계하지 않아도 된다.

## Markdown Format

날짜별 파일에 세션 섹션을 append한다.

예시:

```md
---
date: 2026-03-10
type: work-log
source: codex
tags: [work-log, codex]
---

# 2026-03-10 (화)

## 세션 23:10 (019cd811, daye-agent-toolkit)
> source: codex | event: session_end
> 파일 3개 | 18분 | 42.1K tokens

**요약**: [코딩] Codex용 work-digest 구조를 설계하고 wrapper 기반 lifecycle 연결 방식을 정리했다.
```

format 원칙:
- frontmatter에 `source: codex` 명시
- 섹션 본문에도 `source`와 `event`를 적어 later parser가 쉽게 처리하도록 한다
- compaction과 session_end는 같은 파일에 남기되 `event`로 구분한다

## Telegram Policy

Telegram 전송은 두 경로로 분리한다.

1. `notify.sh`
- 실시간성 우선
- approval / 완료 / 질문 필요 메시지만 전송

2. `session_logger.py`
- `session_end` 최종 요약만 전송
- compaction은 전송하지 않음

이 분리를 유지하면 같은 내용이 중복 전송되는 문제를 줄일 수 있다.

## Configuration Changes

`~/.codex/config.toml`에는 다음 개념이 반영된다.

- `notify` -> 레포 안 `codex/work-digest/scripts/notify.sh`
- `tui.notifications` -> `approval-requested`, `agent-turn-complete`

shell 환경에서는 사용자가 치는 `codex`가 wrapper를 통과하도록 alias 또는 PATH 우선순위를 설정한다.

## Risks

### 1. 세션 파일 식별 실패

wrapper가 방금 시작한 Codex 실행과 해당 JSONL 파일을 안정적으로 매칭해야 한다.

대응:
- 실행 시작 시각과 `~/.codex/sessions` 최신 파일을 함께 사용한다.
- session meta의 `cwd`와 timestamp를 함께 검증한다.

### 2. notify 과다 전송

`agent-turn-complete`는 빈도가 높다.

대응:
- 동일 세션, 동일 메시지 해시 dedupe
- 30초 이내 반복 전송 차단
- 완료/질문 필요 패턴만 허용

### 3. logger 내부 Codex 호출 재귀

요약용 `codex exec`가 wrapper를 다시 타면 무한 재귀 구조가 된다.

대응:
- `session_logger.py`는 실제 바이너리를 절대경로로 호출
- 요약용 호출은 `--ephemeral` 사용

## Testing Strategy

구현 시 검증해야 할 핵심 항목:

- notify payload 샘플로 `approval-requested` 알림 전송 검증
- `agent-turn-complete`에서 완료 메시지와 질문 메시지 필터링 검증
- sample Codex session JSONL로 `compaction` 기록 검증
- sample Codex session JSONL로 `session_end` 기록 검증
- state 기반 dedupe 검증
- wrapper가 실제 Codex 종료 코드를 그대로 전달하는지 검증

## Decision

Codex work-digest는 wrapper 기반 lifecycle 연결을 채택한다.

이유:
- CLI 사용 패턴과 가장 잘 맞는다.
- session_end를 가장 정확하게 잡을 수 있다.
- Claude의 `notify` / `session_logger` 역할 분리 모델을 비슷하게 유지할 수 있다.
- wrapper 없는 watcher 방식보다 구현과 운영 복잡도가 낮다.
