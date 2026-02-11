# vault-memory:resume

> 이전 세션 로그를 스캔하여 컨텍스트를 빠르게 복원한다.
> Quick Reference 우선 스캔으로 토큰 절약.

**기록 규격**: `~/mingming-vault/memory/format.md` 참조

## 트리거

- 세션 시작 시: "resume", "이어서", "어제 뭐 했지", "컨텍스트 복원"
- 파라미터 없이 호출하면 기본 3일

## 파라미터

| 형식 | 예시 | 동작 |
|------|------|------|
| (없음) | `/vault-memory:resume` | 최근 3일 Quick Reference |
| N | `resume 7` | 최근 7일 Quick Reference |
| 키워드 | `resume vault` | 최근 30일 중 키워드 매칭 |
| N+키워드 | `resume 14 dashboard` | 최근 14일 중 키워드 매칭 |

## 워크플로우

### 1. 세션 로그 스캔

**경로**: `~/mingming-vault/memory/daily/`

1. 해당 기간의 `YYYY-MM-DD.md` 파일 목록 (최신순)
2. **1차: Quick Reference만 스캔** — 각 파일의 `## Quick Reference` 섹션만 읽음
3. 키워드 있으면: Topics + 불릿 항목에서 매칭되는 파일만 필터

### 2. 브리핑 출력

```markdown
## 📋 세션 브리핑 (최근 N일)

### 2026-02-11 (화)
**Topics:** vault-memory, hooks
**Outcome:** 7개 스킬 구현, format.md 작성
- vault memory plugin 구조 설계
- SessionEnd hook 구현

### 2026-02-10 (월)
**Topics:** dashboard, cron
**Outcome:** 대시보드 일간 목표 표시 추가
- 프로젝트별 컬러 적용
```

### 3. 미완료 항목 하이라이트

Quick Reference 스캔 중 미완료/대기 항목 감지 시:

```markdown
### ⚠️ 미완료 항목
- [2/11] inbox-process 스킬 테스트
- [2/10] cron email-monitor 모델 오류 수정
```

### 4. 상세 로드 (선택)

브리핑 후:
> "특정 날짜의 전체 세션을 볼까요? (예: 2/10, 또는 '전체')"

- 날짜 지정: 해당 일자 전체 세션 로드
- "전체": 모든 날짜 전체 로드 (토큰 주의 경고)
- 스킵: 브리핑만으로 종료

## 토큰 효율

- Quick Reference만 = 일당 ~100토큰
- 전체 로드 = 일당 ~500-1000토큰
- 기본 3일 Quick Reference ≈ 300토큰으로 컨텍스트 복원
