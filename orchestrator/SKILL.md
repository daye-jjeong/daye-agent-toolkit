---
name: orchestrator
description: 다단계 작업 분해 + 서브에이전트 조율 메타-에이전트
user-invocable: false
---

# Orchestrator

복잡한 다단계 작업을 분해하고, 여러 전문화된 서브에이전트를 조율하여 최종 산출물을 생성하는 메타-에이전트.

## 핵심 역할
- 사용자 요청을 실행 가능한 세부 작업으로 분해
- 각 작업에 적합한 전문 서브에이전트 선택 및 스폰
- **에이전트 템플릿**으로 역할별 프리셋 적용 (researcher, coder, analyst 등)
- **파일 기반 워크스페이스**로 디버깅·재현성·추적성 확보
- 작업 간 의존성 관리 및 실행 순서 결정
- 실행 후 **Dissolution Phase**로 정리·아카이브·메트릭 수집

## 사용법
```python
from skills.orchestrator.scripts import execute_orchestrator_task

result = execute_orchestrator_task(
    request="작업 설명",
    context={"taskUrl": "projects/folder/tasks.yml"},
    deliverable={"type": "report", "format": "markdown", "destination": "file"},
    acceptance_criteria=["성공 기준"],
    interactive=True,
    enable_workspace=True    # 파일 기반 워크스페이스 활성화
)
```

## 실행 흐름 (5 Phase)
1. **Phase 0** — 확인 게이트 (Gate 1: 계획, Gate 2: 예산)
2. **Phase 1** — 계획 수립 + 템플릿 적용
3. **Phase 2** — 워크스페이스 생성 → 에이전트 스폰 → 상태 추적
4. **Phase 3** — 통합 및 검증
5. **Phase 4** — Dissolution (정리·아카이브·메트릭)

## 에이전트 템플릿

| 역할 | 복잡도 | 모델 | 용도 |
|------|--------|------|------|
| researcher | Complex | claude-opus | 심층 연구, 분석 보고서 |
| coder | Moderate | claude-sonnet | 코드 작성, 리팩토링 |
| analyst | Moderate | claude-sonnet | 데이터 분석, 인사이트 |
| writer | Moderate | claude-sonnet | 문서 작성, 가이드 |
| reviewer | Simple | gemini-flash | 코드 리뷰, 품질 검사 |
| integrator | Moderate | claude-sonnet | 산출물 통합, 병합 |

## 주요 정책
- **확인 게이트**: Gate 1(계획) + Gate 2(예산, Medium 이상) 필수
- **깊이 제한**: 최대 2-Level (Main → Orchestrator → Worker)
- **모델 선택**: 템플릿 기반 자동 선택, 수동 오버라이드 가능
- **Fallback**: 모델 실패 시 자동 대체 체인 적용

## 구조
```
scripts/
├── gates.py            # Gate 1/2 승인 로직
├── model_selector.py   # 복잡도 분류 및 모델 선택
├── agent_templates.py  # 역할별 템플릿 (6종)
├── agent_workspace.py  # 파일 기반 워크스페이스
├── orchestrator.py     # 메인 실행 엔진 (5 Phase)
└── __init__.py
```

상세 문서: `README.md`
