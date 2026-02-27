# 교정 전파 프로토콜

## 트리거

사용자가 Claude의 행동을 교정할 때 자동 감지:
- 명시적: "이거 기억해", "다시는 하지 마", "항상 ~해"
- 암시적: 같은 지시를 2회 이상 반복할 때

## 전파 절차

### 1단계: Write Gate 통과 확인
→ [write-gate.md](write-gate.md) 기준으로 저장 가치 판단

### 2단계: 토픽 분류
→ [register-topics.md](register-topics.md) 기준으로 자동 분류
→ 기존 토픽에 안 맞으면 새 토픽 파일 생성

### 3단계: 3계층 동시 저장

#### Layer 1 — Rules
파일: `{project}/.claude/rules/corrections.md`

포맷:
- 한 줄에 하나의 규칙
- `- ` 접두사 (마크다운 리스트)
- 영어로 작성 (Claude가 가장 잘 따름)
- DO/DON'T 명확히 구분
- 최대 50개 규칙 유지 (초과 시 review 모드 제안)

예시:
```
- ALWAYS use bun, NEVER use npm for package management
- NEVER use TypeScript enum, use string literal unions instead
- ALWAYS run typecheck before committing
```

#### Layer 2 — Register
파일: `~/.claude/projects/{hash}/memory/corrections/{topic}.md`

포맷:
```
## {소제목}
- [{날짜}] {이전} → {이후} (사유: {사유})
- [superseded] {이전 규칙} ({날짜} 폐기)
```

새 교정이 기존 규칙을 대체하면 이전 항목에 [superseded] 마커 추가.

#### Layer 3 — Log
파일: `~/.claude/projects/{hash}/memory/corrections/log/YYYY-MM-DD.md`

포맷:
```
{HH:MM} | {토픽} | {요약} | {트리거 유형}
```

트리거 유형: 사용자 직접 교정 | 반복 지시 감지 | 코드 리뷰 결과

### 4단계: 확인 메시지

저장 완료 후 사용자에게 요약 보고:
```
✅ 교정 저장 완료
규칙 추가: "{규칙 내용}"
토픽: {토픽명}
적용 범위: 이 프로젝트의 모든 세션
```
