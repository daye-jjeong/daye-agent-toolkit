# Correction Protocol (Auto-loaded every session)

사용자가 행동을 교정하면 즉시 이 프로토콜 적용. `/correction-memory` 호출 불필요.

## Trigger Detection (넓게 감지)

- 명시적 지시: "always X", "never Y", "X 대신 Y"
- 반복: 같은 지시 2회+
- 방향 전환: "이건 아니야", "그거 말고", "다시 해봐"
- 선호 표현: "이게 더 낫다", "이렇게 해줘", "이건 별로야"
- 불만/좌절: "왜 또 이래", "아까 말했는데", 같은 실수 지적

## 저장 절차

1. **즉시 적용** — 현재 세션에서 바로 행동 변경
2. **Layer 1 (Rules)** — `.claude/rules/correction-{YYYYMMDD}-{HHmm}-{slug}.md`
   - 파일당 1건. `{rule}. Why: {reason}` 형식. why 필수.
   - 중복 확인 후 생성. 50+ 파일이면 `/correction-memory review` 제안.
3. **Layer 2 (Register)** — auto memory `corrections/{topic}.md`
   - `- [YYYY-MM-DD] {before} -> {after} (reason)`
4. **Layer 3 (Log)** — auto memory `corrections/log/YYYY-MM-DD.md`
   - `{HH:MM} | {topic} | {summary}`
5. **보고** — `Correction saved: Rule: "..." | Topic: ... | Scope: ...`

## Write Gate

**기본은 저장.** 다음일 때만 skip:
- 이미 `.claude/rules/` 또는 CLAUDE.md에 존재
- 정말로 1회성인 게 확실 (확신 없으면 저장)

프로젝트 관습에 영향 → CLAUDE.md 업데이트도 제안 (사용자 확인 후).
글로벌 교정 → `~/.claude/CLAUDE.md` 추가 제안.
