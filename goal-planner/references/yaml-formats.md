# Goal Planner YAML Formats

## Monthly (YYYY-MM.yml)

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

## Weekly (YYYY-Www.yml)

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

## Daily (YYYY-MM-DD.yml)

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
