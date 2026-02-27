# daye-agent-toolkit

개인 범용 스킬 전용 레포. Claude Code + OpenClaw 양쪽에서 사용.

## 디렉토리 구조

```
shared/       — CC + OpenClaw 양쪽 스킬 (9개)
cc/           — Claude Code 전용 스킬 (7개)
openclaw/     — OpenClaw 전용 스킬 (5개)
_infra/       — 빌드/설치/동기화 스크립트
```

총 21개 스킬.

## Setup

```bash
# Claude Code — symlink 설치
make install-cc

# OpenClaw — symlink 후 minions init 시 자동 등록
ln -s $(pwd) ~/.openclaw/daye-agent-toolkit

# 설치 상태 확인
make status
```

## 동기화

```bash
# OpenClaw PC에서 양방향 git sync
make sync
```

## 새 스킬 추가

1. 카테고리 디렉토리에 `<skill-name>/` 생성 (`shared/`, `cc/`, `openclaw/`)
2. `SKILL.md` 작성 (frontmatter + 150줄 이내)
3. Claude Code용이면 `.claude-skill` 추가 (`cc/` 또는 `shared/`)
4. `make install-cc` 실행
5. 커밋 + push

## 방침

- 개인 범용 스킬만 관리 (Cube 업무용은 cube-claude-skills)
- 네이밍: 하이픈(`-`) 통일, 언더스코어 금지
- `_infra/scripts/`: stdlib만 사용, 외부 패키지 금지
