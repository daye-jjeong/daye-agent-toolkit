# Goal Planner - 남은 작업

## 1. 월간 목표 업데이트 (2026-02.yml)

`~/clawd/projects/_goals/2026-02.yml` 파일의 current 값들을 업데이트해줘:

- AI 비서 시스템 안정화 > SOT 체계: 30% → **70%** (projects/ 구조, 대시보드 v2, skill-sync v2, goal-planner, AGENTS.md 모두 완료)
- 나머지 KR은 다예에게 현재 상태 물어보고 업데이트

## 2. 주간 목표 조정 (2026-W07.yml)

`~/clawd/projects/_goals/2026-W07.yml` 업데이트:

- "로컬 프로젝트 관리 체계 완성" → status: done (projects/ 구조 + 대시보드 완성됨)
- 추가 필요한 항목:
  - skill repo 셋업 완료 (커밋/푸시/symlink)
  - 대시보드 일간 목표 표시 기능 추가
  - goal-planner 크론 연동

## 3. 오늘 일간 계획 생성 (2026-02-10.yml)

`python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py daily --dry-run` 실행 후 확인.
에너지 레벨은 다예에게 물어볼 것.

## 4. 대시보드 개선 (generate_dashboard_v2.py)

### 4-a. 일간 목표 표시 추가
`~/clawd/skills/task-dashboard/generate_dashboard_v2.py` (또는 symlink 후 `~/git_workplace/claude-skills/task-dashboard/generate_dashboard_v2.py`)

scan_goals()에서 daily YAML도 읽도록 수정:
- `_goals/YYYY-MM-DD.yml` 파일에서 top3, time_blocks, checklist 읽기
- _prepare_goals_data()에 daily 데이터 추가

JS renderGoals()에 일간 카드 추가:
- top3 목표 (체크 아이콘)
- 시간 블록 타임라인 (시각적 바)
- 체크리스트 (체크박스)

### 4-b. 디자인/레이아웃 개선
- goal-card 그리드: 모바일 반응형 (1col → 2col → 3col)
- 프로그레스바 애니메이션
- 일간 카드에 초록색 border-left (월=보라, 주=파랑, 일=초록 구분)
- 시간 블록 시각화: 타임라인 형태로 표시
- 체크리스트: 클릭 가능한 체크박스 UI

## 5. 대시보드 생성 + 검증

수정 후 대시보드 재생성:
```bash
cd ~/clawd/skills/task-dashboard && python3 generate_dashboard_v2.py
```
output: `~/clawd/docs/dashboard/index.html` 확인
