# Life Coach Skill 개선 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** life-coach 스킬을 "스크립트 실행기"에서 "LLM 코치"로 재프레이밍하고, coaching-prompts.md에 누락된 데이터 섹션 7개를 추가한다.

**Architecture:** SKILL.md는 코치 역할 선언 + 의도 확인 흐름으로 재구성. coaching-prompts.md는 수집된 데이터를 모두 활용하도록 섹션 추가. 변경 후 skill-creator eval로 before/after 비교.

**Tech Stack:** Markdown (SKILL.md, coaching-prompts.md), skill-creator eval

**Spec:** `docs/superpowers/specs/2026-03-10-life-coach-skill-improvement-design.md`

---

## Chunk 1: SKILL.md + coaching-prompts.md 편집

### Task 0: Old Skill 스냅샷 저장 (반드시 가장 먼저 실행)

**Files:**
- Create: `life-coach-skill-v2-workspace/skill-snapshot/life-coach/`

- [ ] **Step 1: 스냅샷 저장**

```bash
SKILL_PATH="/Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/life-coach-skill-v2/shared/life-coach"
WORKSPACE="/Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/life-coach-skill-v2/life-coach-skill-v2-workspace"
mkdir -p "$WORKSPACE/skill-snapshot"
cp -r "$SKILL_PATH" "$WORKSPACE/skill-snapshot/"
```

Expected: `skill-snapshot/life-coach/SKILL.md` 와 `skill-snapshot/life-coach/references/coaching-prompts.md` 존재 확인.

---

### Task 1: SKILL.md — 코치 프레이밍 + 워크플로우 재구성

**Note:** `{baseDir}`는 스킬 시스템이 런타임에 치환하는 템플릿 변수. 리터럴 문자열로 유지해도 됨.

**Files:**
- Modify: `shared/life-coach/SKILL.md`

- [ ] **Step 1: `온디맨드 사용` 섹션 전체 교체**

현재:
```markdown
## 온디맨드 사용 (/coach)

스크립트가 데이터를 수집하고, LLM이 직접 코칭을 수행한다.

### 일일 코칭
1. `python3 scripts/daily_coach.py --json` 실행 → JSON 데이터 획득
2. `python3 scripts/daily_coach.py --json | python3 scripts/timeline_chart.py` → 차트 생성
3. `open /tmp/work_timeline.png` → 차트 표시
4. `references/coaching-prompts.md`의 일일 코칭 프레임 적용
5. 데이터 기반으로 코칭 대화

### 주간 코칭
1. `python3 scripts/weekly_coach.py --json` 실행 → JSON 데이터 획득
2. `python3 scripts/weekly_coach.py --json | python3 scripts/timeline_chart.py --weekly` → 요일별 차트 생성
3. `open /tmp/work_timeline.png` → 차트 표시
4. `references/coaching-prompts.md`의 주간 코칭 프레임 적용
5. 주간 트렌드 + 방향성 코칭 대화

### 대안: MCP 도구 사용
life-dashboard MCP의 `get_today_summary` 도구로도 데이터 조회 가능.
```

교체 후:
```markdown
## 온디맨드 코칭 (/coach)

**당신은 코치다.** 스크립트는 데이터를 수집하는 도구일 뿐이다.
데이터를 단순히 나열하지 마라 — 패턴을 읽고, 해석하고, 제안하고, 질문해라.

### 준비 — 데이터 수집

**일일:**
```bash
python3 {baseDir}/scripts/daily_coach.py --json
python3 {baseDir}/scripts/daily_coach.py --json | python3 {baseDir}/scripts/timeline_html.py
open /tmp/work_timeline.html
```

**주간:**
```bash
python3 {baseDir}/scripts/weekly_coach.py --json
python3 {baseDir}/scripts/weekly_coach.py --json | python3 {baseDir}/scripts/timeline_html.py --weekly
open /tmp/work_timeline.html
```

### 코칭 시작 — 의도 확인

데이터 수집 후, 바로 리포트를 쏟아내지 마라. 먼저 의도를 확인해라:

- 사용자가 "빠른 요약" 또는 아무 말 없으면 → `references/coaching-prompts.md` 전체 프레임 적용
- "X 부분만 봐줘" 식이면 → 해당 섹션만 깊게 분석

### 코칭 실행

`references/coaching-prompts.md` 프레임으로 데이터를 해석하고 코칭한다.
escalation_level에 따른 톤 변화도 적용 (아래 "톤 에스컬레이션" 참조).

### 대안: MCP 도구 사용
life-dashboard MCP의 `get_today_summary` 도구로도 데이터 조회 가능.
```

