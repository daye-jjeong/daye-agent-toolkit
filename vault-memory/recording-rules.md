# vault-memory:recording-rules

> 파일별 기록 규칙. 모든 AI 세션(Claude Code, OpenClaw)은 이 규칙을 따른다.

## 파일별 기록 대상

### AGENTS.md — 시스템 정책/행동 규칙
**위치:** `~/clawd/AGENTS.md`
**성격:** 살아있는 문서. AI가 작업할 때 매번 참조하는 운영 매뉴얼.

**기록 대상:**
- 도구 접근 등급 변경 (Tier 1/2/3)
- 모델 우선순위/fallback 순서 변경
- 세션 보호 정책 (메인 세션 허용/금지 범위)
- 출력 정책 (언어, 포맷, 위생 규칙)
- 승인 게이트 (Plan/Budget 승인 기준)
- 크론 작업 정책 (실행 조건, 모델 선택, 로그 억제)
- 텔레그램/슬랙 메시지 규칙
- vault 기록 정책 (이 문서와 연동)

**기록 트리거:**
- 다예가 "이건 규칙으로 해" / "항상 이렇게 해" / "정책 추가해" 라고 말할 때
- 반복되는 실수나 패턴이 발견됐을 때
- 모델/도구/인프라 변경 시

**기록하지 않는 것:**
- 일회성 작업 지시 (세션 로그에 기록)
- 개인 정보, 선호 (MEMORY.md에 기록)
- 구현 상세 (코드/스킬에 기록)

---

### memory/MEMORY.md — 장기 기억
**위치:** `memory/MEMORY.md`
**성격:** 다예에 대한 팩트, 선호, 상태. AI가 "다예를 아는" 근거.

**기록 대상:**
- 커리어 정보 (직장, 연봉, 휴직, 지분)
- 건강 정보 (운동, PT, 질환, 루틴)
- 재무 정보 (수입, 고정비, 예산 목표)
- 시스템 설정 (키 위치, API 정보, 하드웨어)
- 다예 선호 (커뮤니케이션 스타일, 도구 선호)
- 프로젝트 메타 (Notion DB ID, 로닉 팀 구성)
- 핵심 결정 (방향성, 장기 계획)

**기록 트리거:**
- `vault-memory:preserve` 호출 시
- `vault-memory:compress` 중 장기 보관 가치 발견 시 자동 제안
- 다예가 "기억해줘" / "저장해" 라고 말할 때

**기록하지 않는 것:**
- 일시적 상태 (오늘 기분, 임시 할 일)
- API 키/비밀번호 원문 (마스킹 필수)
- 세션별 작업 내역 (세션 로그에 기록)

**보호 섹션:** Career, Health, System, Key — 구조 변경 금지, 내용 추가만

---

### memory/YYYY-MM-DD.md — 일일 세션 로그
**위치:** `memory/` 루트 (flat)
**성격:** 그 날 무슨 일이 있었는지. 검색 가능한 일지.

**기록 대상 (format.md 규격):**
- **결정사항** — 왜 그렇게 결정했는지 (이유 필수)
- **핵심 배움** — 재사용 가능한 지식
- **해결한 문제** — 문제 → 원인 → 해결 방법
- **수정된 파일** — 경로 + 변경 설명
- **미완료/대기** — 다음 세션에서 이어갈 것
- **에러/이슈** — 미해결 에러

**기록 트리거:**
- `vault-memory:compress` 호출 (세션 종료 시)
- `vault-session-save` cron (30분 자동)
- SessionEnd hook (자동 마커)

**기록하지 않는 것:**
- 대화 원문/타임스탬프
- 중간 과정 상세 (최종 결과만)
- MEMORY.md에 이미 있는 배경 반복
- Notion ID/URL 나열

---

### memory/policy/*.md — 상세 정책 문서
**위치:** `memory/policy/`
**성격:** AGENTS.md 규칙의 상세 버전. 배경, 예시, 엣지케이스 포함.

**기록 대상:**
- AGENTS.md 한 줄로 충분하지 않은 복잡한 정책
- 정책의 배경/히스토리/예외 케이스
- 크론 작업 템플릿, 로그 억제 규칙 등

**기록 트리거:**
- 새 정책이 AGENTS.md에 추가될 때 상세 문서가 필요한 경우
- 기존 정책에 예외/엣지케이스가 추가될 때

---

### memory/goals/ — 목표
**위치:** `memory/goals/{daily,weekly,monthly}/`
**성격:** 계획과 회고.

**기록 대상:**
- 일간: 오늘 할 일, 타임블록, 체크리스트
- 주간: 주간 목표, 달성률, 회고
- 월간: 월간 방향, 핵심 마일스톤

