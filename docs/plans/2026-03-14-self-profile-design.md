# Self-Profile 스킬 디자인

## Design

### 목적
수주~수개월간의 업무 데이터를 종합 분석하여 "나는 어떤 사람인가"를 정량 + 서술형으로 프로파일링하는 스킬.
life-coach(단기 코칭)와 분리된 **장기 자기 인식** 도구.

### 핵심 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| 위치 | `shared/self-profile/` | CC + OpenClaw 양쪽 사용 |
| 데이터 수집 | `collect.py` → JSON 출력 | 스킬 패턴 준수 (스크립트=데이터, LLM=분석) |
| 분석 | LLM이 SKILL.md 프레임워크로 해석 | subprocess LLM 금지 규칙 |
| 출력 | `~/life-dashboard/profile.md` (산출물) + `profile-snapshot.json` (진실 원천) | 드리프트 방지 |
| 개선 루프 | A/B 제시 → 사용자 수동 적용 | "이해"와 "변경"을 분리 |
| life-coach 연결 | life-coach가 profile.md 참조 | 코칭 개인화 |

### 스킬 구조

```
shared/self-profile/
├── SKILL.md                        # 분석 프레임워크 + 프로파일 작성 가이드
├── .claude-skill                   # CC 메타데이터
├── scripts/
│   └── collect.py                  # DB 쿼리 → 정량 데이터 JSON 출력
└── references/
    └── profile-dimensions.md       # 분석 차원 상세 정의
```

### 분석 차원

| 차원 | 데이터 소스 | 뽑는 것 |
|------|------------|---------|
| 시간 패턴 | activities | 요일별/시간대별 세션 분포 (건수 + 시간), 평균 세션 길이, 집중 시간대 |
| 작업 성향 | activities.tag | 태그 비율 (건수 + 시간 기준 둘 다), 변화 추이 |
| 실수 패턴 | behavioral_signals (mistake) | 실수 유형 빈도, 반복 여부 |
| 의사결정 패턴 | behavioral_signals (decision) | 어떤 상황에서 어떤 선택을 하는지, 결정 빈도 |
| 행동 패턴 | behavioral_signals (pattern) | 반복되는 습관 (좋은 것 + 나쁜 것) |
| 도구/레포 선호 | activities.repo, activities.source | 레포별/소스별 시간 비중, 멀티태스킹 정도 |
| 교정 이력 | correction-memory rules (다중 프로젝트) | 어떤 규칙이 생겼는지, 카테고리별 분포 |

### 출력물

#### 1. profile-snapshot.json (진실 원천)

`collect.py`가 매 실행 시 `~/life-dashboard/profile-snapshot.json`에 저장.
변화 비교는 항상 이전 snapshot JSON 대비 현재 snapshot JSON으로 수행.
LLM 서술의 재해석이 아닌 원본 데이터 기반 비교.

#### 2. profile.md (산출물)

```markdown
# 다예 업무 프로파일
> 생성: YYYY-MM-DD | 분석 기간: YYYY-MM-DD ~ YYYY-MM-DD

## 정량 요약
(숫자 중심: 세션 수, 평균 길이, 시간대, 태그 비율 등)
(차트는 /tmp/에 생성 후 open — 일회성 표시. profile.md에는 텍스트 요약만 기록)

## 페르소나
(데이터 기반 서술형 인물 묘사)

## 강점
(데이터가 뒷받침하는 강점 나열)

## 개선 포인트
(각 항목마다:)
- 근거: 데이터에서 N회 관찰
- 현재 방식: ...
- 제안 방식: ...
- 적용: 규칙/스킬 변경 제안

## 변화 추이
(이전 snapshot 대비 변화. 정량 diff 기반)
```

`~/life-dashboard/`는 별도 git repo가 아님. profile.md는 untracked 산출물.
변화 추적은 snapshot JSON diff로 수행 (git history 불필요).

### 동작 방식

1. **첫 실행**: collect.py → snapshot JSON 저장 → LLM이 profile.md 생성
2. **이후 실행**: collect.py → 새 snapshot JSON 생성 → LLM이 이전 snapshot + 새 snapshot + 기존 profile.md를 읽고 업데이트
3. 이전 snapshot은 `profile-snapshot.prev.json`으로 백업 후 덮어쓰기

