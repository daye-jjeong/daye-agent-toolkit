---
name: system-audit
description: 시스템 감사 — 문서 린트 + 의미 분석 + 세션/크론 점검
metadata: {"openclaw":{"requires":{"bins":["python3","clawdbot","jq"]}}}
---

# System Audit Skill

**Version:** 2.0.0 | **Updated:** 2026-02-12 | **Status:** Active

시스템 문서 정합성, 의미적 정확성, 세션 상태, 크론 정합성을 통합 감사합니다.
Tier 1 (구문 린트) → Tier 3 (LLM 의미 분석) 하이브리드 파이프라인.

> **doc-lint 스킬을 흡수합니다.** 구문 린트는 `lint_docs.py`가 Tier 1로 처리하고, 의미적 분석은 LLM 세션이 담당합니다.

## Trigger

- Cron: `0 9 * * *` (매일 09:00)
- 수동: `/system-audit`
- 린트만: `python3 {baseDir}/scripts/lint_docs.py`

## Overview

두 단계로 실행:

**1단계 — Tier 1 구문 린트** (0토큰, `lint_docs.py`)
- 참조 유효성 (깨진 경로)
- 스킬/모델 이름 일관성
- 텍스트 중복, 레거시 참조
- 프로젝트 구조, MEMORY.md 범위
- 내용 최신성 (deprecated 패턴)

**2단계 — Tier 3 LLM 분석** (clawdbot 세션)
- 린트 결과를 입력으로 받아 우선순위 분류
- 정책 간 **의미적 충돌** 감지 (규칙이 서로 모순되는지)
- **의미적 중복** 감지 (같은 내용을 다른 표현으로 기술)
- **deprecated 정보** 판단 (패턴 매칭이 아닌 맥락 이해)
- 세션 상태 해석 + 정리 제안
- 크론 경로 정합성 확인
- vault 리포트 생성

## Scripts

| 파일 | 티어 | 역할 |
|------|------|------|
| `{baseDir}/scripts/lint_docs.py` | Tier 1 | 구문 린트 (참조, 이름, 중복, 레거시, 최신성) |
| `{baseDir}/scripts/daily_audit.sh` | 크론 러너 | lint → LLM 세션 파이프라인 실행 |

## lint_docs.py 옵션

```bash
python3 {baseDir}/scripts/lint_docs.py                  # 전체 (text)
python3 {baseDir}/scripts/lint_docs.py --format json     # JSON 출력
python3 {baseDir}/scripts/lint_docs.py --check refs      # 참조만
python3 {baseDir}/scripts/lint_docs.py --check skills    # 스킬 이름만
python3 {baseDir}/scripts/lint_docs.py --check models    # 모델 이름만
python3 {baseDir}/scripts/lint_docs.py --check stale     # 레거시만
python3 {baseDir}/scripts/lint_docs.py --check freshness # 최신성만
```

## Input / Output

**Input:** 시스템 .md 파일, `sessions_list`, `crontab -l`, lint JSON 결과

**Output:**
- `vault/reports/audit/YYYY-MM-DD.md` — 일일 감사 리포트
- Telegram 알림 (Critical만, 무음 정책 준수)
- 로그: `/tmp/daily-audit.log`

## Configuration

- Telegram 그룹: JARVIS HQ (`-1003242721592`)
- 모델: `anthropic/claude-sonnet-4-5` (비용 최적화)

## Notes

- 정상 상태에서는 Telegram 알림 없음 (무음 정책)
- vault 리포트는 항상 생성 (히스토리 추적용)
- 이전 감사 결과와 diff 비교하여 변경사항 하이라이트
- lint_docs.py 단독 실행도 지원 (빠른 구문 체크용)
