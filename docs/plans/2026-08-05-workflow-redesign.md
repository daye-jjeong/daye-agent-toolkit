# 개발 워크플로우 재설계 — 결론과 남은 작업

작성 2026-08-05. 이 세션의 리서치·실측 결과를 압축 없이 남긴 문서.

## 1. 문제 (실측)

### 증상
cube-backend 7월 49개 세션, 사용자 메시지 1,189개 중 명시적 이의제기 11회 / 7개 세션.
발생일 7/26·27·28·30·31 — **Opus 5 출시(7/24) 이후에 몰림**. 모델 교체로 해결될 문제가 아님.

대표 사례:
- "요청한 가드가 아니잖아. 내가 필터링해서 남기라고 얘기했어?"
- "스킬에 그렇게 안 되어있지 않아? 왜 맘대로 바꾼 거야?"
- "stopgap이 뭐야? 왜 용어를 니 맘대로 써?"

### 원인 ① brainstorming이 큰 작업에서 실행되지 않음

brainstorming을 호출한 19개 세션 추적:

| 편집 규모 | AskUserQuestion | 설계 문서 |
|---|---|---|
| 374회 | 1 | 없음 |
| 194회 | 0 | 있음 |
| 159회 | 0 | 1개 |
| 29회 | 7 | 20개 |
| 5회 | 5 | 10개 |

전체: 질문 0회 세션 21%, **설계 문서 미작성 42%**.
큰 작업일수록 형식만 거치고 실질을 건너뜀. 스킬 문서에는 "설계 승인 전 구현 금지" 하드 게이트가 있으나 통과됨.

### 원인 ② 설계와 구현이 한 세션
편집 374회 세션에서 초기 합의가 컨텍스트에 남을 수 없음.
공식 문서: 컨텍스트가 차면 앞선 지시를 잊기 시작.

### 원인 ③ 강제 부재 — 이미 세 번 증명됨

`memory/corrections/architecture.md`:
- [2026-03-15] spec review loop **0% 준수**
- [2026-03-15] Codex plan 리뷰 **5건 중 0건**

이번 실측 42%까지 세 번. 세 번 다 대응이 "금지 조항 추가"였고 세 번 다 실패.
**correction·룰은 실패가 증명된 수단.**

### 원인 ④ 룰 비대
시작 시점 `rules/` 7,558자. cube-backend는 CLAUDE.md 9,368자 + correction 13,402자 = 22,770자.
공식: 파일이 길면 규칙이 노이즈에 묻힘.

### grill-me가 0회 호출된 이유
cube-backend `.claude/skills/`에 grill-me·grill-with-docs가 **이미 설치돼 있었으나 769개 트랜스크립트에서 0회**.

- description 경쟁: brainstorming은 "모든 창작 작업 전 반드시 사용", grill-me는 "사용자가 원할 때"
- 룰이 지목: 파이프라인 1번이 `superpowers:brainstorming`. grill-me는 룰에 없었음

②는 파이프라인 삭제로 해소. ①은 남아 있음.

## 2. 리서치 결론

### Anthropic 공식
- 워크플로우: explore → plan → implement → commit
- **생략 기준: diff를 한 문장으로 설명할 수 있으면 계획 생략**
- 요구사항: AskUserQuestion으로 인터뷰 → SPEC 작성. **범위 밖 명시**. 스펙 완성 후 **새 세션에서 실행**
- CLAUDE.md: 각 줄에 "지우면 실수하나?" 물어 아니면 삭제
- **훅은 결정론적 보장, CLAUDE.md는 권고**
- 반복 위반 시 훅으로 전환

### Boris Cherny (제작자)
설정은 "놀랍도록 바닐라". 실수를 CLAUDE.md에 기록. **최신 모델은 계획 단계가 실제로 필요하지 않다**(Opus 4.6+). 훅 적극 사용. 6개월마다 지우고 관찰.

