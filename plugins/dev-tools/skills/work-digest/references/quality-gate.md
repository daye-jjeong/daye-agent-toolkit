# Gate B-2: 내용 품질 검증 (LLM 자기 검증)

**이 Gate를 건너뛰지 마라.** 스크립트 검증(B-1)은 구조만 본다. 내용이 실제로 유용한지는 여기서 판단한다.

`daily_coach.py --json` 출력의 tasks를 전체 읽고, 아래 체크를 **하나씩** 수행한다. 문제 발견 시 즉시 수정하고 Gate B-1부터 재실행. 모든 항목 통과해야 Phase 2로 진행.

## 체크 1: 기능 단위로 묶여 있는가

task 목록을 위에서 아래로 읽으며 확인:
- 같은 목표의 연속 segment가 쪼개져 있으면 → 1개 task로 병합
- "이 task들을 사용자에게 보여주면, 사용자가 '이건 하나의 작업인데 왜 쪼개져 있어?'라고 할 것인가?" → 그렇다면 병합

병합 시:
```bash
python3 {baseDir}/../../../../mcp/life-dashboard/activity_writer.py update-tasks \
    --date <DATE> --tasks '<병합된 JSON array>'
```

## 체크 2: 불필요 task 없는가

- /exit, /clear, /login, /reload 같은 단순 명령이 독립 task → 인접 task에 포함하거나 삭제
- duration이 비정상 (2분 세션인데 45분으로 표시) → duration_min 수정

## 체크 3: 요약이 코칭에 쓸 수 있는 수준인가

각 task summary를 읽고:
- "이 요약만 보고 코칭할 수 있는가?" — 뭘 했는지, 왜 했는지, 결과가 뭔지
- ".env 설정 후 /login 실행." → 부족. "텔레그램 봇 연결 시도 — 설정 + pair code 디버깅, 실패" → 충분
- 명령어 나열, 파일명만 나열은 부족

## 체크 4: 태그-활동 일치

- 코드 수정했는데 "리뷰", 로그만 봤는데 "코딩" 등
- user_messages를 보고 실제 뭘 했는지 확인

## 체크 5: eval 혼입

- eval 세션 내용이 실제 작업 task에 섞이지 않았는지

## 통과 기준

- **PASS**: 모든 항목 이상 없음 → Phase 2로 진행
- **FAIL**: 하나라도 문제 → 수정 후 Gate B-1부터 재실행 (최대 2회)
- WARN 없음. 애매하면 고쳐라.
