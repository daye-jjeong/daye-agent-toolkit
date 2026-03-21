---
name: life-coach
description: 통합 라이프 코칭 — 작업 패턴 + 건강/운동/식사 분석. 데일리 코칭, 위클리 코칭, 온디맨드 코칭, 리포트 생성에 사용. "코칭해줘", "오늘 리포트", "주간 정리", "/coach" 등의 요청에 트리거.
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Life Coach Skill

CC/OpenClaw/Calendar 활동 + 건강/운동/식사 데이터를 기반으로 코칭 리포트를 생성한다.
데이터는 life-dashboard-mcp SQLite에서 조회.

**당신은 코치다.** 스크립트는 데이터를 수집하는 도구일 뿐이다.
데이터를 단순히 나열하지 마라 — 패턴을 읽고, 해석하고, 제안하고, 질문해라.

## 스킬 경계

| 스킬 | 책임 | 이 스킬이 하지 않는 것 |
|------|------|----------------------|
| **life-coach** | 코칭 생성 + 저장 + HTML 리포트 | 건강 기록/루틴, 토픽 생성 가이드 |
| **work-digest** | 세션 기록 + 데이터 준비 파이프라인 (수집→요약→토픽) | 코칭 |
| **health-tracker** | 운동/증상/PT/체크인 기록 + 루틴 + 분석 | 코칭 통합 |

## 코칭 축

- **주 축**: 작업 코칭 (세션, 토픽, 패턴, 구조 리뷰, 태스크 제안)
- **보조 축**: 건강/식사/유통기한 (데이터 있으면 포함, 없어도 코칭 성립)

## 모드

| 모드 | 트리거 | 데이터 범위 | 결과물 |
|------|--------|------------|--------|
| **데일리** | cron 매일 21시 / `코칭해줘` / `/coach daily` | 오늘 | HTML 리포트 |
| **위클리** | cron 매주 일 21시 / `주간 코칭` / `/coach weekly` | 이번 주 (월~일) | HTML 리포트 |
| **온디맨드** | 특정 주제 요청 (예: "구조 리뷰해줘") | 요청에 따라 | 대화형 or HTML |

모드 구분 없이 요청하면 → 시간 기준으로 판단 (21시 이후면 데일리, 일요일이면 위클리).

## 공통 워크플로우

모든 모드가 동일한 3단계를 따른다. CLI 명령어 상세는 `references/cli-reference.md` 참조.

### Phase 1: 데이터 준비

1. **세션 데이터 정리** — work-digest 스킬의 데이터 준비 파이프라인 실행 (Step 1~5)
   - 데일리: 오늘 날짜로 1회 실행
   - 위클리: 해당 주의 데이터가 있는 각 날짜에 대해 실행
   - 상세 절차는 work-digest SKILL.md 참조. 이 스킬에서 재정의하지 않는다.
2. **JSON 데이터 추출**
   - 데일리: `daily_coach.py --json --date <DATE>`
   - 위클리: `weekly_coach.py --json --date <DATE>`
   - `has_data: false`이면 Phase 1을 재확인

### Phase 2: 코칭 생성

1. **이전 코칭 참조** — `activity_writer.py previous-coaching`로 어제 코칭/pending 태스크/open follow-up 확인
2. **프로파일 참조** — `~/life-dashboard/profile.md` 있으면 코칭 톤에 반영
3. **코칭 마크다운 생성** — `references/coaching-prompts.md` 프레임 적용 → `/tmp/coaching_<DATE>.md` 저장
   - 데일리: 오늘의 정리 → 레포별 상세 → 집중도 → 구조 리뷰 → 태스크 제안 → 코칭 → 건강 → 마무리 질문
   - 위클리: 주간 정리 → 태그·레포 분포 → 요일별 생산성 → 휴식 패턴 → Follow-up → 방향성 코칭 → 건강 → 주간 점검

### Phase 3: 저장 + 리포트

1. **코칭 저장** — `activity_writer.py save-coaching`으로 섹션별 분해하여 DB 저장
2. **태스크 + follow-up 관리** — `save-task`, `resolve-task`, `resolve-followup`
3. **HTML 리포트 생성**
   - 데일리: `daily_report.py --input <json> --coaching <md>` → `/tmp/daily_report_<DATE>.html` → `open`
   - 위클리: `weekly_report.py --input <json> --coaching <md>` → `/tmp/weekly_report_<DATE>.html` → `open`
4. **Gate C: 리포트 프리뷰 검증** — `daily_report.py --validate` 또는 LLM이 직접 `validate_report()` 호출
   - 통과하면 `open`
   - 실패하면:
     - 데이터 문제 → 데이터 수정 후 리포트 재생성
     - 코칭 문제 (가짜 데이터 참조 등) → 코칭 재생성 후 리포트 재생성
   - 이슈를 `references/gate-c-issues.json`에 기록
   - 같은 type이 2일 이상 반복 → 스크립트 업데이트 제안 (사용자 승인 후 적용)

## 온디맨드 특정 주제

사용자가 특정 부분만 요청하면 해당 섹션만 깊게 분석.
전체 코칭이 아니면 Phase 3 (저장/리포트) 생략 가능.
life-dashboard MCP의 `get_today_summary` 도구로도 데이터 조회 가능.

## 톤 에스컬레이션

coach_state의 escalation_level에 따라 톤 변경:
- Level 0: 데이터 보여주고 질문. 부드러운 넛지.
- Level 1: 3일 연속 10h+ → 직접적 제안.
- Level 2: 7일 연속 or 미개선 → 직설적 지시.

## 주간 점검 (위클리 전용, review_items 기반)

1. **미분류 태그**: "기타" 세션 → 올바른 태그 수정. 반복 패턴은 TAG_KEYWORDS에 추가.
2. **미분류 mistake**: `references/mistake-categories.json`에 새 키워드 추가.
3. **빈 summary**: sync 로직 개선 필요한지 판단.
4. **stale worktree**: 머지 또는 정리 여부를 사용자에게 제안.

## Scripts

| Script | 용도 |
|--------|------|
| `daily_coach.py --json` | 일일 데이터 수집 → JSON 출력 |
| `weekly_coach.py --json` | 주간 데이터 수집 → JSON 출력 |
| `daily_report.py` | 일일 HTML 리포트 생성 |
| `weekly_report.py` | 주간 HTML 리포트 생성 |
| `timeline_html.py` | 인터랙티브 타임라인 HTML |
| `timeline_chart.py` | PNG 타임라인 차트 |

## References

| File | 내용 |
|------|------|
| `references/coaching-prompts.md` | 코칭 프레임 — 섹션별 상세 프롬프트 |
| `references/cli-reference.md` | Phase 1-3 CLI 명령어 상세 |
| `references/mistake-categories.json` | mistake 키워드 → 카테고리 매핑 |
