# Task 생성 가이드

## 핵심 원칙

task = 사용자가 한 일의 **기능 단위**. 세션이 아니라 segment 단위로 사고한다.
이 task만 읽고 코칭할 수 있어야 한다.

## summary 필수 요소: 왜 → 뭘 → 결과

```
[왜 시작했는지] → [구체적으로 한 일] → [어떻게 끝났는지]
```

## 좋은 task 예시

### 예시 1: 여러 segment → 1 task (같은 목표)

여러 세션의 segment들이 하나의 기능을 향한 작업:

```json
{
  "tag": "디버깅",
  "summary": "텔레그램 봇 연결 설정 — .env 설정, /login, pair 코드 디버깅, 플러그인 리로드, access.json 전반 점검. 35분간 시도 후 연결 성공.",
  "repo": "daye-agent-toolkit",
  "segments": [
    {"sid": "abc1", "date": "2026-03-31", "start": "13:22", "end": "13:40", "dur": 18},
    {"sid": "abc2", "date": "2026-03-31", "start": "14:10", "end": "14:27", "dur": 17}
  ],
  "duration_min": 35,
  "status": "completed",
  "project": "텔레그램 봇 설정"
}
```

### 예시 2: 왜/뭘/결과가 명확한 task

```json
{
  "tag": "코딩",
  "summary": "Warp 강제 종료로 모든 CC/Codex 세션 소실 → 데이터 품질 문제 인식(코칭 데이터가 부실하게 쌓이고 있음). 깔끔하게 재설계 결정 → sessions+session_content+daily_stats 스키마 직접 구현, 기존 activities 테이블 대체. 셀프 리뷰 + Codex 리뷰 후 머지 완료.",
  "repo": "life-dashboard",
  "segments": [
    {"sid": "def1", "date": "2026-03-31", "start": "10:00", "end": "12:01", "dur": 121}
  ],
  "duration_min": 121,
  "status": "completed",
  "project": "life-dashboard 스키마 개편"
}
```

왜: Warp crash → 데이터 품질 문제 인식
뭘: 스키마 재설계 + 구현
결과: 머지 완료

### 예시 3: 설계→구현 전체 과정 + 투입 시간

```json
{
  "tag": "코딩",
  "summary": "daily 리포트가 세션 단위로만 보여줘서 하루 작업이 뭉뚱그려지는 문제 → brainstorming → spec/plan 작성 → session_topics 테이블 스키마 + db.py + activity_writer 구현 → extract_session.py 설계 → active_session_scanner 구현 → 디버깅. 설계부터 구현까지 4시간+ 한 세션에서 완료. 중간에 여러 번 리팩토링하면서 지침.",
  "repo": "daye-agent-toolkit",
  "segments": [
    {"sid": "ghi1", "date": "2026-03-31", "start": "09:00", "end": "13:16", "dur": 256}
  ],
  "duration_min": 256,
  "status": "completed",
  "project": "work-digest 파이프라인"
}
```

투입 시간 패턴도 기록: "4시간+ 한 세션", "중간에 여러 번 리팩토링"

### 예시 4: follow_up이 있는 task

```json
{
  "tag": "설정",
  "summary": "에이전트를 원격에서 상시 가동하기 위해 맥미니(romeo) 환경 구축 → tailscale SSH 접속 → OpenClaw 업그레이드 → dy-minions-squad clone → PM봇+로니 에이전트 설정 → 슬랙 봇 채널 연결 → 대화 로깅 시스템 설계(SQLite+hook). 환경 구축 완료, outbound 로깅 미지원 확인.",
  "repo": "dy-minions-squad",
  "segments": [
    {"sid": "jkl1", "date": "2026-03-31", "start": "15:00", "end": "17:30", "dur": 150}
  ],
  "duration_min": 150,
  "status": "completed",
  "follow_up": "outbound 로깅 방식 결정 필요 (handler.js 래핑 vs DB 직접)",
  "project": "romeo 원격 환경"
}
```

### 예시 5: project 연결

```json
{
  "tag": "설계",
  "summary": "동일 리포트 3-4건 중복 발송 문제 확인 → mingming이 태스크를 직접 분석하는 구조적 문제 발견(오케스트레이터가 구체화+할당해야 하는데 직접 수행) → cron.json 규칙 위반 분석 → 오케스트레이터/워커 역할 분리 재설계 → wake 프롬프트에 output_ref 추가 → AGENTS 템플릿 구현 → 부동산 태스크에서 재현 여부 검증 후 머지+빌드. 중복 알림도 해결됨.",
  "repo": "dy-minions-squad",
  "segments": [
    {"sid": "mno1", "date": "2026-03-31", "start": "18:00", "end": "21:19", "dur": 199}
  ],
  "duration_min": 199,
  "status": "completed",
  "project": "오케스트레이터 구조 개편"
}
```

기존 projects 목록에 "오케스트레이터 구조 개편"이 있으면 그대로 사용, 없으면 새 name으로 제시.

## 나쁜 task 예시

```json
{"tag": "코딩", "summary": "cron 수정"}
```
→ 뭘 왜 어떻게 수정했는지 모름. 코칭 불가.

```json
{"tag": "ops", "summary": ".env 설정 후 /login 실행."}
```
→ 명령어 나열. 이게 왜 필요했는지, 결과가 뭔지 없음.

```json
{"tag": "ops", "summary": "/exit 명령 실행."}
```
→ 독립 task이면 안 됨. 인접 task에 포함하거나 삭제.

```json
{"tag": "기타", "summary": "dy-minions-squad 작업"}
```
→ tag "기타", summary 무의미. 이런 task는 만들면 안 된다.

## 그룹핑 기준

**묶는 경우:**
- 같은 레포 + 같은 목표 (hint/files로 판단) → 1 task
- 한 세션의 segments가 여러 task에 분산될 수 있다

**나누는 경우:**
- 다른 레포 → 다른 task
- 같은 레포 + 다른 목표 → 다른 task
- **애매하면 분리.** project 레벨에서 연결되므로 과도한 병합보다 분리가 안전.

**segment 전수 검증:** 모든 input segment가 정확히 1개 task에 할당. 누락·중복 불허.

**단순 명령(/exit, /clear)은 독립 task 금지** — 인접 task에 포함하거나 삭제.

## Signals 예시

task를 만들면서 동시에 추출:

```
task: 오케스트레이터 구조 전면 개편 + 중복 알림 해결

signals:
  [decision] 오케스트레이터/워커 역할 분리 재설계
    → mingming이 직접 분석하는 구조 문제를 역할 분리로 해결

  [mistake] cron.json 규칙 위반 재발 (3번째)
    → rule 존재하는데 에이전트가 무시. 프롬프트로는 부족, 강제 필요

  [pattern] 구조적 문제 → 전면 개편 반복
    → 개별 수정이 아닌 전면 개편으로 해결하는 패턴
```
