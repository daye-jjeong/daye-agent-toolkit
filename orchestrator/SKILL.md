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
- 작업 간 의존성 관리 및 실행 순서 결정
- 중간 결과물 검증 및 품질 관리

## 사용법
```python
from skills.orchestrator.lib import execute_orchestrator_task

result = execute_orchestrator_task(
    request="작업 설명",
    context={"taskUrl": "projects/folder/tasks.yml"},
    deliverable={"type": "report", "format": "markdown", "destination": "file"},
    acceptance_criteria=["성공 기준"],
    interactive=True
)
```

## 주요 정책
- **확인 게이트**: Gate 1(계획) + Gate 2(예산, Medium 이상) 필수
- **깊이 제한**: 최대 2-Level (Main → Orchestrator → Worker)
- **모델 선택**: Simple → gemini-flash, Moderate → claude-sonnet, Complex → claude-opus
- **Fallback**: 모델 실패 시 자동 대체 체인 적용

## 구조
```
lib/
├── gates.py          # Gate 1/2 승인 로직
├── model_selector.py # 복잡도 분류 및 모델 선택
├── orchestrator.py   # 메인 실행 엔진
└── __init__.py
```

상세 문서: `README.md`
