# vault-memory:goal-update

> 기존 목표 YAML 파일의 진행률, 회고, 상태를 업데이트한다.

**YAML 포맷**: goal-planner 스킬의 `references/yaml-formats.md` 참조

## 트리거

- "목표 업데이트", "KR 진행률 수정", "진행률 반영"
- "회고 작성", "retrospective", "이번주 회고"
- "목표 완료", "이번달 목표 마감"
- goal-planner 회고 세션 결과를 파일에 반영할 때

## 액션

| 액션 | 설명 | 변경 필드 |
|------|------|-----------|
| **진행률** | KR의 current 값 업데이트 | `key_results[].current` |
| **상태** | 목표 또는 KR 상태 변경 | `status`, `goals[].status` |
| **회고** | retrospective 섹션 작성 | `retrospective` |
| **완료** | 목표 기간 종료 처리 | `status: completed` + retrospective |

## 워크플로우

### 1. 대상 파일 식별

명시되지 않으면:
- `memory/goals/monthly/` — 현재 월 파일
- `memory/goals/weekly/` — 현재 주 파일
- `memory/goals/daily/` — 오늘 파일

명시되면:
- "2026-W07 업데이트" → `goals/weekly/2026-W07.yml`
- "2월 목표 회고" → `goals/monthly/2026-02.yml`

### 2. 진행률 업데이트

#### 월간 KR
```yaml
key_results:
  - description: SOT 체계 구축
    target: "100%"
    current: "70%"       # ← 업데이트
```

#### 주간 목표
```yaml
goals:
  - title: 캘리봇 기획 완성
    status: done          # ← todo → in_progress → done
```

#### 일간 체크리스트
```yaml
checklist:
  - task: 오전 탈잉 체크인
    done: true            # ← false → true
top3:
  - title: 캘리봇 기획
    status: done          # ← 업데이트
```

### 3. 회고 작성

모든 계층에 `retrospective:` 섹션이 있다. 기간 종료 시 채운다.

#### 월간 회고
```yaml
retrospective:
  achievement_rate: 75%
  went_well:
    - SOT 체계 구축 + 대시보드 v3 완성
    - 스킬 정리 및 Notion→vault 마이그레이션
  to_improve:
    - 캘리봇 일정 지연 (기획 단계에서 머무름)
    - 일간 계획 실행률 낮음
  next_month_focus:
    - 캘리봇 구현 완료
    - 운동 루틴 정착
```

#### 주간 회고
```yaml
retrospective:
  went_well:
    - 프로젝트 관리 체계 확정
  to_improve:
    - 오후 집중력 저하
  lessons:
    - 오전에 딥워크, 오후에 미팅/리뷰 배치가 효과적
```

#### 일간 회고
```yaml
retrospective:
  completed_ratio: 75%     # 자동 계산 (checklist done/total)
  mood: 4                   # 1-5
  notes: "오전 집중 잘 됐음. 오후 미팅 후 피로."
```

### 4. 완료 처리

기간 종료 시:
1. `status: active` → `status: completed`
2. retrospective 섹션 채우기
3. 다음 기간 목표 생성 제안 (goal-create 연계)

### 5. 태스크 연동

목표 상태 변경 시 관련 태스크도 확인:
- 월간 목표 done → 연결된 tasks.yml 태스크 상태 확인
- 주간 목표 진행률 → 해당 프로젝트 tasks.yml과 대조

## 자동 계산

| 필드 | 계산 방법 |
|------|-----------|
| 일간 `completed_ratio` | checklist done 수 / 전체 수 |
| 주간 진행률 | goals 중 done 비율 |
| 월간 `achievement_rate` | KR current 평균 또는 수동 입력 |

## 주의사항

- 기존 내용을 덮어쓰지 않음 — 해당 필드만 업데이트
- retrospective는 한 번 작성 후 수정 가능 (덮어쓰기 OK — append가 아님)
- `updated_by` + `updated_at` frontmatter 갱신
- 미래 기간 파일은 업데이트 불가 (아직 시작 안 한 기간)
