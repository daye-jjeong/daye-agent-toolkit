---
name: gemini-cli
description: Gemini CLI 래퍼 — 디자인 위임, 코드 리뷰, 범용 LLM 호출
metadata: {"openclaw":{"requires":{"bins":["gemini","python3"]}}}
---

# Gemini CLI

Gemini CLI를 통해 디자인, 리뷰, 범용 질문을 Gemini에게 위임합니다.

## When to Use

- **사용자가 "Gemini"를 명시적으로 언급할 때만** 사용
- Claude가 자의적으로 Gemini를 호출하지 않음
- 주 용도: 디자인 위임 (UI/UX, 시각적 아트)
- 부 용도: 코드/디자인 리뷰, 범용 질문

## Usage

### Design Mode — UI/UX + 시각적 아트

```bash
{baseDir}/scripts/call.sh --mode design "대시보드 레이아웃 만들어줘"
{baseDir}/scripts/call.sh --mode design --file src/app.tsx "이 컴포넌트 리디자인"
```

### Review Mode — Second Opinion

```bash
{baseDir}/scripts/call.sh --mode review --file src/app.tsx "이 코드 리뷰해줘"
```

### General — 범용 질문

```bash
{baseDir}/scripts/call.sh "질문 내용"
```

### Options

- `--mode design|review` — 모드 선택 (시스템 프롬프트 자동 주입)
- `--file PATH` — 파일 컨텍스트 포함
- `--model MODEL` — 모델 지정 (기본: gemini-2.5-pro)
- `--raw` — JSON 출력 (디버깅용)

## Post-Processing

Gemini 결과를 받은 후:
- **HTML/CSS/SVG 코드** → 파일로 저장하고 경로 안내
- **텍스트 리뷰** → 요약해서 사용자에게 전달
- **필요시** Claude가 결과를 검증하고 수정/보완

## Prerequisites

gemini-cli 설치 필요:
```bash
npm install -g @google/gemini-cli
```

## Extending Modes

새 모드 추가: `{baseDir}/references/prompts.md`에 `## <mode-name>` 섹션 추가.