- [ ] **Step 2: `일일 코칭 구성` 섹션 교체**

현재 (SKILL.md `### 일일 코칭 구성` 섹션 전체):
```markdown
### 일일 코칭 구성

1. **오늘의 정리** — 작업 시간, 세션 상세, 토큰 사용량
2. **레포별 상세** — 세션 수, 작업시간, 토큰, 요약 (daily_digest에서 이관)
3. **코칭** — 과작업, 수면 패턴, 집중도 기반 제안
4. **패턴 피드백** — 컨텍스트 스위칭, 에러, 테스트/커밋 현황
5. **자동화 제안** — 반복 명령/작업 감지
6. **건강 넛지** — 운동, 휴식
7. **유통기한** — 만료/임박 식재료 알림 (pantry-manager 데이터)
```

교체 후:
```markdown
### 일일 코칭 구성

1. **오늘의 정리** — 작업 시간, 세션 상세, 토큰 사용량
2. **레포별 상세** — 세션 수, 작업시간, 핵심 요약, 커밋 여부
3. **집중도 지표** — 세션 평균 길이, 짧은 세션(<15분) 비율, 작업 완료율(has_commits)
4. **코칭** — 행동 신호/반복 패턴/과작업/수면 패턴 기반 제안
5. **자동화 제안** — 반복 명령/패턴 감지
6. **내일 이어할 것** — 진행중 작업
7. **건강** — check_in, exercises, meals, symptoms
8. **유통기한** — pantry_expiry (만료/임박)
9. **마무리 질문** — 데이터 기반 reflection 질문 1개
```

- [ ] **Step 3: `주간 코칭 구성` 섹션 교체**

현재 (SKILL.md `### 주간 코칭 구성` 섹션 전체):
```markdown
### 주간 코칭 구성

1. **주간 정리** — 총 세션, 시간, 토큰
2. **일별 활동** — 바 차트 (daily_stats 기반)
3. **태그/레포 분포** — 작업 유형 편중 분석
4. **방향성 코칭** — 주간 트렌드 기반 다음 주 방향 제안
5. **다음 주 생각해볼 것** — 패턴 기반 reflect 질문
```

교체 후:
```markdown
### 주간 코칭 구성

1. **주간 정리** — 총 세션, 시간, 토큰
2. **태그·레포 분포** — 태그별/레포별 비율, 편중 분석
3. **요일별 생산성** — daily[].work_hours 기반 생산적인 요일 패턴
4. **휴식 패턴** — 무작업일 수 및 시점
5. **방향성 코칭** — weekly_signals + 이전 코칭 연속성 추적
6. **주간 건강 요약** — exercises, meals, check_ins
7. **다음 주 생각해볼 것** — 패턴 기반 reflect 질문
```

- [ ] **Step 4: Scripts 테이블 업데이트** — `timeline_html.py`, `timeline_chart.py` 추가

현재:
```markdown
| Script | Purpose |
|--------|---------|
| `daily_coach.py` | 일일 데이터 수집 + 템플릿 리포트 → 텔레그램 (건강 섹션 포함) |
| `weekly_coach.py` | 주간 데이터 수집 + 템플릿 리포트 → 텔레그램 (건강 섹션 포함) |
| `health_cmds.py` | 건강 코칭 서브커맨드 (루틴 추천, 증상 분석, 운동 가이드, 라이프스타일 조언, 건강 체크) |
| `track_health.py` | 일일 건강 체크인 기록 (수면, 걸음수, 운동, 스트레스, 수분) |
| `daily_routine.py` | 일일 건강 루틴 체크리스트 |
```

