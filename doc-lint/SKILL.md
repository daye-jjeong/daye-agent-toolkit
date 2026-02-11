---
name: doc-lint
description: "시스템 .md 파일들의 정합성을 검사하는 린터. 파일 간 중복, 참조 깨짐, 스킬/모델 이름 불일치, 오래된 참조를 탐지한다. 사용자가 '검토해줘', '정리해줘', '중복 확인', '참조 체크', '린트', 'lint', '정합성', '일관성 체크' 등을 요청하거나, 시스템 .md 파일을 수정한 후 전체 상태를 점검할 때 사용하세요. 정기적인 시스템 헬스 체크에도 활용 가능."
---

# Doc Lint — 시스템 문서 정합성 검사기

## 목적
`~/clawd/` 내 시스템 .md 파일들이 서로 일관되고, 참조가 유효하며, 불필요한 중복이 없는지 자동으로 검사한다.

## 언제 사용하는가
- 시스템 .md 파일 수정 후 전체 정합성 확인
- 스킬 이름 변경, 디렉토리 구조 변경 후 참조 체크
- 정기 점검 (주간/월간 리뷰)
- 사용자가 "검토해줘", "린트 돌려줘" 요청 시

## 검사 항목

### 1. 참조 유효성 (Broken References)
시스템 .md 파일에서 언급하는 파일/디렉토리 경로가 실제로 존재하는지 검사.

**대상 패턴:**
- `skills/{name}/` → 해당 디렉토리 존재 여부
- `scripts/{name}` → 해당 스크립트 존재 여부
- `config/{name}` → 해당 설정 파일 존재 여부
- `memory/{name}` → 해당 메모리 파일 존재 여부
- `docs/{name}` → 해당 문서 존재 여부
- `projects/{name}/` → 해당 프로젝트 폴더 존재 여부

**제외:**
- 코드 블록 (```) 내부의 예시 경로
- 설명용 패턴 (예: `{type}--{name}`)

### 2. 스킬 이름 일관성 (Skill Name Consistency)
`skills/` 디렉토리에 실제 존재하는 스킬 이름과, 시스템 .md에서 참조하는 스킬 이름이 일치하는지 검사.

**검출 대상:**
- 삭제/이동된 스킬을 참조하는 경우
- 이름이 변경된 스킬의 구 이름을 참조하는 경우
- 오타로 인한 불일치

### 3. 모델 이름 일관성 (Model Name Consistency)
AGENTS.md § 2.2에 정의된 활성 모델 목록과, 다른 파일에서 참조하는 모델 이름이 일치하는지 검사.

**검출 대상:**
- 비활성/폐기된 모델 참조 (예: `gemini-2.5`, `claude-opus-4-6`)
- 오타/변형 이름

### 4. 중복 콘텐츠 (Duplicate Content)
두 개 이상의 시스템 .md 파일에 동일/유사한 정보가 존재하는지 검사.

**검출 방법:**
- 동일 문장이 3줄 이상 연속으로 중복되는 경우
- 동일 개념(프로필, 모델 목록, 규칙 등)이 여러 파일에 정의된 경우

**원칙:**
- 각 개념은 한 곳에서만 정의하고, 다른 곳에서는 `→ FILE.md 참조` 형태로 포인터만 둔다.
- 예외: 요약/컨텍스트 제공 목적의 간략한 반복은 허용

### 5. 프로젝트 구조 정합성 (Project Structure)
`projects/` 내 폴더들이 올바른 형식(`{type}--{name}/`)이고, 필수 파일(`project.yml`, `tasks.yml`)을 포함하는지 검사.

### 6. 레거시 참조 (Stale References)
더 이상 유효하지 않은 구 시스템 참조를 검출.

**검출 대상:**
- deprecated된 이름이나 경로 (사용자가 지정한 감시 목록 기반)
- 예: `jarvis-`, `task-os`, `notion_uploader` 등 마이그레이션 완료된 참조

## 실행 방법

### 자동 스크립트
```bash
python3 ~/clawd/skills/doc-lint/scripts/lint_docs.py
```

### 옵션
```bash
# 특정 검사만 실행
python3 scripts/lint_docs.py --check refs        # 참조만
python3 scripts/lint_docs.py --check skills      # 스킬 이름만
python3 scripts/lint_docs.py --check models      # 모델 이름만
python3 scripts/lint_docs.py --check duplicates   # 중복만
python3 scripts/lint_docs.py --check projects     # 프로젝트 구조만
python3 scripts/lint_docs.py --check stale        # 레거시만

# 전체 실행 (기본)
python3 scripts/lint_docs.py --check all

# JSON 출력
python3 scripts/lint_docs.py --format json
```

## 출력 형식

### 요약 보고
```
📋 Doc Lint Report — 2026-02-09
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 참조 유효성: 42/45 OK (3 broken)
✅ 스킬 이름: 18/18 OK
⚠️ 모델 이름: 1 issue
✅ 중복 콘텐츠: 0 found
✅ 프로젝트 구조: 7/7 OK
⚠️ 레거시 참조: 2 found

총 이슈: 6건 (🔴 3 error, ⚠️ 3 warning)
```

### 상세 보고 (이슈별)
```
🔴 BROKEN_REF | AGENTS.md:497
   참조: skills/task-manager/
   → 디렉토리 존재하지 않음

⚠️ STALE_NAME | HEARTBEAT.md:238
   "JARVIS HQ" — 레거시 이름 감지
   → watchlist: jarvis
```

## 감시 목록 (Watchlist)
레거시 참조 검출용 키워드 목록. 새로운 마이그레이션 후 업데이트:

```yaml
stale_patterns:
  - pattern: "jarvis-"
    context: "스킬 prefix로 사용된 경우"
    exception: "텔레그램 그룹명 등 외부 시스템 참조"
  - pattern: "task-os"
    context: "task-policy로 변경됨"
    exception: "없음"
  - pattern: "notion_uploader"
    context: "yaml_writer로 대체됨"
  - pattern: "claude-opus-4-6"
    context: "올바른 이름: claude-opus-4-5"
  - pattern: "gemini-2.5"
    context: "사용 금지 모델"
```

## 주기적 실행
- **수동:** 시스템 파일 수정 후 즉시 실행 권장
- **자동:** 주간 리뷰 시 heartbeat/cron에서 자동 실행 가능

## 한계
- 의미적 중복 (같은 내용을 다른 표현으로 기술)은 자동 감지 어려움 → 수동 검토 필요
- 코드 블록 내 경로는 제외하므로, 실제 스크립트에서 사용하는 경로는 별도 검증 필요
