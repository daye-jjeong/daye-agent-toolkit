# daye-agent-toolkit

개인 범용 스킬 전용 레포. Claude Code + OpenClaw 양쪽에서 사용.
외부 마켓플레이스 플러그인도 `skills.json`으로 선언적 관리.

## 접근 방식

| 환경 | 접근 방식 |
|------|-----------|
| Claude Code (로컬) | `./setup.sh` → 마켓플레이스 등록 + 플러그인 설치 + symlink |
| OpenClaw (원격) | `./setup.sh --openclaw` → clone + 스킬 enable + cron |

## 스킬 분류

### Claude Code 전용 (5개) — `.claude-skill` 있음, OpenClaw disabled

| 스킬 | 설명 |
|------|------|
| correction-memory | 교정 기억 — 실수 반복 방지 3계층 메모리 |
| mermaid-diagrams | Mermaid 다이어그램 생성 가이드 |
| professional-communication | 업무 커뮤니케이션 가이드 |
| skill-forge | SKILL.md 생성/최적화/감사/검증 |
| work-digest | 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림 |

### Claude Code + OpenClaw 양쪽 (10개) — `.claude-skill` 있음, OpenClaw enabled

| 스킬 | 설명 |
|------|------|
| banksalad-import | 뱅크샐러드 → Obsidian vault import |
| goal-planner | 월간→주간→일간 목표 관리 |
| health-coach | 맞춤 건강 조언 + 운동 추천 |
| health-tracker | 운동/증상/PT 트래킹 |
| investment-report | 일일 투자 리포트 |
| investment-research | 투자 종목 리서치 |
| meal-tracker | 식사 기록 + 영양 모니터링 |
| news-brief | 키워드 뉴스 브리핑 |
| pantry-manager | 식재료 관리 자동화 |
| saju-manse | 사주팔자 분석 |

### OpenClaw 전용 (11개) — `.claude-skill` 없음, OpenClaw enabled

| 스킬 | 설명 | 비고 |
|------|------|------|
| check-integrations | 외부 서비스 통합 점검 | `disable-model-invocation` |
| elon-thinking | First Principles 사고 프레임 | |
| model-health-orchestrator | 모델 헬스체크 + 폴백 | |
| notion | Notion API 클라이언트 | |
| openclaw-docs | OpenClaw 문서 참조 가이드 | |
| orchestrator | 서브에이전트 조율 | `user-invocable: false` |
| proactive-agent | 능동적 에이전트 패턴 | |
| prompt-guard | 프롬프트 인젝션 스캐너 | `user-invocable: false` |
| quant-swing | 스윙 전략 실행/분석 | |
| schedule-advisor | 캘린더 브리핑/알림 | |
| system-audit | 시스템 감사 — 문서 린트 + 점검 | |

## skills.json 매니페스트

`local_skills`: Claude Code에서 symlink할 스킬 목록 (15개).
OpenClaw은 `~/openclaw/skills/` 전체를 스캔하므로 별도 목록 불필요.
OpenClaw enable/disable은 `setup.sh --openclaw`이 `~/.openclaw/openclaw.json`에 설정.

## 스킬 포맷

- `<skill-name>/SKILL.md` — 스킬 본문 (공통, 150줄 이내)
- `<skill-name>/references/` — 상세 문서 (SKILL.md에서 포인터 참조)
- `<skill-name>/.claude-skill` — Claude Code 메타데이터 (양쪽/CC전용만)

### SKILL.md frontmatter 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | Y | 스킬 식별자 |
| `description` | Y | 50자 이내 한줄 설명 (OpenClaw 시스템 프롬프트 주입) |
| `user-invocable` | N | `false`면 슬래시 커맨드 비노출 (내부 스킬) |
| `disable-model-invocation` | N | `true`면 모델 프롬프트에서 제외 (cron/수동 전용) |
| `metadata` | N | OpenClaw 의존성 게이팅 (requires.bins, requires.env) |

## 새 스킬 추가 절차

1. `<skill-name>/` 디렉토리 생성
2. `SKILL.md` 작성 (frontmatter + 150줄 이내)
3. 상세 내용은 `references/`로 분리
4. Claude Code용이면: `.claude-skill` 추가 + `skills.json`의 `local_skills`에 추가
5. OpenClaw용이면: `setup.sh`의 `ENABLED_SKILLS`에 추가
6. `./setup.sh` 실행
7. 커밋 + push

## 동기화

- 레포가 source of truth
- `~/openclaw/skills/`는 이 레포의 clone
- `scripts/sync.py`로 양방향 git sync (OpenClaw PC용)
- `setup.sh --openclaw`으로 초기 셋업 (clone + enable + cron)

## scripts/ 규칙

- stdlib만 사용 (외부 패키지 금지)
- bash 또는 python3
- `{baseDir}/scripts/` 경로로 SKILL.md에서 참조

## 방침

- cube-claude-skills는 건드리지 않음
- 이 레포는 개인 범용 스킬만 관리
- Cube 업무용 스킬은 cube-claude-skills에 유지
- 네이밍: 하이픈(`-`) 통일 (언더스코어 금지)