추가 후:
```markdown
| Script | Purpose |
|--------|---------|
| `daily_coach.py` | 일일 데이터 수집 + 템플릿 리포트 → 텔레그램 (건강 섹션 포함) |
| `weekly_coach.py` | 주간 데이터 수집 + 템플릿 리포트 → 텔레그램 (건강 섹션 포함) |
| `timeline_html.py` | 인터랙티브 타임라인 HTML 생성 → /tmp/work_timeline.html |
| `timeline_chart.py` | PNG 타임라인 차트 생성 → /tmp/work_timeline.png |
| `health_cmds.py` | 건강 코칭 서브커맨드 (루틴 추천, 증상 분석, 운동 가이드, 라이프스타일 조언, 건강 체크) |
| `track_health.py` | 일일 건강 체크인 기록 (수면, 걸음수, 운동, 스트레스, 수분) |
| `daily_routine.py` | 일일 건강 루틴 체크리스트 |
```

- [ ] **Step 5: 검증**

SKILL.md를 읽어 다음을 확인:
- "당신은 코치다." 문구가 있는가
- `### 준비 — 데이터 수집` 섹션에 `timeline_html.py` 명령이 있는가
- `### 코칭 시작 — 의도 확인` 섹션이 있는가
- `일일 코칭 구성`이 9개 항목인가
- `주간 코칭 구성`이 7개 항목인가
- Scripts 테이블에 `timeline_html.py`, `timeline_chart.py`가 있는가

- [ ] **Step 6: 커밋**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/life-coach-skill-v2
git add shared/life-coach/SKILL.md
git commit -m "feat(life-coach): SKILL.md 코치 프레이밍 + 워크플로우 재구성"
```

---

### Task 2: coaching-prompts.md — 600자 제약 제거 + 신규 섹션 추가

**Files:**
- Modify: `shared/life-coach/references/coaching-prompts.md`

- [ ] **Step 1: 일일 코칭 — 600자 제약 제거**

`다음 4개 섹션을 생성해라. 각 섹션 2-4줄. 총 600자 이내.` →
`다음 섹션들을 생성해라. 각 섹션 2-4줄. 간결하되, 데이터가 있는 섹션은 빠짐없이 다뤄라.`

- [ ] **Step 2: 일일 코칭 — `📂 레포별 상세` 섹션 추가** (`### 📝 오늘의 정리` 뒤에 삽입)

```markdown
### 📂 레포별 상세
- `sessions[]` 데이터 기반으로 레포별로 묶어 정리.
- 각 레포: 세션 수, 총 작업 시간, 핵심 요약 1줄.
- `has_commits=1`인 레포는 "(커밋됨)"으로 표시. 커밋 없는 레포는 "(진행중)" 표시.
- 3개 이상 레포가 있으면 컨텍스트 스위칭 여부를 명시해라.
- 데이터가 없으면 이 섹션 생략.
```

- [ ] **Step 3: 일일 코칭 — `📊 집중도 지표` 섹션 추가** (`### 📂 레포별 상세` 뒤에 삽입)

```markdown
### 📊 집중도 지표
- `sessions[].duration_min`으로 계산:
  - 세션 평균 길이 (분)
  - 짧은 세션(<15분) 비율 (%)
- `has_commits` 있는 레포 수 / 전체 레포 수 → 작업 완료율 표시.
- 짧은 세션 비율이 30% 이상이면 "분산 집중" 패턴으로 명시.
- 데이터가 없으면 이 섹션 생략.
```

- [ ] **Step 4: 일일 코칭 — `💊 건강 / 🧊 유통기한` 섹션 추가** (`### ⏭️ 내일 이어할 것` 뒤에 삽입)

```markdown
### 💊 건강
- `check_in`이 있으면: 수면 시간, 걸음수, 스트레스, 수분 요약.
- `exercises`가 있으면: 운동 종류 + 시간. 없으면 "운동 없음" 명시.
- `meals`가 있으면: 끼니 수, 총 칼로리, 단백질. 거른 끼니 있으면 명시.
- `symptoms`가 있으면: 증상과 심각도 요약.
- 데이터가 전혀 없으면 이 섹션 생략.

### 🧊 유통기한
- `pantry_expiry.expired`가 있으면: 만료된 식재료 목록.
- `pantry_expiry.expiring`이 있으면: 3일 내 만료 임박 목록.
- 둘 다 없으면 이 섹션 생략.
```

- [ ] **Step 5: 일일 코칭 — `💬 마무리 질문` 섹션 추가** (마지막 섹션으로)

