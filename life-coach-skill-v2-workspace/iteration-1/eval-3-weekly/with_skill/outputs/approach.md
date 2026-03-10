# Approach Notes — eval-3-weekly (with_skill)

## 참조한 파일

- `shared/life-coach/SKILL.md` — 주간 코칭 구성 7개 섹션 정의
- `shared/life-coach/references/coaching-prompts.md` — 각 섹션별 상세 지침, 임계값, 톤 레벨

## 적용한 프레임

### 섹션 매핑 (coaching-prompts.md 주간 코칭)

| 섹션 | SKILL.md 항목 | 적용 지침 |
|------|--------------|-----------|
| 📝 주간 정리 | 총 세션/시간/토큰 요약 | 완료 vs 진행중 구분, 캘린더 데이터 없어 미팅 비율 생략 |
| 🏷 태그·레포 분포 | 태그·레포 편중 분석 | 디버깅 30% > 25% → 테스트 커버리지 언급, 레포 편중 없음 확인 |
| 📅 요일별 생산성 | daily[].work_hours | 상위 2개 요일(화·월) 명시, 다음 주 일정 제안 |
| 🛌 휴식 패턴 | sessions=0인 날 | 일요일 완전 휴식 1일, 토요일 2h 작업 언급 |
| 🔍 방향성 코칭 | repeated_patterns 추적 | "새벽 1시 이후 작업 3회" 반복 패턴 → 구조적 원인 질문 |
| 💊 주간 건강 요약 | exercises/meals/check_ins | 운동 2일 최소선 언급, 수면 6.8h + 새벽 작업 연결 |
| 🔮 다음 주 생각해볼 것 | 패턴 기반 질문 2-3개 | 새벽 작업 구조, 디버깅 원인, 딥워크 구조화 |

### 톤 레벨 판단

- `repeated_patterns`: "새벽 1시 이후 작업" 3회 반복 → 이전 주에도 있던 패턴으로 가정 → **Level 1** (직접적 제안)
- 전반적으로 Level 0-1 사이. 수면/새벽 작업 섹션에서만 직접적 언급, 나머지는 질문형

### 특이 처리

1. **repeated_patterns 추적**: coaching-prompts.md 지침대로 "지난주에도 언급된 패턴이 이번 주도 반복됐다"는 표현 직접 사용
2. **디버깅 임계값**: 25% 기준 초과(30%)이므로 테스트 커버리지 점검 언급 (coaching-prompts.md 명시 지침)
3. **설계 10% 연결**: 디버깅 30%와 설계 10%를 연결해 다음 주 행동 제안으로 연결
4. **수면·새벽 작업 연결**: avg_sleep 6.8h와 새벽 패턴을 단순 나열이 아닌 인과 구조로 해석
5. **🔮 질문 3개**: coaching-prompts.md에서 "2-3개 질문" 지침 → 3개 생성, 답 없이 질문만

## SKILL.md와 coaching-prompts.md 일치 여부

SKILL.md의 주간 코칭 구성(7개 항목)과 coaching-prompts.md의 섹션이 정확히 일치함. 양쪽 모두 참조해 섹션별 세부 기준(임계값, 표현 방식)은 coaching-prompts.md를 우선 적용.

## 생략한 항목

- `pantry_expiry`: 데이터 없어 생략
- `캘린더 이벤트`: 데이터 없어 미팅 vs 코딩 시간 비율 생략
- `symptoms`: 데이터 없어 생략
