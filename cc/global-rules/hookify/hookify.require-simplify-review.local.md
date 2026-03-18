---
name: require-simplify-review
enabled: true
event: stop
action: block
pattern: .*
---

🛑 **완료 전 체크리스트**

코드를 수정했다면 완료 선언 전에 반드시 다음을 실행했는지 확인하라:

1. **`/simplify`** — 코드 리뷰 + 정리
2. **PR review** — `/pr-review-toolkit:review-pr` 또는 코드 리뷰 에이전트

둘 다 실행하지 않았다면 지금 실행하라. 코드 수정이 없는 세션(조사/질문만)이면 무시.
