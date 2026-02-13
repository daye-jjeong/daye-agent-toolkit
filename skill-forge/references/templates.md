# 스킬 생성 템플릿

## .claude-skill 포맷

```json
{
  "name": "<skill-name>",
  "version": "1.0.0",
  "description": "<한줄 설명>",
  "entrypoint": "SKILL.md"
}
```

## SKILL.md frontmatter 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | Y | 스킬 식별자 |
| `description` | Y | 50자 이내 한줄 설명 (OpenClaw 시스템 프롬프트 주입) |
| `argument-hint` | N | 인수 힌트 (슬래시 커맨드 도움말) |
| `user-invocable` | N | `false`면 슬래시 커맨드 비노출 (내부 스킬) |
| `disable-model-invocation` | N | `true`면 모델 프롬프트에서 제외 (cron/수동 전용) |
| `metadata` | N | OpenClaw 의존성 게이팅 (requires.bins, requires.env) |

## SKILL.md 뼈대 템플릿

```yaml
---
name: <skill-name>
description: <한줄 설명>
argument-hint: "<사용법 힌트>"
---

# <스킬 이름>

<1-2문장 개요>

## 트리거

<언제 / 어떤 키워드로 동작하는지>

## 워크플로우

### Step 1: ...

### Step 2: ...

## 출력 포맷

<결과물 형태>
```

## 스킬 분류 기준

| 분류 | .claude-skill | OpenClaw enabled | 예시 |
|------|---------------|------------------|------|
| CC 전용 | O | X | mermaid-diagrams, skill-forge |
| CC + OpenClaw | O | O | health-tracker, vault-memory |
| OpenClaw 전용 | X | O | notion, orchestrator |
