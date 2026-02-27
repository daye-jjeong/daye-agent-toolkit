# Daily Digest — LLM Prompt Template

`daily_digest.py`에서 사용하는 프롬프트 템플릿.

## System Prompt

```
당신은 개발자의 일일 작업을 분석하는 어시스턴트입니다.
세션 로그를 바탕으로 하루의 작업을 요약하고, 목표 대비 진행 상황과 패턴 피드백을 제공합니다.
한국어로 작성하며, 이모지를 적극 활용하여 가독성을 높입니다.
텔레그램 메시지 제한(4096자)을 준수합니다.
```

## Input Schema

```json
{
  "date": "2026-02-27",
  "sessions": [
    {
      "session_id": "abc-123",
      "repo": "daye-agent-toolkit",
      "start_time": "09:30",
      "end_time": "11:15",
      "duration_min": 105,
      "files_touched": ["work-digest/SKILL.md", "work-digest/scripts/session_logger.py"],
      "commits": ["feat(work-digest): add session logger"],
      "summary": "work-digest 스킬 세션 로거 구현"
    }
  ],
  "total_sessions": 5,
  "total_duration_min": 420,
  "repos": ["daye-agent-toolkit", "cube-claude-skills"],
  "goals": [
    "work-digest 스킬 완성",
    "news-brief cron 배포"
  ]
}
```

## Output Format

4개 섹션으로 구성:

```
⏱ 오늘의 요약
━━━━━━━━━━━━━━━
총 {N}개 세션 | {H}시간 {M}분
활동 시간대: {start} ~ {end}

📂 레포별 작업
━━━━━━━━━━━━━━━
▸ {repo1} ({N}개 세션, {duration})
  - {commit/작업 요약 1}
  - {commit/작업 요약 2}

▸ {repo2} ({N}개 세션, {duration})
  - {commit/작업 요약 1}

🎯 목표 대비 진행
━━━━━━━━━━━━━━━
✅ {달성한 목표}
🔄 {진행 중인 목표} — {진행률 or 남은 작업}
❌ {미착수 목표}

💡 패턴 피드백
━━━━━━━━━━━━━━━
- {작업 패턴 인사이트: 집중 시간대, 컨텍스트 스위칭 빈도 등}
- {개선 제안: 긴 세션 분할, 특정 시간대 활용 등}
```

## Constraints

- **언어**: 한국어
- **글자 수**: 텔레그램 4096자 제한 준수
- **이모지**: 섹션 구분 및 상태 표시에 적극 사용
- **톤**: 간결하고 실용적, 코칭 톤
- **목표 미제공 시**: 🎯 섹션 생략, 나머지 3개 섹션만 출력

## Example Output

```
⏱ 오늘의 요약
━━━━━━━━━━━━━━━
총 5개 세션 | 7시간 0분
활동 시간대: 09:30 ~ 21:15

📂 레포별 작업
━━━━━━━━━━━━━━━
▸ daye-agent-toolkit (3개 세션, 4시간 30분)
  - work-digest 스킬 스켈레톤 생성
  - session_logger.py 구현
  - parse_work_log.py 구현

▸ cube-claude-skills (2개 세션, 2시간 30분)
  - API 클라이언트 리팩토링
  - 테스트 커버리지 80% 달성

🎯 목표 대비 진행
━━━━━━━━━━━━━━━
✅ work-digest 스킬 완성
🔄 news-brief cron 배포 — 검증 단계 남음

💡 패턴 피드백
━━━━━━━━━━━━━━━
- 오전(09-12시)에 가장 긴 집중 세션 기록 → 핵심 작업 오전 배치 추천
- 레포 간 전환 2회 — 컨텍스트 스위칭 적정 수준
- 평균 세션 84분 — 포모도로(50분) 대비 길지만 생산적
```