```markdown
### 💬 마무리 질문
- 오늘 데이터에서 가장 눈에 띄는 패턴 하나를 골라 사용자에게 질문을 던져라.
- 답을 주지 말고 질문만. 사용자가 스스로 생각하게 하는 게 목적.
- 예: "오늘 3개 레포를 전환했는데, 그 중 가장 집중됐던 순간은 언제였어?"
- 반드시 1개만.
```

- [ ] **Step 6: 주간 코칭 — 500자 제약 제거**

`다음 3개 섹션을 생성해라. 각 섹션 2-4줄. 총 500자 이내.` →
`다음 섹션들을 생성해라. 각 섹션 2-4줄. 간결하되, 데이터가 있는 섹션은 빠짐없이 다뤄라.`

- [ ] **Step 7: 주간 코칭 — `🏷 태그·레포 분포` 섹션 추가** (`### 📝 주간 정리` 뒤에 삽입)

```markdown
### 🏷 태그·레포 분포
- `tags`: 태그별 세션 수와 비율. 상위 3개 태그 명시.
- `repos`: 레포별 세션 수. 상위 3개 레포 명시.
- 특정 태그나 레포에 50% 이상 편중되면 그 의미를 해석해라.
- 디버깅 비중이 25% 이상이면 "테스트 커버리지 점검 필요" 언급.
- 데이터 없으면 생략.
```

- [ ] **Step 8: 주간 코칭 — `📅 요일별 생산성` + `🛌 휴식 패턴` 섹션 추가** (`🏷` 뒤에 삽입)

```markdown
### 📅 요일별 생산성
- `daily[].work_hours`로 가장 생산적인 요일 상위 2개를 짚어라.
- 생산성이 낮은 날(0.5h 이하)이 있으면 이유를 추측하지 말고 그냥 명시.
- 요일 패턴이 명확하면 ("화·수에 집중") 다음 주 일정 계획 시 활용 제안.

### 🛌 휴식 패턴
- `daily[]`에서 `sessions=0`인 날이 있으면: 어떤 요일이었는지 명시.
- 7일 연속 작업이면 "의도한 건가?" 질문 포함.
- 휴식일이 주말이 아닌 평일이면 눈에 띄게 언급.
```

- [ ] **Step 9: 주간 코칭 — `💊 주간 건강 요약` 섹션 추가** (`🔍 방향성 코칭` 뒤에 삽입)

```markdown
### 💊 주간 건강 요약
- `exercises`: 운동일 수, 총 운동 시간, PT 횟수.
- `meals`: 총 끼니 수, 거른 끼니 수.
- `check_ins`: 평균 수면 시간 (데이터 있는 날만).
- `symptoms`: 있으면 건수와 주요 증상 요약.
- 운동일이 2일 이하면 부드럽게 언급.
- 데이터 전혀 없으면 이 섹션 생략.
```

- [ ] **Step 10: 주간 코칭 — 방향성 코칭에 이전 코칭 연속성 추가**

`### 🔍 방향성 코칭` 내용에 아래 항목 추가:
```
- **이전 패턴 추적**: `repeated_patterns`에서 지난번에 언급된 패턴이 이번 주에도 반복됐는지 확인.
  반복됐으면 "지난주에 짚었던 X가 이번 주도 반복됐어 — 구조적 원인을 볼 필요가 있어."
  개선됐으면 긍정적으로 짚어라.
```

- [ ] **Step 11: 검증**

coaching-prompts.md를 읽어 다음을 확인:
- "총 600자 이내" 문구가 없는가
- "총 500자 이내" 문구가 없는가
- 일일: `### 📂 레포별 상세` 섹션이 있는가
- 일일: `### 📊 집중도 지표` 섹션이 있는가
- 일일: `### 💊 건강` + `### 🧊 유통기한` 섹션이 있는가
- 일일: `### 💬 마무리 질문` 섹션이 있는가
- 주간: `### 🏷 태그·레포 분포` 섹션이 있는가
- 주간: `### 📅 요일별 생산성` + `### 🛌 휴식 패턴` 섹션이 있는가
- 주간: `### 💊 주간 건강 요약` 섹션이 있는가
- 주간: `방향성 코칭`에 "이전 패턴 추적" 항목이 있는가

