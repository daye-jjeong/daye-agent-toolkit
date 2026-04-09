# OpenClaw 제거 + CC 플러그인 전환 디자인

## 배경

OpenClaw을 완전히 버리고, 모든 스킬을 Claude Code 플러그인 포맷으로 전환한다.
기존 `cc/` + `shared/` 이원 구조를 도메인별 플러그인으로 재편한다.

## 결정 사항

| 항목 | 결정 |
|------|------|
| OpenClaw | 완전 제거 |
| 플러그인 단위 | 도메인별 4개 |
| 규칙 | `rules/` 최상위 + `~/.claude/rules/` 심링크 |
| cron.json | 참조용 유지, 실행은 `/schedule` |
| 훅 | dev-tools 플러그인 `hooks/`로 이동 + `hooks.json` 선언 필수. 글로벌 settings.json의 절대 경로 훅은 제거 |
| 배포 | 로컬 마켓플레이스 — path는 레포 루트 (`.claude-plugin/marketplace.json`이 루트에 있으므로) |
| MCP 서버 | 플러그인 밖 `mcp/`에 독립 배치 |
| 설치 | Makefile 하나로 통합 (`_infra/` 삭제) |
| Codex CLI | `codex/` 디렉토리 별도 유지 (CC 플러그인 미지원) |

## 최종 디렉토리 구조

```
daye-agent-toolkit/
├── plugins/
│   ├── life-management/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   └── skills/
│   │       ├── health-tracker/
│   │       │   ├── SKILL.md
│   │       │   ├── scripts/
│   │       │   └── references/
│   │       ├── life-coach/
│   │       │   ├── SKILL.md
│   │       │   ├── scripts/
│   │       │   ├── references/
│   │       │   └── cron.json
│   │       ├── pantry-manager/
│   │       │   ├── SKILL.md
│   │       │   └── scripts/
│   │       └── saju-manse/
│   │           ├── SKILL.md
│   │           └── scripts/
│   │
│   ├── finance/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   └── skills/
│   │       ├── spending-manager/
│   │       │   ├── SKILL.md
│   │       │   ├── scripts/
│   │       │   ├── references/
│   │       │   └── cron.json
│   │       ├── investment-manager/
│   │       │   ├── SKILL.md
│   │       │   ├── scripts/
│   │       │   ├── references/
│   │       │   └── cron.json
│   │       └── banksalad-import/
│   │           ├── SKILL.md
│   │           └── scripts/
│   │
│   ├── dev-tools/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── skills/
│   │   │   ├── codex-cli/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── scripts/
│   │   │   ├── gemini-cli/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── scripts/
│   │   │   ├── correction-memory/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── references/
│   │   │   ├── enforce/
│   │   │   │   └── SKILL.md
│   │   │   ├── work-digest/
│   │   │   │   ├── SKILL.md
│   │   │   │   ├── scripts/
│   │   │   │   └── references/
│   │   │   ├── self-profile/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── references/
│   │   │   └── dashboard-content-design/
│   │   │       └── SKILL.md
│   │   └── hooks/
│   │       ├── merge-gate.sh
│   │       ├── worktree-guard.sh
│   │       └── save-compact-state.sh
│   │
│   └── media-fetch/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           ├── reddit-fetch/
│           │   ├── SKILL.md
│           │   └── scripts/
│           ├── youtube-fetch/
│           │   ├── SKILL.md
│           │   └── scripts/
│           └── news-brief/
│               ├── SKILL.md
│               ├── scripts/
│               ├── references/
│               └── cron.json
│
├── rules/
│   ├── global/              ← cc/global-rules/rules/ 에서 이동
│   │   ├── minimal-scope.md
│   │   ├── long-running-backoff.md
│   │   ├── completion-and-commits.md
│   │   ├── review-learning-loop.md
│   │   ├── superpowers-workflow-gates.md
│   │   ├── session-split.md
│   │   ├── before-starting.md
│   │   ├── tdd-on-new-functions.md
│   │   └── review-multipass.md
│   ├── correction/          ← cc/correction-memory/rules/ 에서 이동
│   │   └── correction-protocol.md
│   └── tone/                ← shared/stop-slop-kr/rules/ 에서 이동
│       └── tone-kr.md
│
├── mcp/
│   └── life-dashboard/
│       ├── scripts/
│       ├── references/
│       └── cron.json
│
├── codex/                   ← Codex CLI 전용 스킬 (CC 플러그인 미지원, 기존 유지)
│   └── work-digest/
│
├── .claude/
│   └── rules/               ← 프로젝트 레벨 오버라이드 (기존 유지)
│
├── Makefile
├── CLAUDE.md
└── README.md
```

