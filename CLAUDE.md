# daye-agent-toolkit

개인 범용 스킬 전용 레포. Claude Code + OpenClaw 양쪽에서 사용.
외부 마켓플레이스 플러그인도 `skills.json`으로 선언적 관리.

## 접근 방식

| 환경 | 접근 방식 |
|------|-----------|
| Claude Code (로컬) | `./setup.sh` → 마켓플레이스 등록 + 플러그인 설치 + symlink |
| OpenClaw (원격) | `./setup.sh --openclaw` → extraDirs 설정 안내 |

## skills.json 매니페스트

모든 스킬 선언은 `skills.json`에서 관리:

- `local_skills`: 이 레포에 있는 SKILL.md 스킬 이름 배열
- `marketplaces`: 등록할 외부 마켓플레이스 목록
- `plugins`: 설치할 외부 플러그인 목록

새 스킬/플러그인 추가 시 skills.json을 수정하고 `./setup.sh` 재실행.

## 스킬 포맷

- `<skill-name>/SKILL.md` — 스킬 본문 (Claude Code + OpenClaw 공통)
- `<skill-name>/.claude-skill` — 스킬 메타데이터
- `<skill-name>/.claude-plugin/plugin.json` — Claude Code plugin (slash command 필요 시)
- `<skill-name>/commands/*.md` — Claude Code slash command (필요 시)

## 포맷 선택 기준

| 조건 | 포맷 |
|------|------|
| 슬래시 커맨드 불필요 | SKILL.md only |
| 슬래시 커맨드 필요 + OpenClaw도 사용 | Dual (SKILL.md + plugin.json) |
| Claude Code 전용 기능 (hooks, agents) | Plugin only |

## 새 스킬 추가 절차

1. `<skill-name>/` 디렉토리 생성
2. `SKILL.md` + `.claude-skill` 작성
3. slash command 필요 시: `.claude-plugin/plugin.json` + `commands/<name>.md` 추가
4. `skills.json`의 `local_skills`에 스킬 이름 추가
5. Plugin 포맷이면: `.claude-plugin/marketplace.json`의 `plugins`에도 추가
6. `./setup.sh` 실행
7. 커밋 + push (OpenClaw 원격 서버에 자동 반영)

## 외부 플러그인 추가 절차

1. `skills.json`의 `marketplaces`에 마켓플레이스 추가 (필요 시)
2. `skills.json`의 `plugins`에 플러그인 추가
3. `./setup.sh` 실행
4. 커밋

## scripts/ 규칙

- stdlib만 사용 (외부 패키지 금지)
- bash 또는 python3
- `{baseDir}/scripts/` 경로로 SKILL.md에서 참조

## 방침

- cube-claude-skills는 건드리지 않음
- 이 레포는 개인 범용 스킬만 관리
- Cube 업무용 스킬은 cube-claude-skills에 유지
