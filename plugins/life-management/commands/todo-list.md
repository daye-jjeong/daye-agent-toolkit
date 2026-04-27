---
description: 전체 todo를 단일 테이블로 출력 (한글 7컬럼, 신호등, 완료기준)
allowed-tools: Bash, Read
---

# /todo-list

life-coach todo 시스템의 전체 backlog/wip를 **단일 테이블**로 출력한다. 완료(done) 상태는 제외.

## 실행

1. `python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py list --status backlog` 실행 → JSON
2. `python3 plugins/life-management/skills/life-coach/scripts/todo_crud.py list --status wip` 실행 → JSON
3. 두 결과를 합쳐 아래 형식의 표 1개로 출력

## 표 형식 (정확히 이대로)

### 컬럼 (7개, 모두 한글)

| 🚦 | 번호 | 우선 | 마감 | 프로젝트 | 제목 | 완료기준 |

### 컬럼 의미

- **🚦 신호등**: 🔥 진행중(wip) / 🔴 마감초과(deadline 지남 + !done) / 🟡 마감있음(deadline 있는 backlog) / ⚪ 마감없음(deadline 없는 backlog)
- **번호**: todo id
- **우선**: priority 숫자 (1=높음, 2=중)
- **마감**: `MM-DD (D±N)` 형식 — D+ 지남, D- 남음, D 0 오늘. deadline 없으면 `-`
- **프로젝트**: project_name (DB 그대로). 없으면 `(없음)`
- **제목**: title 그대로
- **완료기준**: `✓` (done_definition 있음) / `❌` (없거나 빈 문자열)

### 정렬

1. 신호등 그룹: 🔥 → 🔴 → 🟡 → ⚪
2. 같은 그룹 내 deadline asc (NULL 뒤)
3. priority asc (1 → 2 → 3)
4. id asc

### 표 아래 추가

- ⚠️ 완료기준 미정 N개: #X, #Y (있을 때만)
- 📊 총 N개 (마감초과 a / 마감있음 b / 마감없음 c / 진행중 d)
- ✅ 완료된 건 별도 요청 시 표시 (안내)

## 금지

- 프로젝트별로 표 나누지 말 것 — **단일 테이블**
- 영어 컬럼명 금지 (`P`/`DoD`/`Status` 등 X)
- done 상태 자동 포함 금지
- 컬럼 추가/제거 자유롭게 하지 말 것 — 사용자가 명시적으로 요청한 형식
