# daye-agent-toolkit 레포 구조 재설계

- Date: 2026-02-27
- Status: Approved

## 배경

- 25+ 스킬 디렉토리가 루트에 flat하게 나열 (분류 없음)
- 인프라 파일(_cc/, scripts/, docs/)이 스킬과 섞여있음
- OpenClaw이 extraDirs로 레포 전체를 스캔 → 비스킬 디렉토리도 스킬로 인식 시도
- setup.sh 295줄 모놀리식, ENABLED_SKILLS에 존재하지 않는 스킬 다수
- 향후 OpenClaw을 별도 PC로 분리 예정

## 제약사항

- OpenClaw extraDirs는 **1단계만 스캔** (재귀 불가)
- OpenClaw extraDirs는 배열로 여러 디렉토리 지원
- SKILL.md가 스킬 식별 파일 (.claude-skill은 CC 전용)

## 디렉토리 구조

```
daye-agent-toolkit/
├── shared/                    ← CC + OpenClaw 양쪽 (9개)
│   ├── banksalad-import/
│   ├── health-coach/
│   ├── health-tracker/
│   ├── investment-report/
│   ├── investment-research/
│   ├── meal-tracker/
│   ├── news-brief/
│   ├── pantry-manager/
│   └── saju-manse/
│
├── cc/                        ← Claude Code 전용 (7개)
│   ├── correction-memory/
│   ├── mermaid-diagrams/
│   ├── professional-communication/
│   ├── reddit-fetch/
│   ├── skill-forge/
│   ├── work-digest/
│   └── youtube-fetch/
│
├── openclaw/                  ← OpenClaw 전용 (9개, 정리 후 결정)
│   ├── check-integrations/
│   ├── elon-thinking/
│   ├── model-health-orchestrator/
│   ├── notion/
│   ├── openclaw-docs/
│   ├── orchestrator/
│   ├── proactive-agent/
│   ├── prompt-guard/
│   └── quant-swing/
│
├── _infra/                    ← 인프라 (스킬 아님)
│   ├── scripts/
│   │   ├── sync.py
│   │   └── setup_env.py
│   ├── cc/
│   │   └── statusline.sh
│   └── docs/
│       └── plans/
│
├── .claude/
├── .claude-plugin/
├── Makefile                   ← setup.sh 대체
├── skills.json                ← 매니페스트 (구조 업데이트)
├── CLAUDE.md
├── README.md
└── .gitignore
```

## 환경별 동작

| 환경 | 방식 | 스킬 소스 |
|------|------|-----------|
| Claude Code (이 Mac) | symlink → ~/.claude/skills/ | shared/* + cc/* |
| OpenClaw (이 Mac, 임시) | symlink ~/.openclaw/daye-agent-toolkit | shared/* + openclaw/* |
| OpenClaw (별도 PC) | git clone + make sync | shared/* + openclaw/* |

## Makefile 타겟

| 타겟 | 설명 |
|------|------|
| make init | 인터랙티브 환경설정 (setup_env.py) |
| make install-cc | Claude Code: shared/ + cc/ symlink |
| make install-oc | OpenClaw: extraDirs 설정 + enable/disable |
| make clean | symlink 제거 |
| make sync | git push/pull (OpenClaw PC용) |
| make status | 현재 설치 상태 |

## OpenClaw config 변경

```json
"skills": {
  "load": {
    "extraDirs": [
      "~/.openclaw/core-skills",
      "~/.openclaw/daye-agent-toolkit/shared",
      "~/.openclaw/daye-agent-toolkit/openclaw"
    ]
  }
}
```

## skills.json 변경

```json
{
  "cc_skills": ["shared/*", "cc/*"],
  "openclaw_skills": ["shared/*", "openclaw/*"],
  "marketplaces": [...],
  "plugins": [...]
}
```

## 마이그레이션 고려사항

1. git mv로 이동하여 히스토리 추적
2. 기존 symlink: make clean 후 make install-cc로 재생성
3. OpenClaw symlink: extraDirs 경로만 변경
4. Dead symlink 정리 (goal-planner 등)
5. setup.sh의 ENABLED_SKILLS에 존재하지 않는 스킬 정리
6. CLAUDE.md 스킬 분류 테이블 업데이트
