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
| 출력 | `~/life-dashboard/profile.md` | 누적형, git-tracked |
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
| 시간 패턴 | activities | 요일별/시간대별 세션 분포, 평균 세션 길이, 집중 시간대 |
| 작업 성향 | activities.tag | 태그 비율 (코딩 vs 설계 vs 디버깅 vs ...), 변화 추이 |
| 실수 패턴 | behavioral_signals (mistake) | 실수 유형 빈도, 반복 여부, 교정까지 소요 일수 (mistake signal → correction rule 매칭 가능한 경우만) |
| 의사결정 패턴 | behavioral_signals (decision) | 어떤 상황에서 어떤 선택을 하는지, 결정 빈도 |
| 행동 패턴 | behavioral_signals (pattern) | 반복되는 습관 (좋은 것 + 나쁜 것) |
| 도구/레포 선호 | activities.repo | 레포별 시간 비중, 멀티태스킹 정도 |
| 교정 이력 | correction-memory rules | 어떤 규칙이 생겼는지, 카테고리별 분포 |

### 출력물: profile.md

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
(이전 프로파일 대비 변화. git history로 이전 버전 참조)
```

### 동작 방식

1. **첫 실행**: 프로파일 신규 생성
2. **이후 실행**: 기존 `profile.md`를 읽고 → 최신 데이터와 비교 → 변화 부분 업데이트 + "변화 추이" 기록
3. **커밋** → git history가 타임라인 역할 (별도 아카이빙 불필요)

### collect.py 설계

- `~/life-dashboard/data.db` 쿼리
- 분석 기간: 기본 최근 30일, `--days N` 또는 `--since YYYY-MM-DD` 옵션
- 출력: stdout JSON (LLM이 읽음)
- NULL/빈 tag는 "기타"로 분류
- 쿼리 대상:
  - `activities`: 세션 수, 시간, 태그, 레포, 세션 길이
  - `behavioral_signals`: 유형별 빈도, 내용, 반복 패턴
  - `daily_stats`: 일별 추이
- `.claude/rules/correction-*.md` 파일 수집 (기본: 현재 프로젝트, `--project-root PATH`로 변경 가능)

#### JSON 출력 스키마

```json
{
  "period": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 30 },
  "sessions": {
    "total": 0,
    "avg_duration_min": 0,
    "by_weekday": { "Mon": 0, ... },
    "by_hour": { "0": 0, ... },
    "by_tag": { "코딩": 0, ... },
    "by_repo": { "repo-name": { "count": 0, "total_min": 0 } }
  },
  "behavioral_signals": {
    "decisions": [{ "content": "...", "date": "...", "repo": "..." }],
    "mistakes": [{ "content": "...", "date": "...", "repo": "..." }],
    "patterns": [{ "content": "...", "date": "...", "repo": "..." }],
    "mistake_frequency": { "type": 0 },
    "repeat_signals": [{ "content": "...", "count": 0 }]
  },
  "corrections": [
    { "filename": "...", "created": "YYYY-MM-DD", "content_preview": "..." }
  ],
  "daily_trend": [
    { "date": "...", "sessions": 0, "hours": 0, "tags": {} }
  ]
}
```

### Phase 1 범위 (업무 중심)

**포함:**
- 세션/작업 분석 (시간, 태그, 레포)
- 행동 신호 분석 (결정, 실수, 패턴)
- 교정 이력 분석

**미포함 (Phase 2 이후):**
- 건강-생산성 상관관계
- 커뮤니케이션 스타일 (슬랙/PR 코멘트)
- 소비 패턴
- 위임형 에이전트 전환

### life-coach 연결

- `self-profile`이 `~/life-dashboard/profile.md` 생성
- `life-coach`의 `references/coaching-prompts.md` 서두에 profile.md 참조 지시 추가:
  - 읽는 시점: 코칭 시작 시 항상 `~/life-dashboard/profile.md`를 Read
  - 용도: 페르소나/강점/개선 포인트를 코칭 톤과 내용에 반영
  - fallback: profile.md가 없으면 무시하고 기존 코칭 플로우 유지

### 업데이트 전략

- LLM이 기존 `profile.md` 전문 + 새 `collect.py` JSON을 모두 입력받아 업데이트
- collect.py는 이전 프로파일을 파싱하지 않음 — 비교/해석은 전적으로 LLM 역할
