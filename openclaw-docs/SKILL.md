---
name: openclaw-docs
description: OpenClaw 공식 문서 참조 가이드
---

# OpenClaw Docs

OpenClaw 설정/수정 시 공식 문서를 빠르게 참조하는 가이드.

## 문서 조회 방법

### 페이지 직접 fetch

```javascript
web_fetch({ url: "https://docs.openclaw.ai/<path>", extractMode: "markdown" })
```

### 전체 인덱스 (llms.txt)

```javascript
web_fetch({ url: "https://docs.openclaw.ai/llms.txt", extractMode: "markdown" })
```

## 작업별 참조 문서

| 작업 | 참조 페이지 |
|------|------------|
| 크론/자동화 | `automation/cron-jobs`, `automation/hooks` |
| 스킬 추가/수정 | `tools/skills`, `tools/skills-config` |
| 텔레그램 설정 | `channels/telegram` |
| 모델 변경/폴백 | `concepts/model-failover`, `concepts/model-providers` |
| 세션 관리 | `concepts/session`, `concepts/session-pruning` |
| 게이트웨이 설정 | `gateway/configuration`, `gateway/configuration-examples` |
| 보안/샌드박스 | `gateway/security`, `gateway/sandboxing` |
| 메모리 시스템 | `concepts/memory` |
| 시스템 프롬프트 | `concepts/system-prompt`, `concepts/context` |
| 멀티에이전트 | `concepts/multi-agent`, `tools/subagents` |
| 플러그인 | `tools/plugin` |
| 업데이트/설치 | `install/updating`, `install/installer` |
| OAuth/인증 | `concepts/oauth`, `gateway/authentication` |
| AGENTS.md 참조 | `reference/templates/AGENTS.md` |
| 트러블슈팅 | `help/troubleshooting`, `help/faq` |

## 전체 페이지 목록

**상세**: `{baseDir}/references/page-index.md` 참고 (카테고리별 전체 URL)

## 스니펫 관리

자주 참조하는 문서는 `~/openclaw/data/docs-snippets/`에 캐싱 가능.

**상세**: `{baseDir}/references/snippets-guide.md` 참고
