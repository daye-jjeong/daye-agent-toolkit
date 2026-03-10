# Approach — OLD Skill 적용 방식

## 스킬 버전

SKILL.md version: 0.4.0 (2026-03-08)

## 적용 절차

1. `SKILL.md` 읽기 → 일일 코칭 절차 확인
   - `daily_coach.py --json` 실행 → JSON 획득 (시뮬레이션으로 대체)
   - `references/coaching-prompts.md` 적용
2. `references/coaching-prompts.md` 읽기 → 4개 섹션 구조 확인
3. 샘플 데이터를 JSON으로 구성 후 프롬프트 템플릿에 대입
4. 4개 섹션 생성: 오늘의 정리 / 코칭 / 자동화 제안 / 내일 이어할 것

## 사용된 coaching-prompts.md 섹션

- `### 📝 오늘의 정리` — has_commits 기반 완료/진행중 분류
- `### 🔍 코칭` — 패턴 감지(운동 부재, 수면 부족), tone_level=0 (질문형 넛지)
- `### 🤖 자동화 제안` — 반복 패턴 없음 → 섹션 생략
- `### ⏭️ 내일 이어할 것` — has_commits=0인 세션 기준 판단

## 섹션 구성 관찰

- 총 4개 섹션 정의, 조건에 따라 생략 가능 (자동화 제안 생략됨)
- 건강 데이터(수면, 운동)는 "코칭" 섹션에 통합 — 별도 섹션 없음
- 유통기한 알림(토마토 만료)은 coaching-prompts.md에 섹션 정의가 없어 출력에서 누락됨
  → SKILL.md의 "7. 유통기한" 항목과 coaching-prompts.md 간 불일치

## 데이터 → 출력 매핑

| 입력 데이터 | 출력 반영 여부 |
|------------|--------------|
| 세션 3개, 4.2h | 반영 (오늘의 정리) |
| daye-agent-toolkit 완료 (has_commits=1) | 반영 |
| cube-claude-skills 진행중 (has_commits=0) | 반영 |
| token_total 180K | 미반영 (coaching-prompts.md에 토큰 출력 지시 없음) |
| sleep 6.5h | 반영 (코칭 섹션) |
| exercise=false | 반영 (코칭 섹션) |
| pantry_expiry: 토마토 | 미반영 (coaching-prompts.md에 섹션 없음) |

## 이슈 / 갭

1. **유통기한 섹션 누락**: SKILL.md 일일 코칭 구성 7번에 "유통기한" 항목이 있으나 coaching-prompts.md에 해당 섹션 템플릿이 없어 출력에 포함되지 않음.
2. **토큰 사용량 미출력**: SKILL.md 구성 1번에 "토큰 사용량" 포함이 명시되어 있으나 coaching-prompts.md의 "오늘의 정리" 지시에 토큰 언급이 없어 생략됨.
3. **레포별 상세 섹션 누락**: SKILL.md 구성 2번 "레포별 상세"가 coaching-prompts.md에 독립 섹션으로 없고 "오늘의 정리"에 합산됨.
4. **패턴 피드백 섹션 누락**: SKILL.md 구성 4번 "패턴 피드백"이 coaching-prompts.md에 없음 (코칭 섹션에 일부 흡수).
