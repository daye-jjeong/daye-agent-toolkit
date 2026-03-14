---
name: codex-cli
description: Codex CLI 래퍼 — 코드 리뷰, 범용 질문을 Codex(OpenAI)에게 위임
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["codex","python3"]}}}
---

# Codex CLI

Codex CLI를 통해 코드 리뷰 및 범용 질문을 OpenAI 모델에게 위임합니다.

## When to Use

- **사용자가 "Codex"를 명시적으로 언급할 때만** 사용
- Claude가 자의적으로 Codex를 호출하지 않음
- 주 용도: 코드 리뷰 (다른 모델의 시각으로 검증)
- 부 용도: 범용 질문

## Usage

### Review Mode — 코드 리뷰 (기본)

```bash
# 현재 uncommitted 변경사항 리뷰
{baseDir}/scripts/call.sh --mode review

# 특정 브랜치 대비 리뷰
{baseDir}/scripts/call.sh --mode review --base main

# 특정 커밋 리뷰
{baseDir}/scripts/call.sh --mode review --commit abc123

# 커스텀 리뷰 지시
{baseDir}/scripts/call.sh --mode review "보안 취약점 위주로 봐줘"
```

### Exec Mode — 범용 질문

```bash
{baseDir}/scripts/call.sh --mode exec "이 프로젝트 구조 분석해줘"
{baseDir}/scripts/call.sh --mode exec --file src/app.tsx "이 파일 최적화 방안"
```

### Options

- `--mode review|exec` — 모드 선택 (기본: review)
- `--base BRANCH` — review 모드에서 비교 대상 브랜치
- `--commit SHA` — review 모드에서 특정 커밋 리뷰
- `--file PATH` — exec 모드에서 파일 컨텍스트 포함
- `--model MODEL` — 모델 지정 (기본: codex config.toml의 모델)

## Post-Processing

Codex 결과를 받은 후:
- **리뷰 결과** → 요약해서 사용자에게 전달
- **Critical/Important 이슈** → Claude가 수정 여부를 판단하고 제안
- Codex의 제안을 무조건 수용하지 않음 — Claude가 검증 후 적용

## Prerequisites

Codex CLI 설치 필요:
```bash
npm install -g @openai/codex
```
