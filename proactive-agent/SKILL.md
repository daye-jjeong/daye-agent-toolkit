---
name: proactive-agent
version: 1.0.0
description: 능동적 에이전트 패턴 — 선제 제안 + 자가 치유
source: "https://github.com/sundial-org/awesome-openclaw-skills/tree/main/skills/proactive-agent"
adapted: true
---

# Proactive Agent (openclaw 적응판)

원본 스킬의 행동 패턴을 openclaw 아키텍처에 맞게 적용한 버전.
openclaw의 기존 시스템 파일(HEARTBEAT.md, SOUL.md, format.md)에 통합되어 동작한다.

---

## 통합 현황

| 패턴 | 통합 위치 | 상태 |
|------|----------|------|
| Context Flush Protocol | `vault/format.md` § 6 | 적용 |
| Reverse Prompting | `SOUL.md` | 적용 |
| Self-Healing | `HEARTBEAT.md` | 적용 |
| Proactive Surprise | `HEARTBEAT.md` | 적용 |
| Memory Flush Checklist | `vault/format.md` § 6 | 적용 |
| Security Hardening | `HEARTBEAT.md` (기존 + 강화) | 적용 |
| Onboarding | 미적용 (openclaw는 USER.md 직접 관리) | 스킵 |
| Curiosity Loops | 미적용 (MEMORY.md + USER.md로 커버) | 스킵 |

---

## 핵심 원칙

### 마인드셋 전환
- "뭘 해야 하지?" 대신 "다예에게 진짜 도움이 될 건 뭐지?"
- 대기하지 않고 선제적으로 가치 창출
- 단, 외부 행동(메일 발송, 게시 등)은 반드시 승인 후

### Context Flush Protocol
컨텍스트 윈도우 기반 단계별 메모리 저장:

| 컨텍스트 % | 행동 |
|-----------|------|
| < 50% | 정상 운영. 결정사항은 바로 기록 |
| 50-70% | 경계 강화. 주요 교환 후 핵심 포인트 기록 |
| 70-85% | 적극 플러시. 중요 사항 전부 즉시 기록 |
| > 85% | 긴급 플러시. 다음 응답 전 전체 컨텍스트 요약 기록 |
| 컴팩션 후 | 즉시 유실된 컨텍스트 확인 + 연속성 체크 |

### Reverse Prompting
주기적으로 사용자에게:
1. "내가 알고 있는 것 기반으로, 해줄 수 있는 흥미로운 것들이 있어요"
2. "어떤 정보가 있으면 더 도움이 될까요?"

### Self-Healing
```
이슈 감지 → 원인 조사 → 수정 시도 → 테스트 → 문서화
```
최소 5-10가지 접근을 시도한 후에야 도움 요청.

---

## 참조 문서

- [원본 SKILL.md](https://github.com/sundial-org/awesome-openclaw-skills/tree/main/skills/proactive-agent)
- [references/security-patterns.md](references/security-patterns.md) — 보안 패턴 상세
- [references/onboarding-flow.md](references/onboarding-flow.md) — 온보딩 플로우 (참조용)

---

## 자동화

| 스케줄 | 작업 | 스크립트 |
|--------|------|---------|
| */30 9-22 * * * | 통합 Proactive Suggestions (체크+제안) | `scripts/proactive_suggestions.py` |

## 스크립트

| 파일 | 용도 | 티어 |
|------|------|------|
| `scripts/proactive_suggestions.py` | 통합 제안 생성: 크론에러/세션/태스크/캘린더/백로그/시스템 체크 (JSON 출력) | Tier 1 |
| `scripts/security-audit.sh` | 자격증명, 시크릿 노출, 주입 방어 체크 | Tier 1 |
