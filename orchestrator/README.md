# Orchestrator 스킬 문서

**마지막 업데이트:** 2026-02-11 | **버전:** v3.3

---

## 개요

**Orchestrator**는 복잡한 다단계 작업을 분해하고, 여러 전문화된 서브에이전트를 조율하여 최종 산출물을 생성하는 메타-에이전트입니다.

**핵심 역할:**
- 사용자 요청을 실행 가능한 세부 작업으로 분해
- **에이전트 템플릿**으로 역할별 프리셋 자동 적용
- **파일 기반 워크스페이스**로 에이전트별 지시/산출물 추적
- 작업 간 의존성 관리 및 실행 순서 결정
- 중간 결과물 검증 및 품질 관리
- **Dissolution Phase**로 실행 후 정리·아카이브·메트릭 수집

---

## 빠른 시작

### 기본 사용법

```python
from skills.orchestrator.scripts import execute_orchestrator_task

result = execute_orchestrator_task(
    request="작업 설명 (한국어)",
    context={
        "taskUrl": "projects/folder/tasks.yml",
        "relatedDocs": ["AGENTS.md"],
        "constraints": ["제약사항"]
    },
    deliverable={
        "type": "report | code | documentation",
        "format": "markdown | json | code",
        "destination": "file"
    },
    acceptance_criteria=["성공 기준 1", "성공 기준 2"],
    interactive=True,
    enable_workspace=True     # 파일 기반 워크스페이스 (기본값: True)
)

if result["status"] == "completed":
    print(f"✅ 완료: {result['summary']}")
    if "dissolution" in result:
        d = result["dissolution"]
        print(f"   Run: {d['run_id']} | {d['agents_successful']}/{d['agents_total']} 성공")
else:
    print(f"❌ 실패: {result['summary']}")
```

### 확인 게이트 (Gate)

**Gate 1: 계획 확인 (모든 작업)**
```
**작업 제목**

🎯 **목표:** [목표 설명]

**계획:**
• [단계 1]
• [단계 2]
• [단계 3]

**산출물:** [산출물]

ETA: ~25분 | 토큰: ~40K in / ~12K out

진행할까요?
```

**Gate 2: 토큰 예산 확인 (Medium 이상만)**
```
⚠️ **토큰 예산 확인**

이 작업은 Medium 크기입니다:
- 예상 소요: ~30분
- 토큰 사용: ~50K in / ~15K out
- 예상 비용: $1.50 (GPT-4 기준)

계속 진행할까요?
```

---

## 작업 크기 & 게이트 정책

| 크기 | 시간 | 토큰 | Gate 1 | Gate 2 | 예시 |
|------|------|------|--------|--------|------|
| **Trivial** | <2분 | <5K | ⏭️ | ⏭️ | "몇 시?" |
| **Small** | 2-10분 | 5K-20K | ✅ | ⏭️ | "일정 조회" |
| **Medium** | 10-45분 | 20K-100K | ✅ | ✅ | "가이드 작성" |
| **Large** | 45분-3시간 | 100K-500K | ✅ | ✅ | "API 연동" |
| **Epic** | 3시간+ | 500K+ | ✅ | ✅ | "시스템 재설계" |

---

## 에이전트 템플릿

역할별 프리셋으로 복잡도·모델·프롬프트를 자동 할당합니다.

| 역할 | 복잡도 | 모델 | 용도 |
|------|--------|------|------|
| **researcher** | Complex | `claude-opus-4-5` | 심층 연구, 자료 수집, 분석 보고서 |
| **coder** | Moderate | `claude-sonnet-4-5` | 코드 작성, 리팩토링, 버그 수정 |
| **analyst** | Moderate | `claude-sonnet-4-5` | 데이터 분석, 패턴 식별, 인사이트 |
| **writer** | Moderate | `claude-sonnet-4-5` | 문서 작성, 가이드, 매뉴얼 |
| **reviewer** | Simple | `gemini-3-flash` | 코드 리뷰, 문서 검증, 품질 검사 |
| **integrator** | Moderate | `claude-sonnet-4-5` | 산출물 통합, 병합, 일관성 확보 |

**사용법:**
```python
from skills.orchestrator.scripts import get_template, get_model_for_role

# 템플릿 조회
template = get_template("researcher")
# → {"complexity": COMPLEX, "prompt_prefix": "...", "expected_output": "markdown"}

# 역할별 모델 확인
model = get_model_for_role("coder")
# → "anthropic/claude-sonnet-4-5"

# subtask에 템플릿 자동 적용
subtask = {"name": "Research", "task": "시장 조사", "role": "researcher"}
resolved = resolve_subtask_template(subtask)
# → complexity, model, prompt_prefix 자동 채움 (기존 값은 보존)
```

---

## 에이전트 워크스페이스

각 에이전트 실행마다 파일 기반 워크스페이스를 생성하여 디버깅·재현성·추적성을 확보합니다.

