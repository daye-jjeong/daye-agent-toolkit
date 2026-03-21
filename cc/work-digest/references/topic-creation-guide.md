# 토픽 생성 가이드

## 핵심 원칙

토픽 = 사용자가 한 일의 **기능 단위**. 이 토픽만 읽고 코칭할 수 있어야 한다.

## summary 필수 요소: 왜 → 뭘 → 결과

```
[왜 시작했는지] → [구체적으로 한 일] → [어떻게 끝났는지]
```

## 좋은 토픽 예시

### 예시 1: 기능 단위 병합 (연속 세션 → 1토픽)

5개 세션(login, exit, pair code, reload, access 설정)이 있지만 하나의 기능:

```json
{
  "tag": "디버깅",
  "summary": "텔레그램 봇 연결 설정 — .env 설정, /login, pair 코드 디버깅, 플러그인 리로드, access.json 전반 점검. 35분간 시도 후 연결 성공.",
  "start_at": "13:22",
  "end_at": "15:07",
  "duration_min": 35,
  "status": "completed"
}
```

나머지 4개 세션에는 토픽을 만들지 않는다.

### 예시 2: 왜/뭘/결과가 명확한 토픽

```json
{
  "tag": "코딩",
  "summary": "Warp 강제 종료로 모든 CC/Codex 세션 소실 → 데이터 품질 문제 인식(코칭 데이터가 부실하게 쌓이고 있음). 깔끔하게 재설계 결정 → sessions+session_content+daily_stats 스키마 직접 구현, 기존 activities 테이블 대체. 셀프 리뷰 + Codex 리뷰 후 머지 완료.",
  "duration_estimate_min": 121,
  "status": "completed"
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
  "duration_estimate_min": 256,
  "status": "completed"
}
```

투입 시간 패턴도 기록: "4시간+ 한 세션", "중간에 여러 번 리팩토링"

### 예시 4: follow_up이 있는 토픽

```json
{
  "tag": "설정",
  "summary": "에이전트를 원격에서 상시 가동하기 위해 맥미니(romeo) 환경 구축 → tailscale SSH 접속 → OpenClaw 업그레이드 → dy-minions-squad clone → PM봇+로니 에이전트 설정 → 슬랙 봇 채널 연결 → 대화 로깅 시스템 설계(SQLite+hook). 환경 구축 완료, outbound 로깅 미지원 확인.",
  "status": "completed",
  "follow_up": "outbound 로깅 방식 결정 필요 (handler.js 래핑 vs DB 직접)"
}
```

### 예시 5: 구조 문제 발견 + 해결

```json
{
  "tag": "설계",
  "summary": "동일 리포트 3-4건 중복 발송 문제 확인 → mingming이 태스크를 직접 분석하는 구조적 문제 발견(오케스트레이터가 구체화+할당해야 하는데 직접 수행) → cron.json 규칙 위반 분석 → 오케스트레이터/워커 역할 분리 재설계 → wake 프롬프트에 output_ref 추가 → AGENTS 템플릿 구현 → 부동산 태스크에서 재현 여부 검증 후 머지+빌드. 중복 알림도 해결됨.",
  "duration_estimate_min": 199,
  "status": "completed"
}
```

## 나쁜 토픽 예시

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
→ 독립 토픽이면 안 됨. 인접 기능에 포함하거나 삭제.

```json
{"tag": "기타", "summary": "dy-minions-squad 작업"}
```
→ tag "기타", summary 무의미. 이런 토픽은 만들면 안 된다.

## 병합 기준

**묶는 경우:**
- 같은 레포에서 같은 목표를 향한 연속 작업 (세션이 달라도)
- 짧은 세션들이 하나의 맥락 (login→exit→pair code = "텔레그램 연결")
- 설계→구현→리뷰가 하나의 기능이면 하나의 토픽

**나누는 경우:**
- 다른 레포 (보통 다른 목표)
- 같은 레포라도 명확히 다른 목표
- 30분 이상 gap 후 다른 작업으로 전환

**저장 방식:**
- 병합된 토픽은 대표 세션(가장 긴 세션 또는 첫 세션)에 저장
- 나머지 세션에는 토픽을 만들지 않음
- 단순 명령(/exit, /clear)은 독립 토픽 금지 — 인접 토픽에 포함하거나 삭제

## Signals 예시

토픽을 만들면서 동시에 추출:

```
토픽: 오케스트레이터 구조 전면 개편 + 중복 알림 해결

signals:
  [decision] 오케스트레이터/워커 역할 분리 재설계
    → mingming이 직접 분석하는 구조 문제를 역할 분리로 해결

  [mistake] cron.json 규칙 위반 재발 (3번째)
    → rule 존재하는데 에이전트가 무시. 프롬프트로는 부족, 강제 필요

  [pattern] 구조적 문제 → 전면 개편 반복
    → 개별 수정이 아닌 전면 개편으로 해결하는 패턴
```
