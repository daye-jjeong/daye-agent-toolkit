# 캐시 유지 (Cache Keepalive)

백그라운드 에이전트(Codex 등)를 돌리고 내가 idle 상태일 때, prompt cache TTL 만료를 방지하라.

## 조건

- 백그라운드 에이전트가 실행 중이고
- 내가 그 결과를 기다리며 다른 작업이 없을 때

## 방법

1. `CronCreate`로 `*/4 * * * *` recurring job 등록. prompt: `캐시 유지용 ping. 'ok'만 출력하고 끝내.`
2. 백그라운드 작업 완료 후 즉시 `CronDelete`로 해당 job 삭제

## 원리

Claude API prompt cache TTL은 5분. 캐시 히트마다 리셋. 4분 간격 ping이 프리픽스 캐시를 히트시켜 만료 방지.

Why: 백그라운드 에이전트 대기 중 5분+ idle → 캐시 만료 → 다음 요청에서 전체 프리픽스 재처리 = 토큰 낭비.
