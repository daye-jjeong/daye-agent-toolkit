---
name: goal-planner
description: 월간 → 주간 → 일간 3계층 목표 수립 및 관리
---

# Goal Planner

**Version:** 0.1.0 | **Updated:** 2026-02-10 | **Status:** Active

월간 -> 주간 -> 일간 3계층 목표를 수립하고 관리하는 스킬.
`projects/_goals/` 디렉토리에 YAML 파일을 생성/수정한다.

## 트리거

사용자가 다음을 요청할 때 활성화:
- "이번달/이번주/오늘 계획 세우자"
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

**월간 -> 주간:**
1. 현재 월간 목표 YAML 읽기
2. 이번주 집중 항목 자동 선별 (priority + KR 진행률 기반)
3. 캘린더(iCloud + Google) 일정 확인
4. 주간 목표 드래프트 생성 -> 사용자 확인

**주간 -> 일간:**
1. 현재 주간 목표 YAML 읽기
2. 오늘의 캘린더 일정 + 대기 태스크 확인
3. 시간 블록 + 체크리스트 자동 배치
4. 일간 목표 드래프트 생성 -> 사용자 확인

### 모드 2: 대화형 플래닝 세션

질문하며 함께 목표를 세우는 방식.

**월간 (월초):** 지난달 회고 -> "가장 중요한 것은?" -> 프로젝트별 목표+KR -> 테마 설정
**주간 (월요일):** 월간 목표 중 집중 항목 -> "반드시 끝낼 것은?" -> 일정 고려 조정
**일간 (아침):** 주간 목표+일정 확인 -> "가장 중요한 3가지?" -> 에너지 체크 -> 시간 블록

## YAML 포맷

3계층 (월간/주간/일간) YAML 형식 정의.

**상세**: `{baseDir}/references/yaml-formats.md` 참고

## 자동 드래프트 로직

주간/일간 자동 생성 규칙 및 에너지 레벨 반영 정책.

**상세**: `{baseDir}/references/auto-draft-rules.md` 참고

## 스크립트

```bash
python3 create_goal.py monthly|weekly|daily [--date YYYY-MM-DD] [--dry-run]
python3 create_goal.py retro --type daily|weekly|monthly
```

**상세 (전체 옵션, 크론)**: `{baseDir}/references/auto-draft-rules.md` 참고

## 연동

- **task-dashboard**: 생성된 목표가 대시보드 goals 섹션에 자동 반영
- **daily_goal_brief.py**: 텔레그램 브리핑에서 일간 목표 표시
- **schedule-advisor**: 캘린더 일정 참고하여 time_blocks 배치
- **health-tracker**: 에너지 레벨 데이터 연동 가능
