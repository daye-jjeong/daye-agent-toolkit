# work-digest 스킬 디자인

**Date:** 2026-02-27
**Status:** Approved

## 목적

Claude Code 세션 로그를 일일 요약하여 텔레그램으로 전송.
목표 대비 갭 분석 + 작업 패턴 피드백 포함.

## 아키텍처

하이브리드 파이프라인 (schedule-advisor 패턴):
- Tier 1: 스크립트 파싱 (토큰 0)
- Tier 2: LLM 분석 + 텔레그램 전송 (200-400 토큰/일)

## 파일 구조

```
work-digest/
  ├── SKILL.md                    # 스킬 정의
  ├── .claude-skill               # CC 메타데이터
  ├── scripts/
  │   ├── session_logger.py       # CC 훅 — 세션 종료 시 work-log에 기록
  │   ├── parse_work_log.py       # Tier 1 — .md 파싱 → JSON stdout
  │   └── daily_digest.py         # Tier 2 — LLM 요약 + 텔레그램 전송
  ├── work-log/                   # 일일 세션 로그 저장 (git tracked)
  │   └── state/
  │       └── session_logger_state.json
  └── references/
      └── prompt-template.md      # LLM 프롬프트
```

## 데이터 흐름

### 1. 세션 기록 (CC 훅 → session_logger.py)

트리거: PreCompact, SessionEnd 이벤트
입력: stdin JSON (session_id, transcript_path, cwd, hook_event_name)
출력: work-log/YYYY-MM-DD.md에 세션 섹션 append

기존 `_cc/vault_recorder.py`의 로직을 이관:
- transcript .jsonl 파싱 (수정 파일, 명령어, 에러, 토픽, 시간)
- 세션 마커를 daily .md에 append
- 중복 방지 (session_id + event 조합)

변경점:
- 저장 경로: ~/openclaw/vault/ → work-digest/work-log/
- cc-config.json 의존 제거 → 스크립트 내 상대경로 사용
- 태스크 진행 로그 (t-*.md append) 기능 제거

### 2. 일일 파싱 (parse_work_log.py)

입력: work-log/YYYY-MM-DD.md + goal-planner daily YAML
출력: JSON (stdout)

```json
{
  "date": "2026-02-27",
  "sessions": [...],
  "summary": {
    "total_sessions": 9,
    "total_duration_min": 322,
    "repos": {"dy-minions-squad": 4, ...},
    "total_files": 44,
    "total_errors": 2,
    "has_tests": false,
    "has_commits": true
  },
  "goals": {
    "source": "goal-planner daily YAML",
    "items": [...]
  }
}
```

### 3. 일일 다이제스트 (daily_digest.py)

입력: parse_work_log.py의 JSON (stdin 또는 파이프)
처리: LLM 분석 (하루 요약, 갭 분석, 패턴 피드백)
출력: 텔레그램 메시지 (clawdbot)

## 텔레그램 출력 예시

```
📋 2/27(금) 작업 다이제스트

⏱ 9세션 · 5시간 22분 · 파일 44개

📂 레포별:
  dy-minions-squad 4세션 (마크다운 렌더링, suggestion promotion...)
  daye-agent-toolkit 2세션 (correction-memory 설계)
  .openclaw 2세션 (크론 점검)
  cube-agent-toolkit 1세션 (pm-bot 검토)

🎯 목표 대비:
  ✅ correction-memory 설계 → 완료
  ⚠️ 테스트 코드 작성 → 작업 흔적 없음

💡 패턴 피드백:
  • 4개 레포 컨텍스트 스위칭 많음
  • 테스트 실행 0건
```

## 크론

| 스케줄 | 명령 |
|--------|------|
| `0 21 * * *` | `parse_work_log.py --date today \| daily_digest.py` |

## 마이그레이션

1. `_cc/vault_recorder.py` → `work-digest/scripts/session_logger.py` 이관
2. `.claude/settings.json` 훅 경로 업데이트
3. `cc-config.json`의 vault_root 불필요 (삭제 또는 유지)
4. 기존 ~/openclaw/vault/ 데이터는 마이그레이션 안 함 (새로 시작)
5. `skills.json`에 work-digest 추가

## 스코프 외

- 기존 vault 데이터 마이그레이션
- 태스크 진행 로그 (t-*.md) 기능
- 대화형 /work-log CC 명령
