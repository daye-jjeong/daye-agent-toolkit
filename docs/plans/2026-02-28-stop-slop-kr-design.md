# stop-slop-kr 디자인

한국어 AI 말투 교정 스킬. 번역체, 아첨, 상투어를 제거하고 쉽게 읽히는 한국어로 바꿈.

## Design

### 결정사항

- **이름**: stop-slop-kr
- **위치**: `shared/` (CC + OpenClaw 양쪽)
- **대상 언어**: 한국어 전용
- **교정 강도**: 소프트 (대표 slop만 제거)
- **적용 방식**: rules(항상) + 스킬(퇴고)

### 모드

| 모드 | 언제 | 뭘 하나 |
|------|------|---------|
| **예방** | 항상 (rules) | slop 패턴 안 씀 + 가독성 규칙 따름 |
| **퇴고** | 스킬 호출 시 | 텍스트 받아서 slop 찾고 교정본 제시 |

예방 = 기본 강도. 퇴고 = 더 적극적 (문장 구조 개선, 표 변환 제안 포함).

### 파일 구조

```
shared/stop-slop-kr/
  SKILL.md              ← 핵심 규칙 + 퇴고 모드 (~80줄)
  .claude-skill         ← CC 메타데이터
  rules/
    tone-kr.md          ← 글로벌 rules symlink 소스 (~10줄)
  references/
    phrases.md          ← 금지 표현 목록 (카테고리별)
    examples.md         ← Before/After 예시
```

`make install-cc` 시 `rules/tone-kr.md` → `~/.claude/rules/tone-kr.md` symlink.

### rules 최소 규칙 (tone-kr.md, ~10줄)

항상 적용. context 최소화.

하지 마라:
- 과장 아첨: "좋은 질문이에요!", "핵심을 찌르셨네요"
- 마무리 상투어: "도움이 되셨길 바랍니다", "더 궁금한 점 있으시면"
- 번역체: "~를 탐색하다", "심층적으로 들여다보면"
- 후속 제안 남발: "원하시면 ~~~해드릴까요?"
- 불필요한 이모지

해라:
- 바로 본론부터
- 짧고 직접적인 문장
- 자연스러운 한국어 종결어미

### SKILL.md 핵심 내용

1. **금지 표현** → references/phrases.md 포인터
2. **구조 패턴 금지**: 삼중 나열, 리스트/볼드 남발, 수사적 질문-답변
3. **가독성 규칙**:
   - 표로 정리할 수 있으면 표로
   - 한 문장 2줄 넘기지 마
   - 어려운 말 대신 쉬운 말
   - 핵심 먼저, 배경은 나중에
4. **교정 원칙**: 정보 유지 + 말투만 바꿈, 번역체→자연스러운 한국어, 군더더기 삭제
5. **퇴고 모드 절차**: slop 감지 → 교정본 → 변경점 설명

### references/phrases.md 카테고리

| 카테고리 | 예시 | 대체 |
|----------|------|------|
| 아첨 | "좋은 질문이에요" | (삭제) |
| 아첨 | "핵심을 찌르셨네요" | (삭제) |
| 번역체 | "~를 탐색하다" | "살펴보다" |
| 번역체 | "심층적으로" | "자세히" |
| 상투어 | "도움이 되셨길" | (삭제) |
| 상투어 | "더 궁금한 점 있으시면" | (삭제) |
| 과장 | "혁명적인" | (구체적 표현) |
| 후속제안 | "원하시면 ~해드릴까요?" | (삭제/필요시만) |

### 배포

- Makefile `install-cc`에 rules 자동 발견 + symlink 로직 추가
  - `shared/*/rules/*.md` + `cc/*/rules/*.md` → `~/.claude/rules/<filename>` symlink
  - 스킬 폴더 안에 `rules/` 있으면 자동으로 처리됨
- `make clean`에도 rules symlink 제거 추가
- OpenClaw: `shared/`에 있으므로 자동 인식

### 기존 rules 마이그레이션

`.claude/rules/correction-protocol.md`를 `cc/correction-memory/rules/`로 이동.
이 파일은 correction-memory 스킬의 항상-적용 규칙이므로 스킬과 함께 관리하는 게 맞음.

| 파일 | 이동 | 이유 |
|------|------|------|
| `correction-protocol.md` | → `cc/correction-memory/rules/` | correction-memory 스킬 소속 |
| `superpowers-workflow-gates.md` | 그대로 | 외부 플러그인 오버라이드, 스킬 소속 아님 |

### 리서치 출처

- [stop-slop (영어, Claude Code 스킬)](https://github.com/hardikpandya/stop-slop) — 3계층 구조 참고
- [나무위키 AI 아첨 밈](https://namu.wiki/w/%EC%99%80...%20%EB%84%88%20%EC%A0%95%EB%A7%90,%20**%ED%95%B5%EC%8B%AC%EC%9D%84%20%EC%B0%94%EB%A0%80%EC%96%B4.**) — 한국어 패턴 목록
- [모비인사이드 ChatGPT 프롬프트](https://www.mobiinside.co.kr/2025/09/01/chatgpt-prompt/) — 교정 기법
