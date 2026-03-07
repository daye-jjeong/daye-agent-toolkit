# Life Coach P2 Implementation Plan

**Status:** Task 1-6 완료, P2.5 리팩토링 남음

## 완료된 작업 (이 세션)

- [x] Task 1-3: daily_coach.py 보강 (토큰, 세션 상세, 패턴 피드백, work-context)
- [x] Task 4: weekly_coach.py 신규 생성
- [x] Task 5: SKILL.md 업데이트 (양쪽)
- [x] Task 6: Cron 전환 (daily_digest retired, coach 활성)
- [x] Simplify 리뷰 (_helpers.py 추출, SQL 최적화, TOCTOU 수정)

## 남은 작업: P2.5 — LLM 호출 아키텍처 리팩토링

**문제:** daily_coach.py, weekly_coach.py가 `claude -p --model haiku`를 subprocess로 호출하여 코칭을 생성한다.
이 설계는:
1. CC 세션 내에서 실행 불가 (nested session 에러)
2. OpenClaw에서 실행 불가 (claude CLI 없음)
3. 스킬의 온디맨드 사용 패턴(`/coach`)과 충돌 — LLM이 직접 코칭해야 하는데 subprocess를 부른다

**해결 방향:**
- Python 스크립트 = **데이터 수집 전용** (SQLite 조회 → JSON 출력)
- 코칭/분석 = **스킬 레이어에서 LLM이 직접 수행** (SKILL.md + coaching-prompts.md)
- cron 자동화 = 템플릿 리포트만 텔레그램 전송 (LLM 코칭 없이) OR 별도 방식

### 구체적 변경사항

1. **daily_coach.py / weekly_coach.py에서 `generate_llm_coaching()` 제거**
   - `--no-llm`이 기본 동작이 됨
   - `subprocess` import, `COACHING_TIMEOUT_SEC`, `generate_llm_coaching()` 함수 삭제
   - `main()`에서 LLM 분기 제거 → 항상 `build_template_report()` 사용

2. **`--json` 플래그 추가**
   - `--json`: 구조화된 JSON 출력 (온디맨드에서 LLM이 읽을 데이터)
   - `--dry-run`: 기존 템플릿 리포트 (사람이 읽는 포맷)
   - (플래그 없음): 템플릿 리포트 → 텔레그램 전송

3. **SKILL.md `/coach` 섹션 보강**
   - 온디맨드 워크플로우: 스크립트 `--json` → LLM이 coaching-prompts.md 프레임 적용 → 대화
   - CC: `/coach` 슬래시 커맨드 → Claude가 직접 수행
   - OpenClaw: agent가 스크립트 실행 → 결과로 코칭

4. **cron은 템플릿만 전송**
   - LLM 코칭 없는 데이터 리포트 (현재 `--no-llm`과 동일)
   - 이미 충분히 정보량 있음 (세션 상세, 토큰, 패턴 피드백, 넛지)
