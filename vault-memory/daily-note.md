# vault-memory:daily-note

> 주간/월간 목표 + 미완료 항목 기반으로 일간 계획을 생성한다.

**기록 규격**: `~/mingming-vault/memory/format.md` 참조

## 트리거

- "오늘 계획", "daily note", "일간 노트", "오늘 뭐 하지"
- 매일 아침 세션 시작 시 자동 제안

## 워크플로우

### 1. 입력 데이터 수집

| 소스 | 경로 | 용도 |
|------|------|------|
| 월간 목표 | `~/mingming-vault/projects/goals/monthly/YYYY-MM.md` | 이번 달 방향 |
| 주간 목표 | `~/mingming-vault/projects/goals/weekly/YYYY-Www.md` | 이번 주 구체 목표 |
| 어제 세션 | `~/mingming-vault/memory/daily/YYYY-MM-DD.md` | 미완료 항목 |
| 진행 중 태스크 | `~/mingming-vault/projects/` (status: in_progress) | 현재 작업 |

### 2. 에너지 레벨 확인

> "오늘 에너지 레벨은? (high / medium / low)"

### 3. 타임블록 생성

| 에너지 | 전략 |
|--------|------|
| **high** | 집중 작업 먼저 (오전), 루틴/미팅 (오후) |
| **medium** | 균형 배분, 중간 휴식 블록 |
| **low** | 루틴/가벼운 것 위주, 핵심 1개만 |

### 4. 저장

**경로**: `~/mingming-vault/projects/goals/daily/YYYY-MM-DD.md`

```markdown
---
date: YYYY-MM-DD
day_of_week: 요일
energy_level: medium
status: active
linked_weekly: "[[YYYY-Www]]"
updated_by: claude-code
updated_at: ISO-8601
---

## 오늘 목표
- [ ] 목표 1 (← 주간 목표)
- [ ] 목표 2 (← 미완료)
- [ ] 목표 3

## 타임블록
| 시간 | 할 일 | 프로젝트 |
|------|-------|---------|
| 09:00-10:00 | 탈잉 + 아침 | routine |
| 10:00-12:00 | 집중 작업 1 | project |
| 13:00-15:00 | 집중 작업 2 | project |
| 15:00-17:00 | 리뷰/커뮤니케이션 | misc |
| 19:00-20:00 | 운동 | health |

## 체크리스트
- [ ] 탈잉 아침 인증
- [ ] 운동
- [ ] 탈잉 저녁 인증
```

- 파일 이미 있으면: 덮어쓸지 사용자 확인
- Obsidian daily-template.md 형식과 호환 유지

## 주의사항

- `linked_weekly` 필드로 주간 목표와 연결
- 타임블록은 제안일 뿐 → 사용자 조정 가능
