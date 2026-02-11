# Orchestrator 스킬 문서

**마지막 업데이트:** 2026-02-09 | **버전:** v3.2

---

## 개요

**Orchestrator**는 복잡한 다단계 작업을 분해하고, 여러 전문화된 서브에이전트를 조율하여 최종 산출물을 생성하는 메타-에이전트입니다.

**핵심 역할:**
- 사용자 요청을 실행 가능한 세부 작업으로 분해
- 각 작업에 적합한 전문 서브에이전트 선택 및 스폰
- 작업 간 의존성 관리 및 실행 순서 결정
- 중간 결과물 검증 및 품질 관리
- 최종 산출물 통합 및 전달

---

## 빠른 시작

### 기본 사용법

```python
from skills.orchestrator.lib import execute_orchestrator_task

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
    interactive=True
)

if result["status"] == "completed":
    print(f"✅ 완료: {result['summary']}")
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
from skills.orchestrator.lib import select_model_for_task

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
2. **사용자 응답 대기:** "진행", "OK", "Yes", 👍
3. **Gate 2 (Medium+):** 토큰 예산 확인 요청

**승인 판단 기준:**
- Trivial (<2분, 산출물 없음) → 게이트 생략
- Small (2-10분) → Gate 1만 필수
- Medium+ (10분+) → Gate 1 + Gate 2 필수
- 긴급 지시 ("지금 바로") → 게이트 생략 가능

### Phase 1: 계획 수립

- 요청을 3-10개 서브작업으로 분해
- 각 서브작업의 복잡도 판단 및 모델 할당
- ETA 및 토큰 예산 추정
- Gate 2 필요시 토큰 예산 승인 요청

### Phase 2: 실행

- 각 서브작업마다 서브에이전트 스폰
- 진행 상황 추적 및 실패 우아하게 처리 (fallback)
- 다음 단계 전 중간 산출물 검증

### Phase 3: 통합

- 중간 산출물들을 최종 산출물로 병합
- 수용 기준에 대한 최종 검증
- 산출물 포맷팅 및 전달 (파일 저장)

---

## 깊이 제한 (Critical)

**2-Level 최대 깊이:**

```
Main Agent (Depth 0)
  └─ Orchestrator (Depth 1)
       └─ Worker (Depth 2) ← MAX, cannot spawn further
```

**위반 시 ValueError 발생:**
```python
# ❌ 금지됨 - Depth 3
spawn_subagent_with_retry(
    task="...",
    current_depth=2  # Max 2까지만 허용
)
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

**로그:** `~/.clawdbot/agents/main/logs/fallback_decisions.jsonl`

---

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
    dry_run: bool = False            # 실행 없이 계획만 표시
) -> Dict
```

**반환:**
```python
{
    "status": "completed | partial | failed | cancelled",
    "executionLog": [
        {
            "subtask": "서브작업 이름",
            "agent": "사용된 모델",
            "status": "completed | failed",
            "duration": 분,
            "output": "경로 또는 요약"
        }
    ],
    "deliverables": [
        {
            "type": "primary | supporting",
            "description": "설명",
            "url": "접근 가능한 링크"
        }
    ],
    "checkpoints": {
        "A": {"completed": "timestamp", "artifact": "url"},
        "B": {"completed": "timestamp", "artifact": "url"}
    },
    "summary": "1-2문장 결과",
    "issuesEncountered": ["블로커, 재시도 등"],
    "recommendations": ["향후 개선사항"]
}
```

### select_model_for_task()

```python
from skills.orchestrator.lib import select_model_for_task

