# daye-agent-toolkit

Daye's personal agent toolkit — general-purpose skills for Claude Code and OpenClaw.

`skills.json` 매니페스트로 로컬 스킬 + 외부 플러그인을 선언적으로 관리.
새 머신에서 `./setup.sh`만 실행하면 전체 스킬 환경 재현.

## Setup

### Claude Code (로컬)

```bash
# 전체 환경 설치 (마켓플레이스 등록 + 플러그인 설치 + symlink)
./setup.sh

# 설치 상태 확인
./setup.sh --status
```

### OpenClaw (원격 서버)

```bash
# 1. 레포 클론
git clone https://github.com/daye-jjeong/daye-agent-toolkit.git ~/daye-agent-toolkit

# 2. extraDirs 설정 안내 보기
./setup.sh --openclaw

# 3. (선택) cron으로 자동 동기화
# */30 * * * * cd ~/daye-agent-toolkit && git pull --ff-only
```

## skills.json

```json
{
  "local_skills": ["my-skill"],
  "marketplaces": [
    { "name": "some-marketplace", "source": "github", "repo": "owner/repo" }
  ],
  "plugins": [
    { "marketplace": "some-marketplace", "name": "some-plugin" }
  ]
}
```

## Skills

현재 로컬 스킬 없음. 추후 선택적으로 추가.

## Cleanup

```bash
./setup.sh --clean
```
