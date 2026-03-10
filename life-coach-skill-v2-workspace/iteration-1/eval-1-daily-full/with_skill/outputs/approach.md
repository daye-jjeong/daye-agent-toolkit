# Skill Application Summary — eval-1-daily-full (with_skill)

## 사용한 스킬 파일

- `shared/life-coach/SKILL.md` — 코칭 구조 및 실행 절차 확인
- `shared/life-coach/references/coaching-prompts.md` — 섹션별 생성 프레임 적용

## 적용 절차

### 1. 코칭 시작 — 의도 확인

SKILL.md의 "코칭 시작 — 의도 확인" 단계를 따랐다.
사용자가 "오늘 코칭해줘"로 특정 섹션 요청 없이 요청했으므로, `references/coaching-prompts.md` 전체 프레임을 적용했다.

### 2. 데이터 준비 (시뮬레이션)

실제 `daily_coach.py --json` 실행 대신, 제공된 샘플 데이터를 사용했다:

```
sessions: 3개
  - daye-agent-toolkit: 2세션, 코딩, has_commits=1
  - cube-claude-skills: 1세션, 리서치, has_commits=0
total_hours: 4.2h
token_total: 180K
check_in: sleep=6.5h, exercise=없음
pantry_expiry: 토마토 만료
```

### 3. 섹션별 적용

coaching-prompts.md의 일일 코칭 프레임 8개 섹션 전체 적용:

| 섹션 | 적용 여부 | 처리 |
|------|-----------|------|
| 📝 오늘의 정리 | ✅ | 완료(커밋됨) vs 진행중 명확히 구분 |
| 📂 레포별 상세 | ✅ | 2개 레포, 각 커밋 여부 표시 |
| 📊 집중도 지표 | ✅ | 세션 평균 84분, 짧은 세션 0% |
| 🔍 코칭 | ✅ | 수면 부족 + 운동 없음 패턴 짚음, 리서치 메모 누락 위험 언급 |
| 🤖 자동화 제안 | ✅ (생략) | 반복 패턴 없음 → 섹션 생략 |
| ⏭️ 내일 이어할 것 | ✅ | cube-claude-skills 리서치 이어야 함 |
| 💊 건강 | ✅ | check_in 수면 6.5h, 운동 없음 반영 |
| 🧊 유통기한 | ✅ | 토마토 만료 |
| 💬 마무리 질문 | ✅ | 리서치 기록 미비 패턴 기반 질문 1개 |

### 4. 톤 레벨

escalation_level 데이터 없음 → Level 0 (기본) 적용.
질문형 + 부드러운 넛지 톤 유지. 수면 부족과 운동 없음에 대해 직접적 제안 없이 확인 질문 형태로 처리.

### 5. 규칙 준수

- `correction-20260307-2030-no-subprocess-llm`: Python 스크립트 subprocess 호출 없음. LLM이 직접 코칭 수행.
- `coaching-prompts.md` 지침: "완료"와 "진행중" 명확 구분 적용.
- 한국어 톤 규칙(`tone-kr.md`): 번역체, 아첨어, 상투어 없음.

## 주요 판단

- 2개 레포 전환 있었지만 세션 평균 84분으로 집중도 양호 → 컨텍스트 스위칭 이슈로 처리하지 않음
- 자동화 제안 섹션은 반복 패턴 데이터 없어 생략 (coaching-prompts.md 지침 준수)
- 마무리 질문은 오늘 가장 눈에 띄는 패턴(리서치 커밋 없음 → 기록 불확실) 선택
