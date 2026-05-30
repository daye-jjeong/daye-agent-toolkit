# Code Review

코드 리뷰는 최소 2 pass:
- Pass 1: per-file (logic, omission, style)
- Pass 2: cross-file (참조, 스케줄 시각, flag명, 분산 문서)

**일관성 체크 필수** — 매 PR 리뷰:
- 네이밍/패턴/컨벤션이 기존 코드와 일치
- 동형 케이스(같은 일 하는 다른 곳)와 같은 모양
- correction 룰 (`.claude/rules/correction-*.md`) 위반 없음

single-pass는 cross-file 불일치를 silently ship.
PR 머지엔 사용자 명시 승인 필수.
