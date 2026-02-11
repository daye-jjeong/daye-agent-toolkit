---
name: saju-manse
description: Korean 사주/만세력 workflow: compute and interpret 사주팔자 (년/월/일/시 천간지지), 오행 균형, 용신/기신 후보, 대운/세운 포인트, and practical life guidance. Use when Daye asks to 봐줘/풀이해줘/만세력 기준으로 사주 분석, or wants ongoing 사주 체크-ins and 기록.
---

# 사주/만세력 (Saju Manse)


**Version:** 0.1.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

## Input checklist (ask if missing)
- Birth date/time: **YYYY-MM-DD HH:MM**
- Calendar: **양력/음력(윤달 여부)**
- Birthplace (city/country) and timezone at birth (default: Asia/Seoul)
- Sex (optional; only if the chosen interpretation style needs it)

## Workflow
1) Confirm inputs + timezone.
2) Compute the 4 pillars (년/월/일/시) 천간/지지.
   - If exact computation is needed and local script is available, run it.
   - Otherwise, use a reputable 만세력 reference source and record the pillars in the report.
3) Build the structure:
   - 오행 분포(목/화/토/금/수) and 강약
   - 십신(비견/겁재/식신/상관/편재/정재/편관/정관/편인/정인)
   - 격국/용신/희신/기신: present as **candidates with reasoning**, not absolute truth.
4) Translate into practical guidance:
   - Strengths/risks in decision-making, work style, money management, relationships, health routines.
   - Use “if-then” framing (e.g., “화 과다 → 과열/과속 리스크, 속도 조절 루틴”).
5) Time dimension:
   - 대운: 큰 흐름(전환/확장/보수)
   - 세운/월운: 단기 포인트(리스크 관리, 컨디션, 중요한 선택 타이밍)
6) Make it grounded:
   - Separate **observations** (pillars, element balance) vs **interpretation**.
   - Avoid deterministic or fear-based claims.

## Output format (default)
- 입력 요약
- 사주팔자(년/월/일/시)
- 오행/십신 핵심 요약 (3~7 bullets)
- 현재 고민(커리어/투자/건강 등)과 연결한 실행 제안 (3~5 bullets)
- 다음 체크 포인트(대운/세운 관점) 2~3개

## Safety / boundaries
- This is reflective guidance, not medical/legal/financial advice.
- Don’t claim certainty (“무조건”, “반드시”).
- If the user is making a big decision, recommend corroborating with real-world constraints (cashflow, contracts, health).