**기록 트리거:**
- `vault-memory:daily-note` (일간)
- `vault-memory:weekly-review` (주간)
- 수동 생성 (월간)

---

### memory/docs/ — 설계 문서
**위치:** `memory/docs/`
**성격:** 살아있는 설계/가이드/스펙. 구현 진행 중 참조.

**기록 대상:**
- 아키텍처 설계서
- 구현 가이드/스펙
- 기술 의사결정 기록 (ADR)

---

### memory/reports/ — 완료된 산출물
**위치:** `memory/reports/`
**성격:** 완료된 리서치/분석. 참조용 아카이브.

**기록 대상:**
- 투자 리서치 결과
- 시장 분석, 어닝 캘린더
- 리서치 프롬프트 템플릿
- 대시보드, 데이터 시각화

**포맷 선택 (내용에 맞게):**
| 유형 | 포맷 |
|------|------|
| 대시보드, 시각화, 인터랙티브 | `.html` |
| 정식 보고서, 공유용 | `.pdf` |
| 리서치 노트, 편집 필요 | `.md` |

Obsidian 뷰: PDF 네이티브, HTML은 Custom Frames 플러그인.

---

### memory/projects/{type}/{name}/ — 프로젝트 태스크
**위치:** `memory/projects/{work|personal}--{name}/`
**성격:** 프로젝트별 태스크 추적. repo 연결, 진행 로그 포함.

**파일 구조:**
- `project.yml` — 프로젝트 메타 (이름, 상태, 목표, 태그)
- `tasks.yml` — 태스크 목록 (SOT)

**기록 대상 (tasks.yml):**
- **status 변경** — todo → in_progress → done | blocked
- **subtask 완료** — 개별 subtask status 업데이트
- **progress_log** — 작업 내용 요약 (append-only, 최신이 위)
  - `date`: 작업 날짜
  - `by`: claude-code | openclaw | daye
  - `summary`: 1-2줄 작업 요약
  - `files_changed`: 수정한 파일 목록
- **repos** — 관련 코드 연결
  - `repo`: GitHub repo (owner/name)
  - `branch`: 작업 브랜치
  - `prs`: 관련 PR 번호
  - `commits`: 주요 커밋 SHA

**기록 트리거:**
- 태스크 시작/완료 시 (status 변경)
- 코드 작업 후 (progress_log + repos 업데이트)
- compress 시 프로젝트 관련 작업이 감지되면 자동 업데이트 제안
- 커밋 메시지에 `[t-xxx-nnn]` 포함 시 해당 태스크에 commit 기록

**기록하지 않는 것:**
- 세션 대화 내용 (세션 로그에 기록)
- 중간 디버깅 과정 (최종 결과만)

**교차 참조:**
- 태스크 → 목표: `linked_goals`에 `[[위키링크]]`
- 목표 → 태스크: 본문에 `[[t-xxx-nnn]]`
- 커밋 → 태스크: 커밋 메시지에 `[t-xxx-nnn]`

---

## 기록 흐름

```
세션 중 작업 발생
    │
    ├─ 프로젝트 작업? ─────── → tasks.yml (status + progress_log + repos)
    │                            + 세션 로그 (compress)
    │
    ├─ 일회성 결정? ─────────── → 세션 로그 (compress)
    │
    ├─ 반복 규칙? ───────────── → AGENTS.md (sync-agents)
    │                              └─ 상세 필요? → policy/*.md
    │
    ├─ 다예 개인 정보/선호? ──── → MEMORY.md (preserve)
    │
    └─ 산출물? ──────────────── → reports/ 또는 docs/
```

### 프로젝트 작업 기록 흐름 (상세)

```
코드 작업 완료
    │
    ├─ 1. tasks.yml status 업데이트
    │     └─ subtask 완료 처리
    │
    ├─ 2. progress_log append
    │     └─ date, by, summary, files_changed
    │
    ├─ 3. repos 필드 업데이트
    │     └─ branch, commits, prs
    │
    └─ 4. 세션 로그에 요약 기록
          └─ "t-ronik-001: 캘리 프로세스 as-is 정리 완료"
```

## 플랫폼별 트리거

### Claude Code

