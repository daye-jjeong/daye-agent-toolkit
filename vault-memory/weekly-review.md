# vault-memory:weekly-review

> 한 주의 세션 로그 + 목표를 종합하여 주간 회고를 생성한다.

**기록 규격**: `~/mingming-vault/memory/format.md` 참조

## 트리거

- "주간 회고", "weekly review", "이번 주 정리"
- 일요일/월요일 세션 시 자동 제안

## 워크플로우

### 1. 데이터 수집

| 소스 | 경로 |
|------|------|
| 주간 목표 | `~/mingming-vault/projects/goals/weekly/YYYY-Www.md` |
| 세션 로그 (7일) | `~/mingming-vault/memory/daily/` |
| 일간 목표 (7일) | `~/mingming-vault/projects/goals/daily/` |
| 태스크 변화 | `~/mingming-vault/projects/` |

### 2. 분석

- **목표 달성률**: 주간 목표 체크리스트 기준 (완료/전체)
- **결정사항 취합**: 각 세션에서 모아 정리
- **핵심 배움 취합**: 각 세션에서 모아 정리
- **프로젝트별 진행**: 어떤 프로젝트에 시간 많이 썼는지

### 3. 회고 생성

```markdown
---
period: YYYY-Www
status: done
theme: "주간 테마"
updated_by: claude-code
updated_at: ISO-8601
---

## 목표 달성률
- [x] 목표 1 ✅
- [ ] 목표 2 (70%)
> 달성률: 2/3 (67%)

## 이번 주 결정사항
- [2/10] vault 구조 전환
- [2/11] vault-memory 스킬 설계

## 핵심 배움
- Quick Reference가 토큰 효율 핵심

## 프로젝트별 시간
| 프로젝트 | 세션 수 | 주요 작업 |
|---------|--------|----------|
| mingming-ai | 5 | vault 구조, 스킬 개발 |

## 다음 주 우선순위 제안
1. ...

## 회고
### 잘한 점
### 개선할 점
### 다음 주 포커스
```

### 4. 저장

**경로**: `~/mingming-vault/projects/goals/weekly/YYYY-Www.md`

- 파일 있으면: `## 회고` 이후 섹션 업데이트 (목표 섹션 보존)
- 파일 없으면: 전체 생성

### 5. Preserve 제안

장기 보관 가치 있는 배움/결정 발견 시:
> "MEMORY.md에 영구 저장할까요?" → `/vault-memory:preserve` 연계
