# gemini-cli Skill Design

**Date**: 2026-02-27
**Status**: Approved

## Summary

Gemini CLI를 래핑하는 범용 스킬. 주 용도는 디자인 위임(UI/UX + 시각적 아트)이며,
리뷰/범용 질문으로 확장 가능. 사용자가 명시적으로 요청할 때만 호출.

## Structure

```
shared/gemini-cli/
├── SKILL.md              # Claude 가이드 (~100줄)
├── .claude-skill         # Claude Code 메타데이터
├── scripts/
│   └── call.sh           # gemini -p 래퍼
└── references/
    └── prompts.md        # 모드별 시스템 프롬프트 템플릿
```

## Call Flow

```
User: "Gemini로 디자인해줘"
  → Claude: SKILL.md 참조 → Bash로 call.sh 실행
  → call.sh: 모드별 프롬프트 주입 → gemini -p 실행
  → Gemini: 코드/텍스트 생성 → stdout 반환
  → Claude: 결과를 파일 저장 + 사용자에게 전달
```

## call.sh Interface

```bash
# 디자인 모드
{baseDir}/scripts/call.sh --mode design "대시보드 레이아웃 만들어줘"

# 파일 컨텍스트 포함
{baseDir}/scripts/call.sh --mode design --file src/app.tsx "이 컴포넌트 리디자인"

# 모델 지정 (기본: gemini-2.5-pro)
{baseDir}/scripts/call.sh --model gemini-2.5-flash "간단한 질문"

# 리뷰 모드
{baseDir}/scripts/call.sh --mode review --file src/app.tsx "코드 리뷰해줘"

# 범용 (모드 없음)
{baseDir}/scripts/call.sh "프롬프트 내용"

# raw 출력 (디버깅)
{baseDir}/scripts/call.sh --raw "테스트"
```

## Modes

| Mode | Purpose | System Prompt |
|------|---------|---------------|
| `design` | UI/UX + 시각적 아트 | 디자인 전문가 프롬프트 |
| `review` | 코드/디자인 리뷰 | 리뷰어 프롬프트 |
| (none) | 범용 질문 | 시스템 프롬프트 없음 |

## Prompt Extraction

- `references/prompts.md`에서 `## <mode>` 헤더로 구분
- call.sh가 해당 섹션 텍스트를 추출하여 시스템 프롬프트로 주입
- 새 모드 추가 = prompts.md에 섹션 추가만

## SKILL.md Sections

1. **When to Use** — 사용자가 "Gemini"를 명시적으로 요청할 때만
2. **Usage** — 모드별 실행 예시
3. **Post-Processing** — Claude가 결과 파일 저장/검증/보완
4. **Limitations** — 토큰 한계, OAuth 세션 만료 등

## Post-Processing Rules

- HTML/CSS → 파일로 저장, 경로 안내
- SVG → 파일로 저장
- 텍스트 리뷰 → 요약해서 전달
- Claude가 결과 검증 및 필요시 수정/보완

## Error Handling

- `gemini` 명령 없으면 → 설치 안내 후 exit 1
- 네트워크 에러 → stderr 메시지
- youtube-fetch 패턴과 동일

## Environment

- gemini-cli 설치됨 (brew)
- OAuth 인증
- 카테고리: shared/ (CC + OpenClaw 양쪽)