### collect.py 설계

- `~/life-dashboard/data.db` 쿼리
- 분석 기간: 기본 최근 30일, `--days N` 또는 `--since YYYY-MM-DD` 옵션
- 출력: stdout JSON (LLM이 읽음) + `~/life-dashboard/profile-snapshot.json` 파일 저장
- NULL/빈 tag는 "기타"로 분류
- 쿼리 대상:
  - `activities`: 세션 수, 시간, 태그, 레포, 세션 길이 (source별 구분 포함)
  - `behavioral_signals`: 유형별 빈도, 상위 20개 + 빈도 집계 (전문 배열 아님)
  - `daily_stats` + 0-fill: 기간 내 모든 날짜 포함 (무활동일 = 0)
- 교정 이력 수집: `~/git_workplace/*/.claude/rules/correction-*.md` (다중 프로젝트)
  - 생성일 기준: 파일명 타임스탬프 (`correction-YYYYMMDD-HHmm-*.md`)
  - `--project-roots PATH1,PATH2`로 커스텀 가능

#### JSON 출력 스키마

```json
{
  "period": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 30 },
  "sessions": {
    "total": 0,
    "avg_duration_min": 0,
    "by_weekday": { "Mon": { "count": 0, "total_min": 0 }, "..." : "..." },
    "by_hour": { "0": { "count": 0, "total_min": 0 }, "..." : "..." },
    "by_tag": { "코딩": { "count": 0, "total_min": 0 }, "..." : "..." },
    "by_repo": { "repo-name": { "count": 0, "total_min": 0 } },
    "by_source": { "cc": { "count": 0, "total_min": 0 }, "codex": { "count": 0, "total_min": 0 } }
  },
  "behavioral_signals": {
    "summary": {
      "decisions_count": 0,
      "mistakes_count": 0,
      "patterns_count": 0
    },
    "top_decisions": [{ "content": "...", "date": "...", "repo": "..." }],
    "top_mistakes": [{ "content": "...", "date": "...", "repo": "..." }],
    "top_patterns": [{ "content": "...", "date": "...", "repo": "..." }],
    "repeat_signals": [{ "content": "...", "count": 0, "type": "..." }]
  },
  "corrections": [
    { "filename": "...", "created": "YYYY-MM-DD", "project": "...", "content_preview": "..." }
  ],
  "daily_trend": [
    { "date": "...", "sessions": 0, "hours": 0.0, "tags": {} }
  ]
}
```

- `behavioral_signals`의 `top_*` 배열은 각 최대 20개 (프롬프트 크기 관리)
- `daily_trend`는 기간 내 모든 날짜 포함 (무활동일은 `sessions: 0, hours: 0.0`)
- `by_weekday`, `by_hour`, `by_tag` 모두 건수 + 시간 이중 기록 (시간 왜곡 방지)

### Phase 1 범위 (업무 중심)

**포함:**
- 세션/작업 분석 (시간, 태그, 레포, 소스별)
- 행동 신호 분석 (결정, 실수, 패턴)
- 교정 이력 분석 (다중 프로젝트)

**미포함 (Phase 2 이후):**
- 건강-생산성 상관관계
- 커뮤니케이션 스타일 (슬랙/PR 코멘트)
- 소비 패턴
- 위임형 에이전트 전환
- mistake↔correction 구조적 연결 (스키마 변경 필요)

### life-coach 연결

- `self-profile`이 `~/life-dashboard/profile.md` 생성
- `life-coach`의 `references/coaching-prompts.md` 서두에 profile.md 참조 지시 추가:
  - 읽는 시점: 코칭 시작 시 항상 `~/life-dashboard/profile.md`를 Read
  - 용도: 페르소나/강점/개선 포인트를 코칭 톤과 내용에 반영
  - fallback: profile.md가 없으면 무시하고 기존 코칭 플로우 유지

### 업데이트 전략

- LLM이 이전 `profile-snapshot.json` + 새 `profile-snapshot.json` + 기존 `profile.md`를 입력받아 업데이트
- 변화 비교는 snapshot JSON 간 diff (원본 데이터 기반, LLM 서술 재해석 아님)
- collect.py는 이전 프로파일을 파싱하지 않음 — 비교/해석은 전적으로 LLM 역할
