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
디렉토리: `{project}/.claude/rules/`
파일 이름: `correction-{slug}.md` (규칙 1개 = 파일 1개)

포맷:
- 파일당 하나의 규칙
- `- ` 접두사 (마크다운 리스트)
- 영어로 작성 (Claude가 가장 잘 따름)
- DO/DON'T 명확히 구분
- 최대 50개 파일 유지 (초과 시 review 모드 제안)
- slug: lowercase, hyphens, 2-4 words

예시:
```
# .claude/rules/correction-use-bun.md
- ALWAYS use bun, NEVER use npm for package management

# .claude/rules/correction-no-enum.md
- NEVER use TypeScript enum, use string literal unions instead
```

개별 파일 방식의 이점: 동일 디렉토리에서 여러 세션이 동시에 작업해도 충돌 없음.

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

### 4단계: 스코프 결정

교정의 적용 범위를 판단:
- **프로젝트 한정** (기본) → `.claude/rules/corrections.md`
- **전역** (모든 프로젝트에 적용할 교정) → 사용자에게 `~/.claude/CLAUDE.md` 추가 제안
- 판단 기준: "이 규칙이 다른 프로젝트에서도 유효한가?"

### 5단계: 중복 체크

저장 전에 기존 규칙과의 중복 확인:
1. `.claude/rules/corrections.md`에 동일/유사 규칙이 있는지 확인
2. 프로젝트 CLAUDE.md 본문에 이미 같은 내용이 있는지 확인
3. `~/.claude/CLAUDE.md` (전역)에 있는지 확인
4. 중복 발견 시 → 저장 안 함 + "이미 존재하는 규칙입니다" 안내
5. 유사하지만 다른 경우 → 기존 규칙 업데이트 (superseded 마커)

### 6단계: CLAUDE.md 연동

교정이 프로젝트 컨벤션에 해당하는 경우:
- CLAUDE.md 업데이트가 필요한지 사용자에게 제안
- 사용자 승인 후에만 CLAUDE.md 수정
- Layer 1 (Rules)에는 항상 저장, CLAUDE.md는 선택적

### 7단계: 확인 메시지

저장 완료 후 사용자에게 요약 보고:
```
Correction saved:
  Rule: "{규칙 내용}"
  Topic: {토픽명}
  Scope: all sessions in this project
```