### 커뮤니티
- superpowers: "워크플로우는 좋은데 포장이 무겁다". 방법론 인정, 포장 거부
- 다수가 자체 경량 플러그인으로 이전
- **설치 수: grill-me 746k > superpowers 476k**
- grill-me 실사용: 세션당 질문 16~50개 (당신 레포 brainstorming은 0~1개)

### 정량 (2026-08-05 실측)
| 레포 | stars |
|---|---|
| obra/superpowers | 266,712 |
| mattpocock/skills | 203,750 |
| github/spec-kit | 125,360 |
| gsd-build/get-shit-done | 64,761 |
| Fission-AI/openspec | 63,835 |

## 3. 결정된 것

### 채택: grill-with-docs (전 레포 공통)
`grilling` + `domain-modeling` 조합. mattpocock/skills 소속.

`grilling` 본문(8줄) 핵심:
> 사실은 환경을 뒤져 직접 찾고, **결정은 사용자 것이니 하나씩 물어라.** 합의 확인 전엔 실행하지 마라.

`domain-modeling` 산출물:
- `CONTEXT.md` — 용어집. 정의 1~2문장 + `_Avoid_`(쓰지 말 동의어). 구현 세부 금지
- `docs/adr/NNNN-slug.md` — 제목 + 1~3문장. 게으르게 생성
- 다중 컨텍스트면 `CONTEXT-MAP.md`

ADR 작성 조건(셋 다 참): 되돌리기 어렵고 / 맥락 없이 의아하고 / 진짜 트레이드오프.

ADR이 담는 것 = "구조의 전제조건":
아키텍처 형태, 컨텍스트 간 통합 패턴, 락인 기술 선택, **경계·범위 결정(명시적 '아니오')**, **의도적 일탈**.

### 불채택
| 도구 | 이유 |
|---|---|
| OpenSpec / spec-kit | **변경 스펙**(이번에 뭘 만드나)이지 **구조 지식**(전제·이유)이 아님. 원하는 건 후자 |
| GSD (64.7K★) | 컨텍스트 희석은 겨냥하나 마크다운 50개+CLI+훅으로 무거움. 경량화 방향과 충돌 |
| Track | ADR·프로젝트 사실 추적이 domain-modeling과 겹침 |
| superpowers brainstorming | 실측 42% 미실행. grill-with-docs로 대체 |

### 목표 워크플로우
```
[한 문장 테스트] 통과 → 바로 구현
        ↓ 실패
grill-with-docs   인터뷰(사실 조회 / 결정 질문) + CONTEXT.md·ADR 즉시 갱신
        ↓
구현 (worktree / 새 세션)
        ↓
/code-review
```

## 4. 이미 적용 완료

### 전역 설정 (~/.claude)
- gstack 제거: 1.1GB → 8KB, 스킬 52개 소멸, 껍데기 디렉토리 55개 삭제
- 깨진 SessionStart 훅 제거 (gstack-session-update — 본체 없이 남아 매 세션 실패할 상태였음)
- 플러그인 4개 비활성화: context7 · telegram · playwright · andrej-karpathy-skills
- skillOverrides 5개: superpowers의 using-git-worktrees · dispatching-parallel-agents · verification-before-completion · requesting-code-review · receiving-code-review
- `~/.claude/CLAUDE.md` 삭제 (전체가 gstack 지침이었음)
- 스킬 카탈로그 ~8,010 → ~6,150 est.tok (1M 컨텍스트 1% 예산의 100% → 61%)

백업: `~/.claude/settings.json.bak-doctor`

### daye-agent-toolkit 룰 (커밋 3개)
- 12개 7,558자 → **8개 4,415자**
- 삭제: session-split, long-running-backoff, review, correction-protocol
- dev-workflow-gates 2,505 → 519자 (파이프라인 9단계·구현 위임·Workflow 조건·Subagent 모델·커밋 정리·핸드오프 삭제. worktree 게이트만 존치)
- verification: "done 주장 전 필수" 프레이밍 제거 → cross-file 일관성만
- CLAUDE.md 3,914 → 2,159자

