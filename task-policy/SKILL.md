---
name: task-policy
description: 태스크 생성/실행 정책 가드레일 — pre-work gate, post-work 업로드, 감사 로깅
user-invocable: false
---

# Task Policy

태스크 생성, 분류, 실행의 전체 정책과 가드레일을 관리하는 스킬. 하위에 guardrails, triage 서브스킬 포함.
Storage: Obsidian vault (`~/mingming-vault/projects/`).

## 핵심 정책
- **태스크 생성**: 사용자 확인(opt-in) 후에만 생성
- **Due Date**: 절대 자동 설정 금지 -- 반드시 사용자에게 확인
- **Start Date**: 작업 시작 시 자동 설정
- **언어**: 모든 산출물은 한국어 기본

## 서브스킬

### guardrails (v2.0.0)
산출물 접근성 강제 + vault 저장 자동화.
- Pre-Work Gate: Task 참조 없이 deliverable 작업 차단
- Post-Work Gate: 로컬 파일 자동 vault 저장
- 위반 감사 로그 (violations.jsonl)

### triage
태스크 자동 분류 + 생성.
- 사용자 요청 분석 -> 태스크 자동 분류
- 프로젝트 자동 연결
- Obsidian vault frontmatter 기반 태스크 저장

## 사용법
```python
# Guardrails
from guardrails.lib.gates import pre_work_gate, post_work_gate

pre_work_gate(task_description="... Task: t-ronik-001", session_id="...")
post_work_gate(session_id="...", final_output="...", auto_upload=True)

# Triage
from triage.triage import handle_user_request
result = handle_user_request(user_message, auto_approve=False)
```

## 구조
```
task-policy/
├── POLICY.md              # 전체 운영 정책
├── SKILL.md               # 이 파일
├── scripts/
│   └── task_io.py         # Obsidian vault I/O 모듈 (공통)
├── guardrails/            # 가드레일 서브스킬
│   ├── SKILL.md
│   ├── lib/               # 핵심 라이브러리
│   │   ├── classifier.py
│   │   ├── validator.py
│   │   ├── vault_writer.py
│   │   ├── deliverable_checker.py
│   │   ├── state.py
│   │   ├── logger.py
│   │   └── gates.py
│   ├── tests/
│   └── examples/
└── triage/                # 분류 서브스킬
    ├── SKILL.md
    ├── triage.py
    ├── task_helpers.py
    ├── automation_logger.py
    └── config.json
```

상세 정책: `POLICY.md`