### 디렉토리 구조
```
~/.clawdbot/orchestrator/workspaces/{run-id}/{agent-name}/
├── inbox/instructions.md    # 오케스트레이터 → 에이전트 (지시사항)
├── outbox/                  # 에이전트 → 오케스트레이터 (산출물)
├── workspace/               # 에이전트 작업 공간 (정리 대상)
└── status.json              # pending → running → completed | failed
```

### 주요 함수
```python
from skills.orchestrator.scripts import (
    generate_run_id,        # → "20260211-143022"
    create_workspace,       # 디렉토리 구조 생성 + 초기 status.json
    write_instructions,     # inbox/instructions.md 작성
    update_status,          # status.json 갱신
    read_status,            # status.json 읽기
    collect_outbox,         # outbox 파일 목록 반환
    list_agent_workspaces,  # run 내 모든 에이전트 목록
    cleanup_run,            # workspace/ 정리, inbox/outbox 보존
)
```

### 워크스페이스 비활성화
```python
result = execute_orchestrator_task(
    ...,
    enable_workspace=False  # 워크스페이스 없이 기존 방식으로 실행
)
```

---

## 모델 선택 규칙

자동 복잡도 분류 기반 모델 선택 (AGENTS.md § 2.5 gates 준수):

| 복잡도 | 모델 | 용도 |
|--------|------|------|
| **Simple** | `google-gemini-cli/gemini-3-flash-preview` | 데이터 fetch, 단순 변환, 포맷 정리 |
| **Moderate** | `anthropic/claude-sonnet-4-5` | 분석, 문서 작성, 컨텍스트 해석 |
| **Complex** | `anthropic/claude-opus-4-5` | 연구, 설계, 복잡한 의사결정 |

**자동 분류 키워드:**
- **Simple:** fetch, get, 조회, 가져오, 변환, 코드
- **Complex:** research, design, integrate, 연구, 설계, 통합, 분석

**수동 오버라이드:**
```python
from skills.orchestrator.scripts import select_model_for_task

model = select_model_for_task(
    "데이터 분석",
    custom_model="anthropic/claude-opus-4-5"  # 강제 지정
)
```

---

## 실행 흐름

### Phase 0: 확인 게이트 (필수)

모든 비-Trivial 작업은 사용자 승인이 필요합니다 (AGENTS.md § 2.7):

1. **Gate 1 표시:** 목표 + 3 bullets + 산출물 + ETA/토큰
2. **사용자 응답 대기:** "진행", "OK", "Yes"
3. **Gate 2 (Medium+):** 토큰 예산 확인 요청

### Phase 1: 계획 수립 + 템플릿 적용

- 요청을 3-10개 서브작업으로 분해
- **에이전트 템플릿** 적용 (role 기반 complexity/model/prompt 자동 할당)
- 각 서브작업의 복잡도 판단 및 모델 할당
- ETA 및 토큰 예산 추정

### Phase 2: 실행 + 워크스페이스

- **워크스페이스 생성** → inbox에 instructions.md 작성
- 각 서브작업마다 서브에이전트 스폰 + **status.json 추적**
- 진행 상황 추적 및 실패 우아하게 처리 (fallback)

### Phase 3: 통합

- 중간 산출물들을 최종 산출물로 병합
- 수용 기준에 대한 최종 검증
- 산출물 포맷팅 및 전달 (파일 저장)

### Phase 4: Dissolution (정리)

실행 완료 후 자동 실행:

1. **Outbox 검증** — 모든 에이전트의 산출물 존재 확인
2. **execution_summary.json** — 총 에이전트 수, 성공/실패, 사용 모델, 시간
3. **workspace/ 정리** — scratch 디렉토리 삭제 (inbox/outbox 보존)
4. **아카이브 마킹**

**반환값에 dissolution 키 추가:**
```python
result["dissolution"] = {
    "run_id": "20260211-143022",
    "workspace_path": "~/.clawdbot/orchestrator/workspaces/20260211-143022",
    "archived": True,
    "agents_total": 3,
    "agents_successful": 3,
}
```

---

## 깊이 제한 (Critical)

**2-Level 최대 깊이:**

```
Main Agent (Depth 0)
  └─ Orchestrator (Depth 1)
       └─ Worker (Depth 2) ← MAX, cannot spawn further
```

---

## Fallback 정책

모델 실패 시 자동 대체 (AGENTS.md § 2.6 checkpoints 준수):

**기본 Fallback Chain:**
```
gpt-5.2 → claude-sonnet-4-5 → gemini-3-pro → claude-haiku-4-5
```

**재시도 규칙:**
- **Rate Limit (429):** 5초 간격, 최대 3회 재시도 후 fallback
- **Timeout:** 1회 재시도 후 fallback
- **Model Unavailable:** 즉시 fallback (재시도 없음)

---

## API 명세

### execute_orchestrator_task()

```python
def execute_orchestrator_task(
    request: str,                    # 사용자 요청
    context: Dict,                   # taskUrl, relatedDocs, constraints
    deliverable: Dict,               # type, format, destination
    acceptance_criteria: List[str],   # 성공 검증 기준
    interactive: bool = True,        # 사용자 승인 대기
    dry_run: bool = False,           # 실행 없이 계획만 표시
    workspace_root: Optional[str] = None,   # 워크스페이스 루트 오버라이드
    archive_workspace: bool = True,  # Dissolution 후 아카이브
    enable_workspace: bool = True,   # 파일 기반 워크스페이스 활성화
) -> Dict
```

