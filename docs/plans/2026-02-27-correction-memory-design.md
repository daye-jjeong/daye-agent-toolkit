# Design: correction-memory 스킬

> Date: 2026-02-27
> Status: Approved
> Scope: Claude Code 전용, Total Recall 스타일 독립 스킬

## 배경

Boris Cherny(Claude Code 책임자)의 "Compounding Engineering" 패턴에서 영감:
> "교정할 때마다 'CLAUDE.md 업데이트해서 그 실수 반복하지 마'라고 말해라"

이를 자동화하고 체계화하는 스킬을 만든다.
superpowers 워크플로(brainstorm→plan→execute→review→verify)에 빠진
"교정을 영구적으로 기억하는" 마지막 고리를 닫는 역할.

### 참고 프로젝트

| 프로젝트 | 참고 포인트 |
|----------|------------|
| [Total Recall](https://github.com/davegoldblatt/total-recall) | 4계층 메모리 + 교정 전파 프로토콜 + Write Gate |
| [Compound Engineering Plugin](https://github.com/EveryInc/compound-engineering-plugin) | review→compound 워크플로, 복리 효과 철학 |
| [claude-mem](https://github.com/thedotmack/claude-mem) | 벡터 검색 기반 메모리, 시맨틱+키워드 하이브리드 |

## 스킬 메타

| 항목 | 값 |
|------|-----|
| 스킬명 | `correction-memory` |
| 위치 | `correction-memory/SKILL.md` + `references/` |
| 분류 | Claude Code 전용 (`.claude-skill` 있음) |
| `skills.json` | `local_skills`에 추가 |

## 아키텍처 — 3계층 메모리 + 교정 전파

```
┌─────────────────────────────────────────────┐
│  Layer 1: Rules (즉시 적용)                   │
│  .claude/rules/corrections.md               │
│  → 매 세션 시작 시 자동 로드                    │
│  → "bun 사용 필수", "enum 금지" 등 행동 규칙    │
├─────────────────────────────────────────────┤
│  Layer 2: Register (주제별 영구 저장)           │
│  memory/corrections/{topic}.md              │
│  → tooling.md, architecture.md, testing.md  │
│  → 교정 이력 + 사유 + superseded 마커          │
├─────────────────────────────────────────────┤
│  Layer 3: Log (타임라인 기록)                   │
│  memory/corrections/log/YYYY-MM-DD.md       │
│  → 언제 어떤 교정이 발생했는지 시간순 기록         │
│  → 주기적 정리 (오래된 것은 register로 승격)      │
└─────────────────────────────────────────────┘
```

### 경로 규칙

- Layer 1: 프로젝트별 `.claude/rules/corrections.md` (git 추적)
- Layer 2: auto memory `~/.claude/projects/{project}/memory/corrections/{topic}.md`
- Layer 3: auto memory `~/.claude/projects/{project}/memory/corrections/log/YYYY-MM-DD.md`

## 교정 전파 프로토콜

교정 발생 시 → 3곳 동시 업데이트:

```
사용자: "npm 말고 bun 써"
  │
  ├─→ Layer 1 (Rules): .claude/rules/corrections.md
  │   + "- ALWAYS use bun, NEVER use npm for package management"
  │
  ├─→ Layer 2 (Register): memory/corrections/tooling.md
  │   + "## Package Manager"
  │   + "- [2026-02-27] npm → bun (사유: 프로젝트 표준)"
  │   + "- [superseded] npm 사용 허용"
  │
  └─→ Layer 3 (Log): memory/corrections/log/2026-02-27.md
      + "14:30 | tooling | npm→bun | 사용자 직접 교정"
```

## 서브커맨드

| 커맨드 | 트리거 | 설명 |
|--------|--------|------|
| `correction-memory:save` | "이거 기억해", 교정 후 | 교정 사항을 3계층에 동시 저장 |
| `correction-memory:search` | "이전에 ~에 대해 교정한 적 있어?" | 키워드로 교정 이력 검색 |
| `correction-memory:review` | 주기적 정리 | 현재 규칙 전체 리뷰 + 중복/모순 제거 |
| `correction-memory:stats` | "교정 통계 보여줘" | 주제별 빈도, 최근 추세 |

## Write Gate (저장 기준)

모든 교정을 기록하면 노이즈가 되므로, 저장 가치 판단:

### 저장 O
- 행동 변경을 유발하는 교정 (도구, 패턴, 규칙 변경)
- 반복된 실수 (2회 이상 같은 교정)
- 아키텍처 결정 사항
- 프로젝트 컨벤션 관련

### 저장 X
- 일회성 오타/단순 실수
- 컨텍스트 의존적 판단 (이번 세션에서만 유효)
- 이미 CLAUDE.md에 있는 규칙의 중복

## superpowers 연계

별도 코드 없이 자동 연계:
- `.claude/rules/corrections.md` → Claude Code가 매 세션 자동 로드
- 모든 superpowers 워크플로(brainstorming, writing-plans 등)에서 교정 규칙이 컨텍스트에 존재
- `receiving-code-review` 후 교정 사항 발견 시 → `correction-memory:save` 안내

## Register 토픽 초기 분류

| 토픽 | 파일명 | 예시 |
|------|--------|------|
| 도구/런타임 | `tooling.md` | bun vs npm, 특정 CLI 사용법 |
| 아키텍처 | `architecture.md` | 디자인 패턴, 파일 구조 |
| 테스팅 | `testing.md` | 테스트 작성 규칙, 프레임워크 |
| 코딩 스타일 | `style.md` | 네이밍, 포매팅, 언어별 관습 |
| API/외부 연동 | `integrations.md` | API 사용법, 인증 방식 |
| 일반 | `general.md` | 분류 안 되는 것들 |

새로운 토픽이 발견되면 자동으로 새 파일 생성.

## vault-memory 폐기 결정

vault-memory는 dy-minions-squad가 완전 대체하므로 삭제 예정:
- 태스크 관리: minions-squad의 DAG + 상태머신이 대체
- 세션 기억: minions-squad의 journal→promote 파이프라인이 대체
- 장기 기억: minions-squad의 MEMORY.md + AGENTS.md + beliefs가 대체
- Claude Code 교정 기억: correction-memory (이 스킬)가 담당

최종 기억 체계:
```
기억/태스크 체계
├── OpenClaw: dy-minions-squad (brain/ 기반)
├── Claude Code: correction-memory + superpowers + auto memory
└── vault-memory → 삭제
```

## 리서치 참고 — OpenSwarm

별도 디자인 대상은 아니지만, 추후 참고용으로 기록:

- [Intrect-io/OpenSwarm](https://github.com/Intrect-io/OpenSwarm): Linear+Claude Code 자율 코딩 파이프라인
- 핵심: Worker/Reviewer 쌍 파이프라인 + 모델 에스컬레이션 + 인지 메모리(LanceDB)
- 현재 상태: 2026-02-23 공개, 107 stars, 안정성 미검증
- 도입 시 필요: Linear 도입, Discord→Slack 어댑터
- 판단: 프로젝트 성숙 후 재검토. correction-memory의 인지 메모리와 시너지 가능
