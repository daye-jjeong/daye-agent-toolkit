# Quality Gates — 코치 데이터 파이프라인 품질 자동 검증 + 자가개선

> 생성: 2026-03-21

## 배경

코치 데이터 파이프라인이 품질 검증 없이 실행되어 사용자에게 깨진 리포트가 전달되는 문제가 반복됨.

실제 발생한 문제:
- session_topics.repo가 NULL → 리포트에 "unknown" 레포 표시
- eval 자동 세션 165건이 리포트에 쓰레기로 노출
- eval 세션이 health-tracker를 실행해 가짜 건강 데이터 DB 오염
- 가짜 건강 데이터 기반으로 코칭 작성 (PT, 메니에르, 마운자로 등)
- 제안 태스크 중복 누적 (사주앱 기획 5건, outbound 로깅 2건 등)
- 1-2분짜리 단순 명령(/exit, /login)이 독립 토픽으로 나열

## 목표

1. 파이프라인 각 단계에서 품질 검증 → 통과해야 다음 단계 진행
2. 자동 수정 가능한 것은 스크립트가 직접 수정
3. LLM이 판단해야 하는 것은 LLM이 직접 검증
4. 반복되는 이슈는 스크립트를 업데이트해서 재발 방지 (자가개선)

## 파이프라인 전체 흐름

```
Step 1 (scanner)
  → Step 2 (요약)
  → Gate A: 미요약 0건 확인 + eval 세션 일괄 처리
  → Step 3 (segments)
  → Step 4 (토픽 생성)
  → Step 5 (저장)
  → Gate B-1: validate_topics.py --fix (구조 검증 + 자동 수정)
  → Gate B-2: LLM 자기 검증 (내용 품질)
  → Phase 2 (코칭 생성)
  → Phase 3 (리포트 생성)
  → Gate C: 리포트 프리뷰 검증 (daily_report.py --validate)
  → 자가개선 루프: 이슈 로그 → 반복 패턴 → 스크립트 업데이트
  → open
```

## Layer 1: Gate A — 요약 품질

### 위치
Step 2 완료 후, Step 3 진입 전.

### 검증 항목
1. `unsummarized --date <DATE>` 재실행 → 0건이어야 통과
2. `-claude` 레포 세션은 LLM 요약 불필요 → tag="eval", summary="자동 스킬 eval 세션"으로 일괄 처리
3. eval 세션이 health/meal/symptom DB에 데이터를 넣었는지 확인 → 있으면 삭제

### eval 세션 판별 기준
`-claude` 레포 = eval. tag 무관. `-claude` 레포의 모든 세션은 자동 eval 처리.

### 자동 수정
- eval 일괄 처리: `update-summary --tag eval`
- 가짜 건강 데이터: eval 세션의 시작~종료 시간 범위와 겹치는 건강 기록(exercises, symptoms, meals) 삭제. 범위가 없으면 created_at ± 5분.

### 실패 시
- 미요약 세션 잔존 → 해당 세션 요약 후 재확인
- 가짜 건강 데이터 → 삭제 후 통과

## Layer 2: Gate B-1 — 구조 검증 (스크립트)

### 위치
Step 5 완료 후.

### 구현
`validate_topics.py --fix --date <DATE>` 실행.

### 검증 항목
| 체크 | 현재 | 추가 |
|------|------|------|
| segment:topic 1:1 | O | eval 세션은 면제 |
| 시간 일치 | O | 변경 없음 |
| tag 유효성 | "기타" 거부 | eval 허용, 나머지 기존대로 |
| summary 길이 | 10자 미만 | 변경 없음 |
| repo NULL | 없음 | **추가** — 부모 세션에서 자동 채움 |
| summary 반복 | 없음 | **추가** — 동일 summary 3건+ 감지 |

### --fix 모드 동작
- repo NULL → 부모 세션의 repo로 채움
- `-claude` 레포 세션 → tag="eval"로 변경 (기존 tag 무관)
- eval 세션은 segment 검증 면제 (시간, 1:1 체크 skip)

### 실패 시
- 자동 수정 가능 → 수정 후 재검증
- 수정 불가 → 에러 출력, 해당 토픽 재생성 후 재검증 (최대 2회)
- 2회 재시도 후에도 실패 → 파이프라인 중단, 사용자에게 에러 보고

## Layer 3: Gate B-2 — 내용 품질 검증 (LLM)

### 위치
Gate B-1 통과 후, Phase 2 진입 전.

### 검증 방법
`daily_coach.py --json` 출력의 topics + sessions(user_messages 포함)를 LLM이 직접 읽고 판단.

### 통과 기준
- **PASS**: 모든 항목 이상 없음 → 다음 Phase로 진행
- **WARN**: 경미한 품질 이슈 (요약이 좀 짧지만 틀리진 않음) → 진행하되 로그 기록
- **FAIL**: 내용 불일치, eval 혼입, 병합 필요 → 수정 후 Gate B-1부터 재실행

### 검증 항목

**1. 토픽-세션 내용 일치**
- 토픽 summary가 세션의 user_messages 내용과 맞는지
- 코드 수정했는데 "리뷰"로 태깅, 확인만 했는데 "코딩"으로 태깅 등

**2. 불필요 분리 병합**
- 같은 레포에서 연속된 5분 미만 세션들이 하나의 맥락이면 → 하나로 묶어 재생성
- 예: login → exit → pair code → reload → access 설정 → "텔레그램 연결 설정 (19min)"