| 이벤트 | 트리거 | 메커니즘 |
|--------|--------|----------|
| 세션 종료 | 자동 | `SessionEnd` hook → `memory/YYYY-MM-DD.md`에 세션 마커 append |
| 세션 압축 | 수동 | `/vault-memory:compress` Skill 호출 → 세션 마커를 AI 분석으로 보강 |
| 프로젝트 작업 | 정책 | 태스크 시작/완료 시 tasks.yml 업데이트 + progress_log + repos 기록 |
| 에이전트 완료 | 정책 | 메인 세션이 Task 결과 수신 후 세션 로그 + 관련 tasks.yml 업데이트 |
| 정책 동기화 | 수동 | compress 후 정책 키워드 감지 시 sync-agents 제안 |
| 장기 보존 | 수동 | `/vault-memory:preserve` Skill 호출 |

**Claude Code hook 파일**: `.claude/hooks/session_end.py`
- `.jsonl` transcript 파싱 → 수정 파일, 실행 명령, 에러 추출
- `memory/YYYY-MM-DD.md`에 세션 마커 자동 append
- compress가 나중에 이 마커를 보강(enrich)

### OpenClaw

| 이벤트 | 트리거 | 메커니즘 |
|--------|--------|----------|
| 세션 종료 | 대화 지시 | "세션 저장해", "compress", "오늘 정리" → compress 워크플로우 실행 |
| 자동 저장 | 크론 | `vault-session-save` (30분 주기) → 기본 세션 마커 append |
| 프로젝트 작업 | 정책 | 태스크 시작/완료 시 tasks.yml 업데이트 + progress_log + repos 기록 |
| 에이전트 완료 | 정책 | orchestrator가 worker 완료 수신 후 세션 로그 + 관련 tasks.yml 업데이트 |
| 정책 동기화 | 대화 지시 | "정책 동기화", "agents 업데이트" → sync-agents 워크플로우 |
| 장기 보존 | 대화 지시 | "기억해줘", "MEMORY에 저장" → preserve 워크플로우 |

**OpenClaw 자동 제안 규칙:**
- 세션 30분+ → compress 자동 제안
- compress 중 정책 키워드 감지 → sync-agents 제안
- compress 중 장기 가치 감지 → preserve 제안

### 공통 규칙

- **기록 포맷**: `memory/format.md` 규격 (양쪽 동일)
- **기록 경로**: 양쪽 모두 `memory/YYYY-MM-DD.md` (flat)
- **세션 헤더**: `## 세션 HH:MM (플랫폼, session-id-8자리)` — 플랫폼은 `claude-code` 또는 `openclaw`
- **충돌 방지**: 같은 날 양쪽에서 기록해도 세션 헤더로 구분

---

## 알림

### 아키텍처

```
태스크 파일 변경 (Claude Code / Obsidian Sync)
    │
    ↓  Obsidian Shell Commands "File content modified" 감지
    │
    ↓  python3 ~/clawd/scripts/notify_task_change.py "{{file_path}}"
    │
    ↓  변경 파싱 + 쿨다운 체크 (30초 내 중복 방지)
    │
    ↓  clawdbot agent --message "요약" --channel telegram --deliver
    │
    ↓  OpenClaw이 수신 → 필요시 후속 작업
```

### Obsidian Shell Commands 설정

1. 플러그인 설치: Shell Commands
2. 셸 커맨드 등록: `python3 ~/clawd/scripts/notify_task_change.py "{{file_path}}"`
3. 이벤트: "File content modified"
4. 경로 필터: `projects/**/*` (tasks.yml, project.yml, t-*.md)

### 알림 스크립트

**경로**: `scripts/notify_task_change.py`

알림 메시지 형식:
```
📋 work--ronik tasks.yml 변경됨
  ✅ t-ronik-001: 캘리봇 기획 재정리 완료
  🔄 t-ronik-004: PM봇 태스크 형식 검증 — openclaw: Notion DB 구조 확인 완료
```

전달 경로:
1. `clawdbot agent` → OpenClaw (primary)
2. Telegram 직접 전송 (fallback)

### 크로스 플랫폼 컨텍스트 복원

| 상황 | 메커니즘 |
|------|----------|
| OpenClaw 작업 → Claude Code 세션 시작 | resume에서 활성 태스크 스캔, 다른 플랫폼 작업 하이라이트 |
| Claude Code 작업 → OpenClaw 세션 시작 | Obsidian webhook → clawdbot agent → OpenClaw 수신 |
| 긴급 핸드오프 | Obsidian webhook → 즉시 알림 |

---

## 자동 감지 키워드

| 키워드 | 대상 파일 |
|--------|----------|
| "항상", "규칙으로", "정책 추가" | AGENTS.md |
| "기억해", "저장해", "잊지마" | MEMORY.md |
| "이건 앞으로도", "매번" | AGENTS.md |
| "내 xx는", "나는 xx 선호" | MEMORY.md |
