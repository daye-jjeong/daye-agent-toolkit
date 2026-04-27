# daye-agent-toolkit

개인 범용 에이전트 툴킷. Claude Code 플러그인 구조로 스킬/훅/규칙을 관리.

## 접근 방식

`make install` → 로컬 마켓플레이스 등록 + 플러그인 활성화 + 규칙 심링크

## 디렉토리 구조

```
plugins/          — CC 플러그인 (4개 플러그인, 18개 스킬)
rules/            — 글로벌 규칙 (~/.claude/rules/에 심링크)
mcp/              — MCP 서버 (life-dashboard 등)
codex/            — Codex CLI 전용 설정
docs/plans/       — 디자인 문서 + 구현 plan
.claude/rules/    — 프로젝트 레벨 규칙 오버라이드
```

## 플러그인 분류

### life-management (4개 스킬)

| 스킬 | 설명 |
|------|------|
| health-tracker | 운동/증상/PT/건강체크인/식사 트래킹 + 루틴 추천 + 분석 |
| life-coach | 통합 라이프 코칭 — 작업 패턴 + 건강/운동/식사 분석 |
| pantry-manager | 식재료 관리 자동화 |
| saju-manse | 사주팔자 분석 |

### finance (3개 스킬)

| 스킬 | 설명 |
|------|------|
| banksalad-import | 뱅크샐러드 → life-dashboard SQLite DB import |
| investment-manager | 투자 포트폴리오 현황, 종목 점검, 리스크 분석, 시세 갱신 |
| spending-manager | 소비 분석 — 카테고리 요약, 추세, 미분류 정리, 예산 관리 |

### dev-tools (7개 스킬 + 훅)

| 스킬 | 설명 |
|------|------|
| codex-cli | 프로젝트 맞춤 adversarial 프롬프트 — 공식 /codex:adversarial-review에 focus text 전달 |
| correction-memory | 교정 기억 — 실수 반복 방지 3계층 메모리 |
| enforce | 반복 교정 → 훅 전환 제안 — correction 로그 스캔 + 훅 코드 초안 |
| gemini-cli | Gemini CLI 래퍼 — 디자인 위임, 코드 리뷰, 범용 LLM 호출 |
| self-profile | 업무 데이터 기반 자기 프로파일링 |
| stop-slop-kr | 한국어 AI 말투 교정 — 번역체, 아첨, 상투어 제거 |
| work-digest | 일일 작업 다이제스트 — CC 세션 로그 + 요약 + 알림 |

### media-fetch (3개 스킬)

| 스킬 | 설명 |
|------|------|
| news-brief | 키워드 뉴스 브리핑 |
| reddit-fetch | Reddit 포스트/댓글 조회 + 검색 |
| youtube-fetch | YouTube 메타데이터 + 자막 추출 |

## marketplace.json

`.claude-plugin/marketplace.json`이 로컬 마켓플레이스를 정의. `make install`이 이를 `~/.claude/settings.json`에 등록.

## 규칙 시스템

`rules/*.md` 파일은 모든 CC 세션에 자동 로드되는 행동 규칙.

### 규칙 소스

| 경로 | 설명 |
|------|------|
| `rules/global/` | 프로젝트 무관 글로벌 규칙 |
| `rules/correction/` | 교정 프로토콜 자동 적용 |
| `rules/tone/` | 한국어 톤 규칙 |
| `.claude/rules/` | 프로젝트 레벨 오버라이드 (git-tracked) |

### 동작

- `make install` → `rules/**/*.md`를 `~/.claude/rules/`에 심링크
- 기존 파일(심링크 아닌)이 있으면 SKIP
- `.claude/rules/`는 프로젝트별 오버라이드 (예: worktree 명령어 변경)

## 스킬 포맷

- `plugins/<plugin>/skills/<skill-name>/SKILL.md` — 스킬 본문 (150줄 이내)
- `plugins/<plugin>/skills/<skill-name>/references/` — 상세 문서 (SKILL.md에서 포인터 참조)
- `plugins/<plugin>/.claude-plugin/plugin.json` — 플러그인 메타데이터
- `plugins/<plugin>/hooks/hooks.json` — 훅 정의 (해당 플러그인에 훅이 있을 때)

### SKILL.md frontmatter 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | Y | 스킬 식별자 |
| `description` | Y | 한줄 설명. 트리거링용이므로 구체적으로. |
| `user-invocable` | N | `false`면 슬래시 커맨드 비노출 (내부 스킬) |
| `disable-model-invocation` | N | `true`면 모델 프롬프트에서 제외 (cron/수동 전용) |

## 새 스킬 추가 절차

1. 해당 플러그인 디렉토리에 `skills/<skill-name>/` 생성
2. `SKILL.md` 작성 (frontmatter + 150줄 이내)
3. 상세 내용은 `references/`로 분리
4. `make install` 실행
5. 커밋 + push

## scripts/ 규칙

- stdlib만 사용 (외부 패키지 금지)
- bash 또는 python3
- 개별 스킬은 자체 `scripts/`를 SKILL.md에서 참조

## 스킬 자동 개선

대화 중 스킬에 개선할 만한 부분이 보이면 사용자에게 한 번 물어보고, 동의하면 알아서 업데이트한다. 작은 개선(SKILL.md 섹션 추가, 규칙 한 줄 추가 등)은 별도 todo로 쌓지 말고 즉시 처리.

- 코드 변경은 worktree에서
- feedback memory와 SKILL.md 둘 다 반영 — memory는 즉시 효과, SKILL.md는 타 세션/에이전트까지 적용
- 머지 후 보고

## 방침

- cube-claude-skills는 건드리지 않음
- 이 레포는 개인 범용 스킬만 관리
- Cube 업무용 스킬은 cube-claude-skills에 유지
- 네이밍: 하이픈(`-`) 통일 (언더스코어 금지)