**반환:**
```python
{
    "status": "completed | partial | failed | cancelled",
    "executionLog": [...],
    "deliverables": [...],
    "checkpoints": {...},
    "summary": "1-2문장 결과",
    "issuesEncountered": [...],
    "recommendations": [...],
    "dissolution": {              # enable_workspace=True일 때만
        "run_id": str,
        "workspace_path": str,
        "archived": bool,
        "agents_total": int,
        "agents_successful": int,
    }
}
```

---

## 트러블슈팅

### "Depth limit exceeded"
**해결:** 작업을 2단계 이내로 재구성

### "All models failed"
**조치:** 로그 확인 → Rate limit 쿨다운 → 커스텀 fallback

### "Gate timeout"
**해결:** `dry_run=True`로 미리보기 또는 `interactive=False`

---

## 아키텍처

```
scripts/
├── gates.py            # Gate 1/2 형식 및 승인 로직
├── model_selector.py   # 복잡도 분류 및 모델 선택
├── agent_templates.py  # 역할별 템플릿 (6종)
├── agent_workspace.py  # 파일 기반 워크스페이스
├── orchestrator.py     # 메인 실행 엔진 (5 Phase)
└── __init__.py         # 공개 API
```

---

## 모듈 구현 세부사항

### agent_templates.py (v3.3 추가)

- `AGENT_TEMPLATES`: 6개 역할 템플릿 dict
- `get_template(role)`: 템플릿 조회
- `get_model_for_role(role)`: COMPLEXITY_MODEL_MAP 기반 모델 resolve
- `resolve_subtask_template(subtask, default_role)`: subtask에 템플릿 기본값 적용
- `list_roles()`: 역할 → 설명 dict 반환

### agent_workspace.py (v3.3 추가)

- `generate_run_id()`: 타임스탬프 기반 run ID 생성
- `create_workspace()`: 디렉토리 구조 생성 + 초기 status.json
- `write_instructions()`: inbox/instructions.md 작성
- `update_status()` / `read_status()`: status.json 관리
- `collect_outbox()`: outbox 파일 목록 반환
- `list_agent_workspaces()`: run 내 에이전트 목록
- `cleanup_run()`: workspace/ 정리 (inbox/outbox 보존)
- `write_execution_summary()`: execution_summary.json 생성

### model_selector.py

- `TaskComplexity`: 복잡도 enum (SIMPLE/MODERATE/COMPLEX)
- `COMPLEXITY_MODEL_MAP`: 복잡도 → 모델 매핑
- `classify_task_complexity()`: 작업 설명으로 자동 분류
- `select_model_for_task()`: 작업에 맞는 모델 선택
- `select_models_for_plan()`: 다중 서브작업 모델 할당

### gates.py

- `format_plan_confirmation()`: Gate 1 메시지 포맷
- `format_budget_confirmation()`: Gate 2 메시지 포맷
- `check_approval()`: 사용자 응답 검증
- `ask_approval()`: 고수준 승인 흐름

### orchestrator.py

- `WorkSize`: 작업 크기 enum (TRIVIAL/SMALL/MEDIUM/LARGE/EPIC)
- `classify_work_size()`: ETA/토큰으로 작업 크기 분류
- `estimate_cost()`: USD 비용 추정
- `run_confirmation_gates()`: Gate 1/2 실행
- `_run_dissolution_phase()`: Phase 4 Dissolution (v3.3 추가)
- `execute_orchestrator_task()`: 메인 실행 함수 (5 Phase)

---

## 버전 이력

**v3.3 (2026-02-11):** 에이전트 템플릿 + 워크스페이스 + Dissolution
- 에이전트 템플릿 6종 추가 (researcher, coder, analyst, writer, reviewer, integrator)
- 파일 기반 에이전트 워크스페이스 (inbox/outbox/workspace/status.json)
- Phase 4 Dissolution 추가 (정리·아카이브·메트릭 수집)
- execute_orchestrator_task()에 workspace_root, archive_workspace, enable_workspace 파라미터 추가
- session_manager import를 optional로 변경 (graceful fallback)

**v3.2 (2026-02-09):** YAML SOT 마이그레이션
- Notion 모든 참조 제거
- 모델 목록 업데이트 (gpt-5.2, claude-opus-4-5, gemini-cli 경로 등)
- AGENTS.md 섹션 참조 정확화 (§ 2.5, 2.6, 2.7, 6, 7.3)

**v3.1 (2026-02-04):** Confirmation Gates + Depth Limit

**v3.0 (2026-02-04):** Fallback Policy

---

**📝 작성 정보**
- **최종 업데이트:** 2026-02-11 (Claude Opus 4.6)
- **상태:** Production ready
- **라이선스:** MIT (Task OS 일부)
