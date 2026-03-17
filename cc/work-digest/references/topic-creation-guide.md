# 토픽 생성 가이드

## 완성된 토픽 예시

### 좋은 토픽

```json
{
  "tag": "설계",
  "summary": "cron 중복 해결 + 오케스트레이터 위임 전면 개편 — [f9524da1에서 cron 구조 검토 시작됨] mingming 직접 분석 문제, cron.json 규칙 위반 재발(3번째). PROPOSAL 상태 추가, wake routing type 전환, task-refine/review thinking framework. 승인 플로우 설계. AGENTS.md+orchestrator+wake-routing 전면 수정. simplify+PR review 후 머지",
  "repo": "dy-minions-squad",
  "start_at": "2026-03-16T11:33:00+09:00",
  "end_at": "2026-03-16T14:03:00+09:00",
  "duration_estimate_min": 150,
  "status": "completed",
  "follow_up": "cron.json hookify rule 강제 — 프롬프트 규칙으로 3번 실패, 자동 강제 필요"
}
```

왜 좋은가:
- tag(설계)가 실제 활동(구조 설계+수정)과 일치
- summary에 무엇을/왜/결과가 다 있음
- 다른 세션과의 연결 `[f9524da1에서 이어짐]`
- 반복 패턴 명시 "3번째"
- follow_up이 구체적 (뭘 왜 해야 하는지)

### 나쁜 토픽

```json
{
  "tag": "코딩",
  "summary": "cron 수정",
  "repo": "dy-minions-squad",
  "start_at": "2026-03-16T11:33:00+09:00",
  "end_at": "2026-03-16T14:03:00+09:00",
  "duration_estimate_min": 150,
  "status": "completed"
}
```

왜 나쁜가:
- tag(코딩)이 실제(설계)와 불일치
- summary "cron 수정" — 뭘 왜 어떻게 수정했는지 모름
- 세션 간 연결 없음
- follow_up 없음 (completed인데 후속 작업이 있는 경우)

## 여러 작업이 섞인 segment 예시

```json
{
  "tag": "ops",
  "summary": "(1) qa-patrol 멘션 unacked 승인→머지→빌드 (~20분). (2) breaking-alert retry 소진(3/3) 진단 — count 누적 구조, suffix match 충돌, agent 필드 부재 (~30분). (3) cron-registration-unification spec+design, 전면 수정 착수 (~70분). [→5a45a36d로 cron 수정 이어짐]",
  "start_at": "2026-03-16T10:48:00+09:00",
  "end_at": "2026-03-16T12:54:00+09:00",
  "duration_estimate_min": 120,
  "status": "in_progress",
  "follow_up": "cron-registration-unification 구현+테스트 — spec 작성 완료, cron.ts/scan.ts/registry 수정 시작됨"
}
```

왜 좋은가:
- 시간 비중 (~20분, ~30분, ~70분)으로 무게 파악 가능
- 다음 세션 연결 `[→5a45a36d로 이어짐]`
- follow_up이 구체적 (어디까지 됐고 뭐가 남았는지)

## Signals 예시

토픽을 만들면서 동시에 추출:

```
토픽: cron 중복 해결 + 오케스트레이터 개편

signals:
  [decision] PROPOSAL 상태 추가 + wake routing type 전환
    → 오케스트레이터가 직접 실행하는 문제를 구조적으로 해결

  [mistake] cron.json 규칙 위반 재발 (3번째)
    → rule 존재하는데 에이전트가 무시. 프롬프트로는 부족, 강제 필요

  [pattern] 구조적 문제 → 전면 개편 반복 패턴
    → cron 구조, 오케스트레이터 구조 모두 개별 수정이 아닌 전면 개편으로 해결
```