- [ ] **Step 12: 커밋**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/life-coach-skill-v2
git add shared/life-coach/references/coaching-prompts.md
git commit -m "feat(life-coach): coaching-prompts 길이 제약 제거 + 신규 섹션 7개 추가"
```

---

## Chunk 2: Skill-creator Eval

### Task 3: Old skill 스냅샷 + Eval 실행

**Files:**
- Snapshot: `life-coach-skill-v2-workspace/skill-snapshot/` (old SKILL.md + coaching-prompts.md)
- Evals: `life-coach-skill-v2-workspace/evals/evals.json`

> **참고:** skill-creator eval은 subagent를 통해 with_skill / old_skill 두 버전을 병렬 실행한다.
> skill-creator 스킬의 "Running and evaluating test cases" 절차를 따른다.

- [ ] **Step 1: 스냅샷 확인** (Chunk 1 Task 0에서 이미 저장됨)

```bash
ls /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/life-coach-skill-v2/life-coach-skill-v2-workspace/skill-snapshot/life-coach/
```

Expected: `SKILL.md`, `references/coaching-prompts.md` 존재.
없으면 Task 0 Step 1을 먼저 실행할 것.

- [ ] **Step 2: evals.json 작성**

`life-coach-skill-v2-workspace/evals/evals.json`:
```json
{
  "skill_name": "life-coach",
  "evals": [
    {
      "id": 1,
      "prompt": "오늘 코칭해줘",
      "expected_output": "의도 확인 → 전체 일일 코칭. 레포별 상세, 집중도 지표, 건강 섹션, 마무리 질문 포함.",
      "files": []
    },
    {
      "id": 2,
      "prompt": "오늘 건강이랑 과작업 부분만 봐줘",
      "expected_output": "건강 데이터 + 과작업 패턴 집중 분석. 불필요한 섹션 생략.",
      "files": []
    },
    {
      "id": 3,
      "prompt": "이번 주 리뷰해줘",
      "expected_output": "주간 전체 코칭. 태그/레포 분포, 요일별 생산성, 휴식 패턴, 주간 건강 포함.",
      "files": []
    }
  ]
}
```

- [ ] **Step 3: skill-creator 스킬 호출해 with_skill / old_skill 병렬 실행**

skill-creator 스킬의 "Step 1: Spawn all runs" 절차 따름:
- `with_skill` run: 개선된 SKILL.md (Chunk 1 완료 후)
- `old_skill` run: `skill-snapshot/` 경로 지정
- 각 eval당 두 subagent 동시 실행

- [ ] **Step 4: 평가 어설션 작성 (runs 진행 중)**

```json
"assertions": [
  {"id": "coach-role", "description": "의도 확인 단계가 있는가 (스크립트 실행 나열로 시작하지 않는가)"},
  {"id": "new-sections", "description": "레포별 상세, 집중도 지표, 건강 섹션 중 최소 1개 포함"},
  {"id": "coaching-quality", "description": "데이터 단순 나열이 아닌 해석+제안+질문이 있는가"},
  {"id": "reflection-question", "description": "마무리 질문 1개로 끝나는가 (일일 코칭)"}
]
```

- [ ] **Step 5: eval-viewer 실행 + 사용자 리뷰**

```bash
SKILL_CREATOR_PATH="/Users/dayejeong/.claude/plugins/cache/claude-plugins-official/skill-creator/205b6e0b3036/skills/skill-creator"
WORKSPACE="/Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/life-coach-skill-v2/life-coach-skill-v2-workspace"

nohup python "$SKILL_CREATOR_PATH/eval-viewer/generate_review.py" \
  "$WORKSPACE/iteration-1" \
  --skill-name "life-coach" \
  --benchmark "$WORKSPACE/iteration-1/benchmark.json" \
  > /dev/null 2>&1 &
```

사용자가 리뷰 완료 후 feedback.json 반영해 필요 시 2차 iteration.

- [ ] **Step 6: 최종 커밋**

```bash
cd /Users/dayejeong/git_workplace/daye-agent-toolkit/.claude/worktrees/life-coach-skill-v2
git add life-coach-skill-v2-workspace/
git commit -m "eval: life-coach skill-creator eval 결과"
```