**미머지.** 브랜치 `claude/opus5-rules-skills-review-f9d899`, 커밋 `9b3baa7` `180c2b8` `8fd8a7d`.

## 5. 남은 작업

### A. 재분류 (핵심)
correction 안에 세 층이 섞여 있음. 지우는 게 아니라 제자리로 옮기는 작업.

| 성격 | 갈 곳 |
|---|---|
| 도메인 경계·구조 결정, 의도적 일탈 | **ADR** |
| 용어 정의 | **CONTEXT.md** |
| 코드 컨벤션·명령어 | **CLAUDE.md** |
| 작업 습관 교정 | correction 유지 |
| 죽은 파이프라인 강제 | **삭제** |

대상 전수:
| 위치 | 개수 | 자수 |
|---|---|---|
| `rules/` (daye) | 8 | 4,415 |
| `memory/` | 13 | ~6,100 |
| `.claude/rules/` (daye) | 2 | 746 |
| cube-backend `.claude/rules/` | 8 | 13,402 |
| cube-backend `CLAUDE.md` | 1 | 9,368 |

삭제 확정:
- `memory/corrections/architecture.md` 2·3번 — spec review loop·Codex plan 리뷰. 폐기한 파이프라인 강제 + 준수율 0%
- `memory/corrections/workflow.md` "S 사이즈도 simplify + pr-review 필수" — 규모 무관 강제

재분류 예시 (cube-backend `no-system-writes-to-operator-owned-columns` 2,697자):
- "운영자 전용 컬럼은 그 API의 것, 재사용은 읽기로만" → **ADR**
- "리뷰 지적이 연쇄로 나오면 메커니즘 제거를 검토하라" → correction 유지
- PR #1048 사례 → ADR 배경

### B. 워크플로우 문서 재작성
- `rules/global/dev-workflow-gates.md` — 새 흐름 반영
- `memory/corrections/workflow.md`
- cube-backend `CLAUDE.md`

### C. 훅 설계
grill-with-docs가 실제로 불리게 만드는 장치. description이 "사용자가 원할 때"라 자동으로는 안 걸림.

미결 사항:
- 무엇을 트리거로 볼 것인가 (한 문장 테스트를 기계적으로 판정 불가)
- `PreToolUse`가 검사할 산출물이 무엇인가 (OpenSpec을 뺐으므로 `openspec validate` 같은 결정론적 검증기 없음)
- ADR 존재 여부는 "작성 조건 셋"이 판단 사항이라 기계 판정 어려움

### D. cube-backend 초기 구축
앱 8개(orders-api, order-worker, machines-api, dashboard-api, connectors-api, outbox-worker, notification-worker, calibration-worker) = 다중 컨텍스트.

```
CONTEXT-MAP.md
docs/adr/                      ← 시스템 전역
apps/<app>/CONTEXT.md
apps/<app>/docs/adr/
```

### E. 기타 미결
- reddit-fetch 스킬 사망 — Reddit이 익명 JSON 차단. OAuth 앱 등록 필요
- `claude update` 2.1.217 → 2.1.220 (앱이 `DISABLE_AUTOUPDATER=1` 주입, 터미널에서 수동)
- warp SessionStart:resume 훅 7/7 타임아웃 (med 8.9초)
- feature-dev 플러그인 끄기 — 스킬 0회, superpowers·pr-review-toolkit과 3중 중복
- claude.ai 커넥터 정리 (Gmail·Drive·calibration 중복 2개 등) — 웹 설정에서 계정 단위
- 룰 정리 커밋 머지 + `make install` (심링크 5개 dangling 예정)

## 6. 판단 기준 (다음 결정에 적용)

1. **하네스나 모델이 이미 하는가** → 하면 넣지 마라
2. **없으면 구체적으로 뭐가 깨지나** → 답 안 나오면 삭제
3. **선언인가 강제인가** → 룰·스킬은 선언. 세 번 실패했음
4. **인기 ≠ 적합** → superpowers는 1위지만 이 레포에서 42% 실패
