# daye-agent-toolkit

개인 범용 에이전트 툴킷. standalone 크로스 에이전트 스킬 + 규칙을 관리.

## 접근 방식

`make install` → 스킬 심링크(CC + Codex) + 로컬 마켓플레이스 등록 + 규칙·커맨드 심링크

`make install`은 **메인 레포 루트에서** 실행한다. worktree에서 실행하면 worktree 제거 후 `~/.claude/skills/`·`~/.codex/skills/` 심링크가 dangling 된다(머지 후 메인에서 재실행 필요).

## 레거시 플러그인 (grandfathered)

`plugins/` 아래 4종(life-management, finance, dev-tools, media-fetch)은 유지하되 **신규 스킬은 플러그인으로 만들지 않는다.** 마이그레이션은 범위 밖. 목록은 스킬 카탈로그에 이미 실린다.

## marketplace.json

`.claude-plugin/marketplace.json`이 로컬 마켓플레이스를 정의. `make install`이 이를 `~/.claude/settings.json`에 등록. 레거시 플러그인 4종만 관리하며, standalone 스킬은 marketplace.json을 건드리지 않는다.

## 규칙 시스템

`rules/**/*.md`는 모든 CC 세션에 자동 로드되는 행동 규칙. `rules/global`·`rules/correction`·`rules/tone`으로 나뉘고, `.claude/rules/`는 프로젝트 레벨 오버라이드(git-tracked).

- `make install` → `~/.claude/rules/`에 심링크
- 기존 파일(심링크 아닌)이 있으면 SKIP
- 룰 파일을 지우거나 이름을 바꾸면 심링크가 dangling 된다 → `make install` 재실행

## 커맨드

`commands/*.md`는 슬래시 커맨드. `make install`이 `~/.claude/commands/`에 심링크한다(룰과 같은 방식).

**플러그인(`plugins/*/commands/`)에 넣지 마라.** 플러그인은 `~/.claude/plugins/cache/<플러그인>/<버전>/`으로 **복사**되는데, 이 캐시가 원본을 따라오지 않는다. 2026-08 실측에서 캐시가 두 달 낡아 `life-management`의 커맨드 4개(`/todo-list`·`/morning`·`/evening`·`/capacity`)가 캐시에 아예 없었다. 심링크는 원본을 가리켜 즉시 반영된다.

## 스킬 포맷

신규 standalone 스킬 경로:

- `skills/<skill-name>/SKILL.md` — 스킬 본문 (레포 루트, ≤150줄)
- `skills/<skill-name>/references/` — 상세 문서 (SKILL.md에서 포인터 참조)
- `skills/<skill-name>/scripts/` — 데이터 수집/가공 스크립트 (stdlib만)

frontmatter(`name`/`description`)는 CC·Codex 공통. `make install`이 `~/.claude/skills/` + `~/.codex/skills/`에 심링크.

레거시 플러그인 스킬은 `plugins/<plugin>/skills/...` 구조 그대로 유지(변경 안 함).

### frontmatter 선택 필드

| 필드 | 설명 |
|------|------|
| `user-invocable` | `false`면 슬래시 커맨드 비노출 (내부 스킬) |
| `disable-model-invocation` | `true`면 모델 프롬프트에서 제외 (cron/수동 전용) |

## scripts/ 규칙

- stdlib만 사용 (외부 패키지 금지)
- bash 또는 python3
- 개별 스킬은 자체 `scripts/`를 SKILL.md에서 참조
- 훅(`plugins/*/hooks/*.sh`): 입력은 **stdin JSON + jq** (`INPUT=$(cat); echo "$INPUT" | jq -r '.tool_name'`). `$CLAUDE_TOOL_*` env는 CC가 안 채워 no-op — 이걸 읽는 훅은 아무것도 안 하고 조용히 통과한다. grep은 macOS BSD 호환 `[[:space:]]` (`\s`/`\b` 금지)
- 차단은 `PreToolUse` + `exit 2`만 가능. `PostToolUse`나 `exit 0` 훅은 텍스트만 흘리는 리마인더라, 같은 내용이 룰에 있으면 중복이다
- **LLM subprocess 금지**: 스크립트에서 `claude -p` 등 LLM CLI를 호출하지 마라. 스크립트는 데이터 수집·가공만 하고, LLM이 할 일은 SKILL.md에 적어 세션이 직접 수행한다. CC 안에서는 nested session 에러가 나고 OpenClaw엔 claude CLI가 없다. 예외: 훅 스크립트(`session_logger.py`)는 세션 밖에서 돌아 허용

## 스킬 자동 개선

대화 중 스킬에 개선할 만한 부분이 보이면 사용자에게 한 번 물어보고, 동의하면 알아서 업데이트한다. 작은 개선(SKILL.md 섹션 추가, 규칙 한 줄 추가 등)은 별도 todo로 쌓지 말고 즉시 처리.

- 코드 변경은 worktree에서
- 세션 중엔 feedback memory로 즉시 반영하되, SKILL.md에 옮겨 적은 뒤엔 그 memory를 지운다(중복 로드)
- 머지 후 보고

## 방침

- cube-claude-skills는 건드리지 않음
- 이 레포는 개인 범용 스킬만 관리
- Cube 업무용 스킬은 cube-claude-skills에 유지
- 네이밍: 하이픈(`-`) 통일 (언더스코어 금지)