**3. 요약 유용성**
- ".env 설정 후 /login 실행." 수준의 명령어 나열은 부족
- 코칭에 쓸 수 있는 수준: 뭘 했고, 왜, 결과가 뭔지
- 1-2분짜리 단순 명령(/exit, /clear)은 독립 토픽으로 만들지 않음

**4. eval 혼입**
- eval 세션이 실제 작업 토픽에 섞여 있지 않은지

### 수정
- 문제 발견 시 해당 토픽을 수정/병합하고 Gate B-1부터 재실행

## Layer 4: Gate C — 리포트 프리뷰 검증

### 위치
Phase 3 (HTML 생성) 후, `open` 전.

### 구현
`daily_report.py --validate` 플래그 추가. 생성된 HTML을 파싱해서 코드로 체크.

### 검증 항목

| # | 카테고리 | 체크 | 자동수정 |
|---|----------|------|----------|
| 1 | 세션 수 | stats에 eval 세션 포함 여부 | eval 필터링 |
| 2 | 태그 분포 | tag pill에 eval 표시 여부 | eval 제외 |
| 3 | 토큰 수 | eval 토큰 합산 여부 | eval 제외 |
| 4 | 레포명 | "unknown", NULL, 빈 문자열 | 에러 |
| 5 | 건강 데이터 | eval 세션 시간 범위와 겹치는 건강 기록 (주 기준) | 경고 → 삭제 |
| 6 | 건강 데이터 | 가짜 키워드 ("테스트용", "스크립트 검증", "알수없는음식") (보조 기준) | 경고 → 삭제 |
| 7 | 코칭 내용 | 삭제된 건강 데이터를 참조하는 코칭 | 코칭 재생성 |
| 8 | 제안 태스크 | 같은 주제 3건+ 중복 | 경고 → 통합 |
| 9 | 타임라인 | 0분 바, eval 잔존 | eval 필터링 |
| 10 | 빈 섹션 | 데이터 있는데 빈 렌더링 | 에러 |
| 11 | 토픽 품질 | 1-2분 단순 명령 독립 항목 | 경고 (B-2 실패 감지용 2중 체크) |

### 실패 시
- 데이터 문제 → 데이터 수정 → 리포트 재생성 → Gate C 재실행
- 코칭 문제 → 코칭 재생성 → 리포트 재생성
- 코드 문제 → 자가개선 루프로 전달

## Layer 5: 자가개선 루프

### 원칙
- **데이터 수정**: 오늘 데이터만 고침. 매 실행마다.
- **코드 수정**: 같은 유형 이슈 2회 이상 발생 시 스크립트 영구 업데이트.
- **코칭 내용**은 자동 수정 안 함. LLM이 재생성.

### 이슈 로그
Gate C가 잡은 이슈를 `shared/life-coach/references/gate-c-issues.json`에 구조화 기록:
```json
[
  {"date": "2026-03-21", "type": "repo-null", "count": 165, "fix": "db.py auto-fill", "auto_fixed": true},
  {"date": "2026-03-21", "type": "eval-leak", "count": 165, "fix": "daily_report.py eval filter", "auto_fixed": true},
  {"date": "2026-03-21", "type": "fake-health", "count": 13, "fix": "Gate A 삭제", "auto_fixed": true}
]
```
type 필드는 정해진 enum: `repo-null`, `eval-leak`, `fake-health`, `stale-coaching`, `task-dup`, `empty-section`, `trivial-topic`, `tag-mismatch`, `session-missing`.

### 코드 수정 흐름
```
Gate C 이슈 발생
  → gate-c-issues.json에 기록
  → 같은 type이 2일 이상 발생?
    → No: 데이터만 수정, 다음 실행에서 재확인
    → Yes: 스크립트 업데이트 제안
      → 수정할 파일 식별 (validate_topics.py, daily_report.py, db.py 등)
      → 사용자에게 수정 내용 보고 + 승인 요청
      → 승인 후 수정 적용
      → Gate C 재실행으로 검증
```

### 수정 범위 제한
- validate_topics.py, daily_report.py, weekly_report.py, timeline_html.py, _helpers.py, db.py
- 이 외 파일은 자동 수정하지 않음
- SKILL.md는 수정하지 않음 (프로세스 변경은 사용자 승인 필요)

## 코칭 저장 시 태스크 중복 방지

### 현재 문제
`save-task`가 기존 pending 태스크와 중복 체크 없이 매번 새로 생성.

### 수정
SKILL.md에 명시: "같은 주제의 pending 태스크가 이미 있으면 새로 만들지 말고 기존 것의 날짜/설명을 갱신하라."

`activity_writer.py save-task`에 중복 체크 필수화:
- pending 태스크 중 description 앞 5단어가 동일한 것이 있으면 기존 것의 날짜/설명을 업데이트 (신규 생성 안 함)
- LLM 호출 없이 문자열 매칭으로 판단

## 변경 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `cc/work-digest/scripts/validate_topics.py` | --fix 모드, repo NULL 체크, eval 면제, summary 반복 감지 |
| `cc/work-digest/SKILL.md` | Gate A, Gate B-1, Gate B-2 절차 추가 |
| `shared/life-coach/SKILL.md` | Gate C, 자가개선 루프 절차 추가 |
| `shared/life-coach/scripts/daily_report.py` | --validate 플래그, eval 필터 (일부 완료) |
| `shared/life-coach/scripts/timeline_html.py` | eval 필터 (완료) |
| `shared/life-dashboard-mcp/db.py` | repo 자동 채움 (완료), _VALID_TAGS eval 추가 (완료) |
| `shared/life-coach/references/coaching-prompts.md` | 태스크 중복 방지 지침 추가 |
