# daye-agent-toolkit

개인 범용 에이전트 툴킷. standalone 크로스 에이전트 스킬 + 규칙을 관리.

## 접근 방식

`make install` → 스킬 심링크(CC + Codex) + 로컬 마켓플레이스 등록 + 규칙·커맨드·훅 심링크 + 플러그인 캐시 제거

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

## 플러그인 캐시 — 만들지 않는다

CC는 플러그인을 `~/.claude/plugins/cache/daye-agent-toolkit/<플러그인>/<버전>/`으로 **복사**한다. 이 복사본은 원본을 따라오지 않는다. 버전이 `1.0.0` 그대로면 재복사할 이유가 없어서다. 2026-08 실측에서 캐시가 4월 9일자로 4개월 낡아 있었고, 그 하나가 여러 증상을 냈다 — 커맨드 4개 미로드, 삭제한 스킬 2개 잔존, 옮긴 `session_logger.py` 크래시, `auto-format.sh` 무동작.

**캐시가 없으면 CC가 레포 원본을 직접 읽는다.** 마켓플레이스가 `source: directory`이고 `installLocation`이 레포 루트라서다(2026-08-07 실측: 캐시를 지운 뒤 스킬·커맨드·훅 전부 원본에서 정상 동작). 그러니 캐시는 **만들지 않는 게 답이다.**

- `make install` → 캐시 디렉토리 삭제
- `make status` → 캐시가 되살아났으면 경고
- CC가 재생성하면 다음 `make install`이 다시 지운다. 그 사이엔 낡은 복사본이 원본을 가린다

`installed_plugins.json`의 `installPath`는 없어진 캐시 경로를 계속 가리키지만 무시된다. CC 내부 파일이라 손대지 않는다.

## 커맨드

`commands/*.md`는 슬래시 커맨드. `make install`이 `~/.claude/commands/`에 심링크한다(룰과 같은 방식). 플러그인에 속한 커맨드(`/morning`·`/evening`·`/capacity`·`/todo-list`)는 `plugins/life-management/commands/`에 그대로 둔다 — 캐시가 없으면 원본이 읽힌다.

기준: **플러그인과 무관한 범용 커맨드만 `commands/`에.** 소속이 있으면 그 플러그인에 둔다.

## life-dashboard DB

진짜 DB는 **`~/life-dashboard/data.db`**다(`mcp/life-dashboard/db.py`의 `DB_PATH`). 2026-08 기준 16MB, 세션 3,653건.

레포 안 `mcp/life-dashboard/data.db`는 **0바이트 잔재**이고 git에도 없다. 아무도 안 읽는다 — 이걸 보고 "DB가 비었다"고 판단하지 마라(실제로 그런 오진이 있었다).

## 훅

훅이 사는 곳은 둘이고 등록 방식이 다르다.

| | `hooks/` | `plugins/*/hooks/` |
|---|---|---|
| 등록 | `~/.claude/settings.json`에 직접 | 플러그인 `hooks.json` |
| 반영 | `make install`이 심링크 | 캐시 없을 때 원본 직접 |
| 끄기 | settings.json에서 제거 | 플러그인을 끄면 같이 꺼짐 |

**플러그인을 꺼도 돌아야 하는 훅은 `hooks/`에 둔다.** 현재 `hooks/`에 3개(`context-monitor.py`·`filter-verbose-output.sh`·`session_logger.py`), `dev-tools`에 2개(`auto-format.sh`, `notify.sh`).

훅을 새로 만들거나 옮기면 **읽는 쪽이 있는지 먼저 확인한다.** `save-compact-state.sh`는 `~/.claude/compact-state.json`을 4개월 썼는데 읽던 `enforce` 스킬이 사라진 뒤로도 계속 돌았다.

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
| `disable-model-invocation` | `true`면 모델 프롬프트에서 제외 + **`Skill` 도구 호출도 차단**. 슬래시로만 부를 수 있다 — 다른 스킬·커맨드가 이걸 호출하도록 설계하면 그 지점에서 멈춘다 (2026-08 실측) |

## scripts/ 규칙

- stdlib만 사용 (외부 패키지 금지)
- bash 또는 python3
- 개별 스킬은 자체 `scripts/`를 SKILL.md에서 참조
- 훅(`hooks/`·`plugins/*/hooks/`): 입력은 **stdin JSON + jq** (`INPUT=$(cat); echo "$INPUT" | jq -r '.tool_name'`). `$CLAUDE_TOOL_*` env는 CC가 안 채워 no-op — 이걸 읽는 훅은 아무것도 안 하고 조용히 통과한다. grep은 macOS BSD 호환 `[[:space:]]` (`\s`/`\b` 금지)
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
