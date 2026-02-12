---
name: prompt-guard
description: 프롬프트 인젝션/탈옥 스캐너 — 패턴 매칭 + 시맨틱 탐지
user-invocable: false
---

# Prompt Guard

프롬프트 인젝션, 탈옥 시도, 악성 명령을 패턴 매칭으로 사전 차단하는 메시지 스캐너.
에이전트 파이프라인 앞단에서 메시지를 검사하여 위협을 차단한다.

**Version:** 0.1.0 | **Status:** Experimental

## 트리거 / 모드

- **자동 트리거**: 에이전트 파이프라인에 통합 시 모든 수신 메시지를 자동 스캔
- **수동 호출**: `guard.py --message "..."` 또는 `guard_prompt_injection.sh "..."`
- **모드**: `enabled` (차단) / `dry_run` (로그만) / `disabled` (비활성)

## 아키텍처

```
User Message → Gateway → PROMPT GUARD SCAN → SAFE → Normal Processing
                                           → BLOCKED → Refusal + Log (+ Alert if CRITICAL)
```

스캔 단계: 패턴 매칭 → 심각도 계산 → 화이트리스트 확인 → 판정

## 탐지 카테고리

| 카테고리 | 심각도 가중치 | 예시 |
|----------|-------------|------|
| Jailbreak | 0.8 (HIGH) | "Ignore previous instructions" |
| Prompt Injection | 0.9 (HIGH) | `[SYSTEM]` 태그, `ADMIN MODE` |
| Data Exfiltration | 1.0 (CRITICAL) | "Send credentials to http://..." |
| Harmful Intent | 0.95 (CRITICAL) | "rm -rf /", "Drop database" |

**상세**: `{baseDir}/references/detection-patterns.md` 참고

## 심각도 수준

| Level | Action |
|-------|--------|
| SAFE (0) | 허용 |
| LOW (1) | 허용 + 로그 |
| MEDIUM (2) | 허용 + 로그 |
| HIGH (3) | 차단 (기본 임계값) |
| CRITICAL (4) | 차단 + 관리자 알림 |

## 핵심 설정

`config.json`에서 관리. 주요 항목:

- `enabled` / `dry_run` / `severity_threshold` (기본: HIGH)
- `owner_whitelist`: 모든 검사를 우회하는 사용자 목록
- `safe_command_prefixes`: 검사를 우회하는 명령 접두사
- `notify_critical`: CRITICAL 시 텔레그램 알림

**상세**: `{baseDir}/references/configuration.md` 참고

## 사용법

```bash
# 메시지 스캔
python3 skills/prompt-guard/guard.py --message "test message"

# 셸 래퍼
./scripts/guard_prompt_injection.sh "message text"

# JSON 출력 / dry-run
python3 skills/prompt-guard/guard.py --json --message "test"
python3 skills/prompt-guard/guard.py --dry-run --message "test"
```

에이전트 파이프라인 통합은 pre-processing hook 방식을 권장한다.

**상세**: `{baseDir}/references/integration.md` 참고

## 출력 형식

```json
{
  "blocked": true,
  "severity": "HIGH",
  "confidence": 0.85,
  "labels": ["jailbreak_patterns"],
  "reason": "Jailbreak pattern detected"
}
```

- 차단 시 exit code 1, 안전 시 exit code 0
- `--json` 플래그로 JSON 출력, 기본은 사람이 읽기 쉬운 텍스트

## 성능

패턴 매칭 <10ms, 메모리 <5MB, 외부 API 호출 없음 (토큰 비용 0).

## 참고 문서

| 주제 | 파일 |
|------|------|
| 탐지 패턴 상세 + 오탐 처리 | `{baseDir}/references/detection-patterns.md` |
| 설정 전체 + 안전 기능 | `{baseDir}/references/configuration.md` |
| 테스트 (유닛/수동/드라이런) | `{baseDir}/references/testing.md` |
| 통합 방법 상세 | `{baseDir}/references/integration.md` |
| 운영: 마이그레이션/롤백/트러블슈팅 | `{baseDir}/references/operations.md` |
| 고급: 보안/언어지원/외부API/로드맵 | `{baseDir}/references/advanced.md` |

## 스크립트

| 파일 | 용도 | 티어 |
|------|------|------|
| `scripts/prompt_guard_scan.py` | 인바운드 메시지 패턴 매칭 스캐너 (CLI) | Tier 1 |
| `scripts/guard_prompt_injection.sh` | 프롬프트 가드 셸 래퍼 | Tier 1 |

## See Also

- **Policy:** AGENTS.md S 3 (Operational Rules - Safety)
- **Integration:** AGENTS.md S 2 (Session Protection - Message preprocessing)
- **Validation:** `scripts/validate_deliverable_accessibility.py`
