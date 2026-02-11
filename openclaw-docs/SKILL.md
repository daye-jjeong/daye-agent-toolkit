---
name: openclaw-docs
description: OpenClaw 공식 문서 스마트 접근 — 스니펫 캐시 → 키워드 인덱스 → on-demand fetch 3계층 구조
---

# OpenClaw Docs

OpenClaw 공식 문서(docs.openclaw.ai)를 효율적으로 조회하는 스킬.
토큰 절약을 위한 3계층 구조: 스니펫(0) → 인덱스(0) → fetch(8-12k).

## 조회 워크플로우

### 1단계: 스니펫 확인 (0 tokens)

```bash
cat ~/clawd/data/docs-snippets/<topic>.md
```

| 스니펫 | 트리거 키워드 |
|--------|--------------|
| `telegram-setup.md` | telegram, 텔레그램, 봇 설정 |
| `oauth-troubleshoot.md` | token expired, oauth, 인증 에러 |
| `skill-setup.md` | 스킬 만들기, skill 설정, SKILL.md |
| `cron-setup.md` | cron, 자동화, 스케줄 |
| `config-basics.md` | config, 설정, gateway 설정 |
| `update-procedure.md` | 업데이트, update, 버전 |
| `memory-search.md` | memory, 메모리, vector search |
| `multi-agent.md` | multi-agent, 멀티에이전트, workspace |

### 2단계: 인덱스 검색 (0 tokens)

`~/clawd/data/docs-index.json`에서 키워드 매칭:

| 키워드 | 문서 경로 |
|--------|----------|
| telegram, discord, slack | `channels/<provider>` |
| cron, webhook, hook | `automation/<type>` |
| skill, plugin, tool | `tools/<name>` |
| agent, session, memory | `concepts/<topic>` |
| config, security, sandbox | `gateway/<topic>` |
| install, docker, update | `install/<method>` |
| anthropic, openai, bedrock | `providers/<name>` |
| ios, android, mac | `platforms/<os>` |

**전체 페이지 목록**: `{baseDir}/references/page-index.md` 참고

### 3단계: 페이지 fetch (최후 수단)

```javascript
web_fetch({ url: "https://docs.openclaw.ai/<path>", extractMode: "markdown" })
```

예시:
```javascript
web_fetch({ url: "https://docs.openclaw.ai/tools/skills", extractMode: "markdown" })
```

전체 인덱스 새로고침:
```javascript
web_fetch({ url: "https://docs.openclaw.ai/llms.txt", extractMode: "markdown" })
```

## TTL 전략

| 카테고리 | TTL | 이유 |
|----------|-----|------|
| `install/*` | 1일 | 설치 절차 변경 빈번 |
| `gateway/*`, `channels/*` | 7일 | 설정/제공자 업데이트 |
| `tools/*`, `automation/*` | 7일 | 기능 추가 |
| `concepts/*` | 14일 | 드물게 변경 |
| `reference/*`, `providers/*` | 30일 | 안정적 |

## 토큰 효율

| 방법 | 토큰 | 사용 시점 |
|------|------|----------|
| 스니펫 | 300-500 | 항상 최우선 |
| 인덱스 검색 | 0 | 키워드 매칭 |
| 페이지 fetch | 8-12k | 스니펫/인덱스에 없을 때 |

80-90%의 질문은 스니펫으로 해결 가능.

## 데이터 구조

```
~/clawd/data/
├── docs-index.json       # 검색 인덱스
├── docs-snippets/        # Golden Snippets
└── docs-cache/           # 페이지 캐시 (자동 관리)
```

**스니펫 관리 가이드**: `{baseDir}/references/snippets-guide.md` 참고
