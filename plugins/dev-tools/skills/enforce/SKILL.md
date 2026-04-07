---
name: enforce
description: 반복 교정 패턴을 훅으로 전환 제안. correction 로그를 스캔하여 3회+ 반복 위반을 감지하고, 훅 코드 초안 + settings.json 등록 방법을 제시한다. "enforce", "훅으로 전환", "규칙 강제", "반복 교정 확인" 등의 요청에 사용.
---

# Enforce — 반복 교정 → 훅 전환

correction-memory 로그를 스캔하여 반복되는 위반 패턴을 찾고, 훅으로 자동 강제할 수 있는 후보를 제안한다.

## 실행 절차

### 1. 수집

다음 3개 소스를 모두 스캔:

- **Layer 1 (Rules):** `~/.claude/rules/correction-*.md` — 프로젝트별 `.claude/rules/correction-*.md`도 포함
- **Layer 2 (Register):** auto memory `corrections/*.md` (토픽별 교정 이력)
- **Layer 3 (Log):** auto memory `corrections/log/*.md` (날짜별 타임라인)

### 2. 감지

토픽별로 Layer 2 엔트리 수를 카운트한다. `- [YYYY-MM-DD]` 형식 라인 1개 = 1회.

**훅 전환 후보 기준:** 같은 토픽 3회 이상.

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
