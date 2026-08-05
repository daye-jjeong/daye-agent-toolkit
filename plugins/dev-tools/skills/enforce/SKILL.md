---
name: enforce
description: 반복 교정 패턴을 훅으로 전환 제안. correction 로그를 스캔하여 3회+ 반복 위반을 감지하고, 훅 코드 초안 + settings.json 등록 방법을 제시한다. "enforce", "훅으로 전환", "규칙 강제", "반복 교정 확인" 등의 요청에 사용.
---

# Enforce — 반복 교정 → 훅 전환

correction-memory 로그를 스캔하여 반복되는 위반 패턴을 찾고, 훅으로 자동 강제할 수 있는 후보를 제안한다.

## 실행 절차

### 1. 수집

프로젝트별 `.claude/rules/correction-*.md`와 전역 `~/.claude/rules/`를 모두 읽는다.

> 예전에는 auto memory의 Register·Log 계층도 스캔했다. 두 계층은 미기록으로 폐기됐다 — `correction-memory` 스킬 참조.

### 2. 감지

규칙을 겨냥 대상(파일 경로, 명령어, 코드 패턴, 절차)으로 묶는다.

**훅 전환 후보 기준:** 같은 대상을 겨냥한 규칙이 3개 이상이거나, 규칙이 이미 있는데도 같은 위반이 재발한 경우.

재발은 파일 개수로 안 잡힌다. 사용자가 "이거 규칙에 있는데 또 그러네"라고 하면 그 자리에서 후보로 올린다.

### 3. 분류

각 후보를 위반 유형별로 분류하고 적합한 훅 이벤트를 매핑:

| 위반 유형 | 훅 이벤트 | 매처 | 예시 |
|-----------|-----------|------|------|
| 특정 파일 수정 금지 | PreToolUse | Edit\|Write | `.env` 직접 수정 |
| 코드 패턴 사용 금지 | PostToolUse | — | `console.log` 잔존, transition-all |
| 절차 누락 (테스트/검증) | Stop | — | 테스트 미실행, tsc 미실행 |
| 명령어 사용 금지 | PreToolUse | Bash | `git push --force` |
| 분류 불가 | — | — | 규칙으로 유지 (훅 부적합) |

**분류 불가한 경우:** 모든 교정이 훅으로 전환 가능한 것은 아니다. "코드 스타일 선호", "설명 방식" 등 주관적 교정은 규칙으로 유지하고 훅 후보에서 제외.

### 4. 제안

각 훅 후보에 대해 다음을 출력:

```
## 후보 N: {토픽} ({위반횟수}회)

### 교정 이력
- [날짜] {교정 내용 요약}
- ...

### 제안 훅
- 이벤트: {PreToolUse|PostToolUse|Stop}
- 매처: {패턴}
- 동작: {차단|경고}

### 훅 코드 초안
\`\`\`bash
#!/bin/bash
# {설명}
{코드}
\`\`\`

### 설치 방법
1. 파일 저장: `plugins/dev-tools/hooks/{slug}.sh`
2. `chmod +x plugins/dev-tools/hooks/{slug}.sh`
3. `~/.claude/settings.json`의 `hooks.{이벤트}` 배열에 추가
```

### 5. 설치

**사용자 승인 후에만 진행.** 승인 시:
1. 훅 스크립트를 `plugins/dev-tools/hooks/`에 Write
2. `chmod +x` 실행
3. `~/.claude/settings.json`의 해당 이벤트 hooks 배열에 Edit으로 등록
4. 해당 교정의 Layer 1 rule 파일에 "훅으로 전환됨" 메모 추가

## 주의사항

- 훅 코드는 LLM이 직접 작성한다. 별도 코드 생성 스크립트 없음.
- 훅은 bash, stdlib만 사용. 외부 패키지 금지.
- 기존 훅 패턴 참고: `plugins/dev-tools/hooks/worktree-guard.sh`, `plugins/dev-tools/hooks/merge-gate.sh`
- 차단 훅은 `exit 2`, 통과는 `exit 0`.