## 플러그인 구성

### 4개 플러그인

| 플러그인 | 스킬 | 설명 |
|----------|------|------|
| life-management | health-tracker, life-coach, pantry-manager, saju-manse | 건강/생활/코칭 |
| finance | spending-manager, investment-manager, banksalad-import | 금융/소비 |
| dev-tools | codex-cli, gemini-cli, correction-memory, enforce, work-digest, self-profile, dashboard-content-design, stop-slop-kr | 개발 워크플로우 + 훅 + 텍스트 교정 |
| media-fetch | reddit-fetch, youtube-fetch, news-brief | 외부 콘텐츠 수집 |

### plugin.json 포맷

```json
{
  "name": "life-management",
  "description": "건강/생활/코칭 관련 스킬 모음",
  "version": "1.0.0",
  "author": {
    "name": "정다예"
  }
}
```

4개 모두 동일 구조, `name`/`description`만 다름.

## SKILL.md 변경

### 제거

- `metadata.openclaw.requires.bins` — OpenClaw 전용 필드
- `.claude-skill` 파일 — 플러그인 내 자동 발견으로 불필요

### 유지

- frontmatter: `name`, `description`, `argument-hint`
- `user-invocable`, `disable-model-invocation` (해당 스킬만)
- `{baseDir}` 플레이스홀더
- `scripts/`, `references/`, `cron.json` (참조용)

## 설치 흐름 (Makefile)

### `make install`

1. `settings.json`의 `extraKnownMarketplaces`에 로컬 디렉토리 등록
   - source: `directory`, path: **레포 루트** (`.claude-plugin/marketplace.json`이 여기 있으므로)
2. `enabledPlugins`에 4개 플러그인 등록
3. `rules/**/*.md` → `~/.claude/rules/` 심링크
4. `mcp/life-dashboard` → 프로젝트 또는 글로벌 `.mcp.json` 등록
5. 글로벌 `settings.json`에서 기존 절대 경로 훅 제거 (플러그인 `hooks.json`이 대체)

### 훅 구조

`dev-tools` 플러그인에 `hooks/hooks.json`을 생성하여 CC가 자동 등록하도록 한다:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/worktree-guard.sh"}]
      },
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/merge-gate.sh"}]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/work-digest/scripts/session_logger.py"},
          {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/save-compact-state.sh"}
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/work-digest/scripts/session_logger.py"}
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/skills/work-digest/scripts/notify.sh permission"}
        ]
      }
    ]
  }
}
```

프로젝트 레벨 훅(`.claude/settings.json`의 `plan-review-gate.sh`)은 프로젝트 전용이므로 그대로 유지.

### `make clean`

역순으로 제거.

### `make status`

설치 상태 확인 (심링크, 플러그인 등록 여부).

## 삭제 대상

| 대상 | 이유 |
|------|------|
| `cc/` | 플러그인으로 이동 완료 |
| `shared/` | 플러그인으로 이동 완료 |
| `codex/` | Codex CLI 전용 — 별도 유지 (삭제하지 않음) |
| `skills.json` | 플러그인 구조가 대체 |
| `.claude-skill` 파일들 | 플러그인 내 자동 발견 |
| `_infra/` | Makefile로 통합 |
| `stop-slop-kr/` | 스킬 본체(퇴고 모드 포함)를 dev-tools 플러그인으로 이동, 규칙은 `rules/tone/`으로 분리 |

## 마이그레이션 전략 (C: 구조 먼저, 내용 나중에)

1. **플러그인 골격 생성** — `plugins/` 디렉토리 + 4개 `.claude-plugin/plugin.json` + 빈 `skills/`
2. **스킬 이동** — `git mv`로 기존 스킬을 플러그인 구조로 이동
3. **OpenClaw 흔적 제거** — `.claude-skill` 삭제, openclaw 메타데이터 제거, SKILL.md 정리
4. **규칙 이동** — `rules/` 최상위로 이동
5. **MCP 분리** — `mcp/life-dashboard/` 생성
6. **훅 이동** — `_infra/cc/` → `plugins/dev-tools/hooks/`
7. **Makefile 재작성** — 플러그인 등록 + rules 심링크 + mcp 등록
8. **레거시 삭제** — `cc/`, `shared/`, `_infra/`, `skills.json` (`codex/`는 유지)
9. **CLAUDE.md 업데이트** — 새 구조 반영
10. **설치 검증** — `make install` + CC에서 스킬 동작 확인
