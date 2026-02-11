# Goal Planner

**Version:** 0.1.0
**Updated:** 2026-02-10
**Status:** Active

## 개요

월간 → 주간 → 일간 3계층 목표를 수립하고 관리하는 스킬.
`projects/_goals/` 디렉토리에 YAML 파일을 생성/수정한다.

## 트리거

사용자가 다음을 요청할 때 이 스킬을 활성화:
- "이번달 계획/목표 세우자"
- "이번주 계획 세우자"
- "오늘 계획 세우자"
- "플래닝 세션 하자"
- "목표 업데이트해줘"
- "회고하자" / "retrospective"

## 파일 구조

```
projects/_goals/
  ├── 2026-02.yml         # 월간 (YYYY-MM)
  ├── 2026-W07.yml        # 주간 (YYYY-Www)
  ├── 2026-02-10.yml      # 일간 (YYYY-MM-DD)
  └── ...
```

## 워크플로우

### 모드 1: 자동 드래프트 (기본)

상위 계층에서 하위 계층을 자동으로 생성하고 확인받는 방식.

**월간 → 주간:**
1. 현재 월간 목표 YAML 읽기
2. 이번주에 집중할 항목 자동 선별 (priority + KR 진행률 기반)
3. 캘린더(iCloud + Google) 일정 확인
4. 주간 목표 드래프트 생성 → 사용자 확인

**주간 → 일간:**
1. 현재 주간 목표 YAML 읽기
2. 오늘의 캘린더 일정 + 대기 태스크 확인
3. 시간 블록 + 체크리스트 자동 배치
4. 일간 목표 드래프트 생성 → 사용자 확인

### 모드 2: 대화형 플래닝 세션

밍밍이 질문하며 함께 목표를 세우는 방식.

**월간 플래닝 (월초):**
1. 지난달 회고 먼저 진행 (retrospective 필드)
2. "이번 달 가장 중요한 것은?" 질문
3. 프로젝트별 목표 + KR 설정
4. 테마 한 줄 정하기

**주간 플래닝 (월요일):**
1. 월간 목표 중 이번주 집중 항목 확인
2. "이번주 반드시 끝낼 것은?" 질문
3. 일정 고려해서 현실적 목표 조정

**일간 플래닝 (아침):**
1. 주간 목표 + 오늘 일정 확인
2. "오늘 가장 중요한 3가지는?" 질문
3. 에너지 레벨 체크 → 시간 블록 배치

## YAML 포맷

### 월간 (YYYY-MM.yml)

```yaml
month: "2026-02"
status: active
theme: "체계 잡기 + Pre-A 준비"

goals:
  - title: 목표 제목
    project: work--mingming-ai    # projects/ 폴더명
    priority: high|medium|low
    key_results:
      - description: KR 설명
        target: "100%"            # 숫자, %, 횟수, "완료"
        current: "30%"            # 현재 진행률

retrospective:
  achievement_rate: null
  went_well: []
  to_improve: []
  next_month_focus: []
```

### 주간 (YYYY-Www.yml)

```yaml
week: "2026-W07"
period: "2026-02-09 ~ 2026-02-15"
status: active

goals:
  - title: 주간 목표 제목
    project: work--mingming-ai
    priority: high|medium|low
    status: todo|in_progress|done
    key_results:
      - KR 항목 (문자열 리스트)

retrospective:
  went_well: []
  to_improve: []
  lessons: []
```

### 일간 (YYYY-MM-DD.yml)

```yaml
date: "2026-02-10"
day_of_week: "월"
energy_level: high|medium|low     # 아침 자가 체크
status: active

top3:                              # 오늘의 핵심 목표 3개
  - title: 핵심 목표 1
    project: work--mingming-ai
    status: todo|in_progress|done

time_blocks:                       # 시간대별 배치
  - time: "09:00-10:00"
    task: 탈잉 체크인 + 아침 루틴
    category: personal
  - time: "10:00-12:00"
    task: 캘리브레이션 정확도 개선
    category: work
  - time: "13:00-15:00"
    task: 포트폴리오 사이트 작업
    category: work
  - time: "15:00-16:00"
    task: PT 숙제
    category: personal

checklist:                         # 할일 체크리스트
  - task: 오전 탈잉 체크인
    done: false
  - task: 캘리브레이션 테스트 3회
    done: false
  - task: 포트폴리오 히어로 섹션
    done: false
  - task: PT 스쿼트 3세트
    done: false

retrospective:                     # 저녁에 작성
  completed_ratio: null            # 완료율 (자동 계산)
  mood: null                       # 1-5
  notes: ""
```

## 자동 드래프트 로직

### 주간 목표 자동 생성 규칙
1. 월간 goals 중 `priority: high` 우선 포함
2. KR `current`가 비어있거나 진행률 낮은 항목 우선
3. 해당 주에 캘린더 일정이 있는 프로젝트 반영
4. 최대 5개 목표 (현실적 범위)

### 일간 목표 자동 생성 규칙
1. 주간 goals 중 `status: in_progress` 또는 `todo` 항목에서 추출
2. 오늘 캘린더 일정을 time_blocks에 먼저 배치
3. 빈 시간대에 목표 관련 작업 자동 배치
4. 에너지 레벨 반영:
   - high → 어려운 작업을 오전에
   - medium → 균등 배분
   - low → 가벼운 작업 위주, 휴식 시간 포함
5. top3는 가장 임팩트 큰 3가지만 선정

## 스크립트

```bash
# 월간 목표 생성
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py monthly

# 주간 목표 생성 (월간에서 자동 드래프트)
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py weekly

# 일간 목표 생성 (주간 + 캘린더에서 자동 드래프트)
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py daily

# 특정 날짜 지정
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py daily --date 2026-02-11

# 드라이런 (파일 생성 없이 출력만)
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py weekly --dry-run

# 회고 모드
python3 ~/git_workplace/claude-skills/goal-planner/create_goal.py retro --type daily
```

## 연동

- **task-dashboard**: 생성된 목표가 대시보드 goals 섹션에 자동 반영
- **daily_goal_brief.py**: 텔레그램 브리핑에서 일간 목표 표시
- **schedule-advisor**: 캘린더 일정 참고하여 time_blocks 배치
- **health-tracker**: 에너지 레벨 데이터 연동 가능

## 크론 연동 (권장)

```
매일 08:30  → create_goal.py daily --auto (자동 생성 + 텔레그램 전송)
매주 월 08:00 → create_goal.py weekly --auto
매월 1일 09:00 → create_goal.py monthly --interactive (대화형)
```
