# Daily Digest — LLM Prompt Template

`daily_digest.py`에서 사용하는 프롬프트 템플릿.

## System Prompt

```
당신은 개발자의 일일 작업을 분석하는 어시스턴트입니다.
세션 로그를 바탕으로 하루의 작업을 요약하고 패턴 피드백을 제공합니다.
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
      "time": "09:30",
      "duration_min": 105,
      "tag": "코딩",
      "summary": "work-digest 스킬 세션 로거 구현",
      "files": ["work-digest/SKILL.md"],
      "commands": ["git commit ..."]
    }
  ],
  "summary": {
    "total_sessions": 5,
    "total_duration_min": 420,
    "repos": {"daye-agent-toolkit": 3, "cube-backend": 2},
    "tokens": {"total": 50000000}
  }
}
```

## Output Format

3개 섹션으로 구성:

```
⏱ 오늘의 요약
━━━━━━━━━━━━━━━
총 {N}개 세션 | {H}시간 {M}분
🏷 작업 유형: 💻코딩 N건 · 🐛디버깅 N건

📂 레포별 작업
━━━━━━━━━━━━━━━
▸ {repo1} ({N}개 세션, {duration})
  - {작업 요약 1}
  - {작업 요약 2}

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

## Example Output

```
⏱ 오늘의 요약
━━━━━━━━━━━━━━━
총 5개 세션 | 7시간 0분
🏷 작업 유형: 💻코딩 3건(60%) · 🐛디버깅 2건(40%)

📂 레포별 작업
━━━━━━━━━━━━━━━
▸ daye-agent-toolkit (3개 세션, 4시간 30분)
  - work-digest 스킬 세션 요약 + 태깅 기능 구현
  - 텔레그램 채널 분리 및 config 일원화

▸ cube-backend (2개 세션, 2시간 30분)
  - Prisma 7 마이그레이션 검증
  - soft-delete extension 리팩토링

💡 패턴 피드백
━━━━━━━━━━━━━━━
- 오전(09-12시)에 가장 긴 집중 세션 기록 → 핵심 작업 오전 배치 추천
- 레포 간 전환 2회 — 컨텍스트 스위칭 적정 수준
```
