# daye-agent-toolkit

개인 범용 스킬 전용 레포. Claude Code + OpenClaw 양쪽에서 사용.
외부 마켓플레이스 플러그인도 `skills.json`으로 선언적 관리.

## 접근 방식

| 환경 | 접근 방식 |
|------|-----------|
| Claude Code (로컬) | `make install-cc` → 마켓플레이스 등록 + 플러그인 설치 + symlink |
| OpenClaw (원격) | `make install-oc` → clone + 스킬 enable + cron |
| 동기화 | `make sync` → 양방향 git sync (OpenClaw PC용) |

## 디렉토리 구조

```
cc/           — Claude Code 전용 스킬
shared/       — CC + OpenClaw 양쪽 스킬
openclaw/     — OpenClaw 전용 스킬
_infra/       — 빌드/설치/동기화 스크립트
```

## 스킬 분류

### Claude Code 전용 (7개) — `cc/` 디렉토리

| 스킬 | 설명 |
|------|------|
| correction-memory | 교정 기억 — 실수 반복 방지 3계층 메모리 |
| mermaid-diagrams | Mermaid 다이어그램 생성 가이드 |
| professional-communication | 업무 커뮤니케이션 가이드 |
| reddit-fetch | Reddit 포스트/댓글 조회 + 검색 |
| skill-forge | SKILL.md 생성/최적화/감사/검증 |
| work-digest | 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림 |
| youtube-fetch | YouTube 메타데이터 + 자막 추출 |

### Claude Code + OpenClaw 양쪽 (9개) — `shared/` 디렉토리

| 스킬 | 설명 |
|------|------|
| banksalad-import | 뱅크샐러드 → Obsidian vault import |
| health-coach | 맞춤 건강 조언 + 운동 추천 |
| health-tracker | 운동/증상/PT 트래킹 |
| investment-report | 일일 투자 리포트 |
| investment-research | 투자 종목 리서치 |
| meal-tracker | 식사 기록 + 영양 모니터링 |
| news-brief | 키워드 뉴스 브리핑 |
| pantry-manager | 식재료 관리 자동화 |
| saju-manse | 사주팔자 분석 |

### OpenClaw 전용 (5개) — `openclaw/` 디렉토리

| 스킬 | 설명 | 비고 |
|------|------|------|
| check-integrations | 외부 서비스 통합 점검 | `disable-model-invocation` |
| elon-thinking | First Principles 사고 프레임 | |
| notion | Notion API 클라이언트 | |
| prompt-guard | 프롬프트 인젝션 스캐너 | `user-invocable: false` |
| quant-swing | 스윙 전략 실행/분석 | |

## skills.json 매니페스트

디렉토리 기반 자동 탐색. `cc/`, `shared/`의 스킬을 자동으로 발견하므로 개별 목록 불필요.
`marketplace_plugins`로 외부 플러그인 선언.
OpenClaw enable/disable은 `make install-oc`이 `~/.openclaw/openclaw.json`에 설정.

## 스킬 포맷

- `<category>/<skill-name>/SKILL.md` — 스킬 본문 (공통, 150줄 이내)
- `<category>/<skill-name>/references/` — 상세 문서 (SKILL.md에서 포인터 참조)
- `<category>/<skill-name>/.claude-skill` — Claude Code 메타데이터 (cc/, shared/만)

### SKILL.md frontmatter 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | Y | 스킬 식별자 |
| `description` | Y | 50자 이내 한줄 설명 (OpenClaw 시스템 프롬프트 주입) |
| `user-invocable` | N | `false`면 슬래시 커맨드 비노출 (내부 스킬) |
| `disable-model-invocation` | N | `true`면 모델 프롬프트에서 제외 (cron/수동 전용) |
| `metadata` | N | OpenClaw 의존성 게이팅 (requires.bins, requires.env) |

## 새 스킬 추가 절차

1. 카테고리 디렉토리에 `<skill-name>/` 생성 (`cc/`, `shared/`, `openclaw/`)
2. `SKILL.md` 작성 (frontmatter + 150줄 이내)
3. 상세 내용은 `references/`로 분리
4. Claude Code용이면: `.claude-skill` 추가 (`cc/` 또는 `shared/`에 배치)
5. OpenClaw용이면: `openclaw/` 또는 `shared/`에 배치
6. `make install-cc` 또는 `make install-oc` 실행
7. 커밋 + push

## 동기화

- 레포가 source of truth
- `~/openclaw/skills/`는 이 레포의 clone
- `make sync`로 양방향 git sync (OpenClaw PC용)
- `make install-oc`으로 초기 셋업 (clone + enable + cron)

## scripts/ 규칙

- stdlib만 사용 (외부 패키지 금지)
- bash 또는 python3
- 개별 스킬은 자체 `{baseDir}/scripts/`를 SKILL.md에서 참조
- `_infra/scripts/`는 레포 인프라 전용 (Makefile에서 호출, SKILL.md에서 참조하지 않음)

## 방침

- cube-claude-skills는 건드리지 않음
- 이 레포는 개인 범용 스킬만 관리
- Cube 업무용 스킬은 cube-claude-skills에 유지
- 네이밍: 하이픈(`-`) 통일 (언더스코어 금지)