model = select_model_for_task(
    task_description="작업 설명",
    complexity_override=None,        # TaskComplexity.SIMPLE/MODERATE/COMPLEX
    custom_model=None                # 강제 모델 지정
)
```

---

## 사용 예시

### 예시 1: 간단한 데이터 조회

```python
result = execute_orchestrator_task(
    request="Google Calendar에서 오늘 일정 가져오기",
    context={"taskUrl": "projects/tasks/tasks.yml"},
    deliverable={"type": "data", "format": "json", "destination": "file"},
    acceptance_criteria=["JSON 파일 생성"],
    interactive=True
)
# → 자동으로 Simple 분류, gemini-flash 사용, Gate 2 생략
```

### 예시 2: 복잡한 연구 작업

```python
result = execute_orchestrator_task(
    request="멀티에이전트 시스템 설계 및 구현 방안 연구",
    context={
        "taskUrl": "projects/research/tasks.yml",
        "relatedDocs": ["AGENTS.md"]
    },
    deliverable={
        "type": "documentation",
        "format": "markdown",
        "destination": "file"
    },
    acceptance_criteria=[
        "아키텍처 다이어그램 포함",
        "구현 예시 코드 포함"
    ],
    interactive=True
)
# → 자동으로 Complex 분류, claude-opus-4-5 사용, Gate 1 + Gate 2 필수
```

---

## 트러블슈팅

### "Depth limit exceeded"
**원인:** Worker가 추가 서브에이전트를 스폰하려고 함

**해결:** 작업을 2단계 이내로 재구성

### "Task URL required"
**원인:** 서브에이전트 스폰 시 taskUrl 누락

**해결:**
```python
spawn_subagent_with_retry(
    task="...",
    task_url="projects/folder/tasks.yml"  # 필수
)
```

### "All models failed"
**증상:** Fallback chain 모든 모델 실패

**조치:**
1. 로그 확인: `~/.clawdbot/agents/main/logs/fallback_decisions.jsonl`
2. Rate limit 쿨다운 대기 (보통 1분)
3. 커스텀 fallback 순서 지정

### "Gate timeout"
**증상:** 10분 무응답으로 작업 취소

**해결:**
- `dry_run=True`로 계획 미리보기
- `interactive=False`로 자동화 (사전 승인 필수)

---

## 정책 & 안전 규칙

### AGENTS.md 참조

- **§ 2.5 Gates:** 확인 게이트 정책
- **§ 2.6 Checkpoints:** 체크포인트 및 상태 저장
- **§ 2.7 Reapproval:** 재승인 정책
- **§ 6 Protocol:** 전체 프로토콜
- **§ 7.3 SOT:** Task 저장소 (YAML)

### 해야 할 것

- ✅ Gate 1 형식 준수 (목표 + 3 bullets + 산출물 + ETA/토큰)
- ✅ Gate 2 (Medium+) 토큰 예산 승인
- ✅ 사용자 응답 대기 (타임아웃 정책 준수)
- ✅ 10개 미만의 서브작업으로 분해
- ✅ 각 산출물에 체크포인트 URL 포함

### 하지 말아야 할 것

- ❌ 게이트 생략 (예외 제외)
- ❌ Gate 1 포맷 위반 (4개 이상 bullet)
- ❌ Gate 2 생략 (Medium+ 작업)
- ❌ 승인 전 서브에이전트 스폰
- ❌ 명확하지 않은 작업 정의로 스폰
- ❌ 검증 실패한 채로 다음 단계 진행

---

## 아키텍처

```
lib/
├── gates.py          # Gate 1/2 형식 및 승인 로직
├── model_selector.py # 복잡도 분류 및 모델 선택
├── orchestrator.py   # 메인 실행 엔진
└── __init__.py       # 공개 API
```

---

## 모듈 구현 세부사항

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
- `execute_orchestrator_task()`: 메인 실행 함수

---

## 버전 이력

**v3.2 (2026-02-09):** YAML SOT 마이그레이션
- Notion 모든 참조 제거
- 모델 목록 업데이트 (gpt-5.2, claude-opus-4-5, gemini-cli 경로 등)
- AGENTS.md 섹션 참조 정확화 (§ 2.5, 2.6, 2.7, 6, 7.3)
- README + QUICKSTART 통합, 한국어 간결화 (<200줄)

**v3.1 (2026-02-04):** Confirmation Gates + Depth Limit
- Gate 1/2 추가
- 2-Level 깊이 제한
- Task OS 안전 규칙

**v3.0 (2026-02-04):** Fallback Policy
- 자동 재시도/대체 로직
- Rate Limit, Timeout, Model Unavailable 처리

---

**📝 작성 정보**
- **최종 업데이트:** 2026-02-09 (Claude Haiku 4.5)
- **상태:** Production ready
- **라이선스:** MIT (Task OS 일부)
