---
name: codex-cli
description: Project-specific adversarial review prompt for Codex. Adds Korean attack axes (SoT layer violations, minimal scope violations) on top of the official /codex:adversarial-review. Use when the user asks for "설계 리뷰" or "프로젝트 adversarial".
---

# Codex Adversarial — 프로젝트 맞춤 프롬프트

공식 `/codex:adversarial-review`에 프로젝트 특화 공격 축을 추가하는 래퍼.

## Usage

1. `{baseDir}/references/adversarial-prompt.md`를 읽는다
2. 그 내용을 focus text로 `/codex:adversarial-review`에 전달한다

```
/codex:adversarial-review [프롬프트 내용을 focus text로 붙여넣기]
```

## 프롬프트 커스터마이징

공격 축을 바꾸려면 `references/adversarial-prompt.md`를 편집.

## 범용 Codex 명령

- `/codex:review` — 일반 코드 리뷰
- `/codex:adversarial-review` — 범용 adversarial (이 스킬 없이도 사용 가능)
- `/codex:rescue` — 태스크 위임
