# Correction Protocol

사용자가 행동을 교정하면 즉시 적용 + 저장.

## Trigger
명시적("always X", "never Y"), 반복(2회+), 방향 전환("이건 아니야"), 선호("이게 더 낫다"), 좌절("왜 또 이래").

## 저장
1. 즉시 행동 변경
2. `.claude/rules/correction-{YYYYMMDD}-{HHmm}-{slug}.md` — `{rule}. Why: {reason}`. 1건/파일. 중복 확인
3. Auto memory `corrections/{topic}.md`: `- [YYYY-MM-DD] {before} -> {after} (reason)`
4. Auto memory log `corrections/log/YYYY-MM-DD.md`: `{HH:MM} | {topic} | {summary}`
5. 보고: `Correction saved: Rule: "..." | Topic: ... | Scope: ...`
6. 같은 topic 3+ 반복 → `/enforce` 훅 전환 제안

## Write Gate
기본 저장. Skip: 이미 존재 또는 확실한 1회성. 확신 없으면 저장.
프로젝트 관습 영향 → CLAUDE.md 업데이트 제안. 글로벌 → ~/.claude/CLAUDE.md.
