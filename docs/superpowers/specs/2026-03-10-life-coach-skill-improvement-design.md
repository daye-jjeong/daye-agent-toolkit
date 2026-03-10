# Life Coach Skill 개선 설계

**날짜:** 2026-03-10
**브랜치:** wt/life-coach-skill-v2
**범위:** Phase 1 — SKILL.md + coaching-prompts.md 개선 + skill-creator eval

---

## 배경

현재 life-coach 스킬은 두 가지 문제가 있다:

1. **코치 역할 부재**: SKILL.md 온디맨드 사용이 스크립트 실행 순서 나열에 그침. LLM이 코치가 아니라 스크립트 실행기처럼 보임.
2. **데이터 활용 부족**: `daily_coach.py --json`이 수집하는 데이터의 절반 이하가 coaching-prompts.md에 반영됨. 건강 데이터, 레포 상세, 행동 신호, 집중도 지표 등이 LLM에게 전달되지 않음.

---

## 설계

### 1. SKILL.md 구조 개편

**핵심 변경:** 온디맨드 코칭을 "스크립트 중심"에서 "코치 중심"으로 재프레이밍.

```
## 온디맨드 코칭

당신은 코치다. 스크립트는 데이터 수집 도구다.

### 준비 (데이터 수집)
1. python3 scripts/daily_coach.py --json → JSON
2. python3 ... | python3 timeline_html.py → /tmp/work_timeline.html 열기

### 코칭 시작
데이터 수집 후, 사용자 의도 확인:
- "빠른 요약" → coaching-prompts.md 전체 실행
- "특정 부분 집중" → 해당 섹션만 깊게
- 아무 말 없으면 → 전체 코칭 (기본값)

### 코칭 실행
coaching-prompts.md 프레임으로 데이터 기반 코칭 수행.
```

추가로 Scripts 테이블에 `timeline_html.py`, `timeline_chart.py` 추가.

---

### 2. coaching-prompts.md 개선

**600자 제약 제거** — 온디맨드 코칭은 터미널/HTML 출력이므로 Telegram 길이 제한 불필요.

#### 일일 코칭 섹션 (변경 후)

| 섹션 | 상태 | 사용 데이터 |
|------|------|------------|
| 📝 오늘의 정리 | 유지 | work_hours, session_count, tag_breakdown |
| 📂 레포별 상세 | **신규** | sessions[].repo/summary/duration_min/has_commits |
| 🔍 코칭 | 강화 | behavioral_signals, repeated_patterns, first_session, error_count |
| 📊 집중도 지표 | **신규** | sessions[].duration_min (평균 세션 길이, 짧은 세션<15분 비율) |
| 📈 작업 완료율 | **신규** | has_commits 있는 레포 수 / 전체 레포 수 |
| 🤖 자동화 제안 | 유지 | repeated_patterns |
| ⏭️ 내일 이어할 것 | 유지 | sessions[].summary (진행중 작업) |
| 💊 건강 / 🧊 유통기한 | **신규** | check_in, exercises, meals, pantry_expiry |
| 💬 코칭 마무리 질문 | **신규** | 반드시 reflection 질문 1개로 마무리 |

#### 주간 코칭 섹션 (변경 후)

| 섹션 | 상태 | 사용 데이터 |
|------|------|------------|
| 📝 주간 정리 | 유지 | total_sessions, total_hours, total_tokens |
| 🏷 태그·레포 분포 | **신규** | tags, repos (비율, 편중 분석) |
| 📅 요일별 생산성 | **신규** | daily[].work_hours (어떤 요일이 가장 생산적인가) |
| 🛌 휴식 패턴 | **신규** | active_days 계산 (무작업일 수 및 시점) |
| 🔍 방향성 코칭 | 강화 | weekly_signals, repeated_patterns 이전 코칭 연속성 추적 |
| 💊 주간 건강 요약 | **신규** | exercises, meals, check_ins |
| 🔮 다음 주 생각해볼 것 | 유지 | 패턴 기반 질문 |

**이전 코칭 연속성:** `repeated_patterns`에서 이전에 짚었던 패턴이 오늘/이번 주 개선됐는지 추적.

---

### 3. Skill-creator Eval

#### 테스트 케이스

| ID | 프롬프트 | 목적 |
|----|---------|------|
| 1 | `"오늘 코칭해줘"` | 전체 일일 코칭 + 의도 확인 흐름 |
| 2 | `"오늘 건강이랑 과작업 부분만 봐줘"` | 특정 섹션 집중 + 신규 건강 섹션 |
| 3 | `"이번 주 리뷰해줘"` | 주간 전체 + 신규 섹션들 |

#### 평가 기준

- LLM이 의도 확인부터 시작하는가 (스크립트 실행 열거 vs 코치 역할)
- 신규 섹션 (건강, 레포 상세, 집중도 지표 등)이 포함되는가
- 데이터 단순 나열 vs 해석+제안+코칭 질문

#### 비교

`with_skill` (개선 후) vs `old_skill` (현재 버전 스냅샷)

---

## 파일 변경 목록

```
shared/life-coach/
├── SKILL.md                          ← 코치 프레이밍 + 워크플로우 재구성
└── references/
    └── coaching-prompts.md           ← 600자 제약 제거 + 신규 섹션 7개 추가
```
