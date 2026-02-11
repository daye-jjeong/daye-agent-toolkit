# vault-memory:compound

> 야간 자동 compound review — 하루 세션을 리뷰하고 장기 기억에 반영.

**Tier:** 2 (Hybrid) — 스크립트가 데이터 추출, 선택적 LLM 판단
**스크립트:** `scripts/compound_review.py`
**Cron:** `30 22 * * *`

## 트리거

- 자동: 매일 22:30 cron
- 수동: "compound review", "오늘 정리", "야간 리뷰"

## 워크플로우

### 1. 세션 로그 파싱
`memory/YYYY-MM-DD.md`에서 오늘 세션들을 파싱.
각 세션의 카테고리별 항목 추출:
- 결정사항, 핵심 배움, 해결한 문제, 에러/이슈, 미완료/대기

### 2. MEMORY.md 후보 추출
**핵심 배움** 중 장기 보관 가치 있는 항목 식별:
- 재사용 가능한 패턴/지식
- 사용자 선호/습관 발견
- 중요 결정과 그 이유

→ `MEMORY.md` "Lessons Learned" 또는 적절한 섹션에 append.

### 3. AGENTS.md 후보 추출
**결정사항** 중 정책 키워드 포함 항목:
- "항상", "규칙으로", "정책 추가", "매번", "금지", "필수"
- 반복된 실수/패턴 (3회+ 등장)

→ `AGENTS.md` "Learned Lessons" 섹션에 append.

### 4. Git Commit
변경사항이 있으면 자동 커밋:
```
compound: daily review YYYY-MM-DD
```

### 5. 요약 로그
`/tmp/compound_review.log`에 기록:
- 처리한 세션 수
- MEMORY.md 추가 항목 수
- AGENTS.md 추가 항목 수

## 규칙

- **노이즈 방지:** 모든 배움을 다 올리지 않음. 재사용 가치가 명확한 것만.
- **중복 방지:** 기존 MEMORY.md/AGENTS.md에 이미 있는 내용은 스킵.
- **Telegram 무음:** 성공 시 메시지 없음. 실패 시에만 알림.
- **월간 pruning:** 매월 1일, 오래된/중복된 Learned Lessons 정리 제안.

## 연계

- `vault-memory:compress`와 상호보완 (compress=수동 상세, compound=자동 야간)
- compress가 이미 실행된 세션은 compound에서 중복 처리 안 함
- Quick Reference가 이미 있는 날은 compound가 MEMORY.md/AGENTS.md만 처리
