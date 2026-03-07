# Behavioral Extraction — 행동 신호 추출 파이프라인

## 목적

CC 세션에서 사용자의 의사결정, 시행착오, 반복 패턴을 자동 추출하여
코칭이 구체적 피드백과 자동화 제안을 할 수 있게 한다.

## Design

### 아키텍처

```
SessionEnd hook
  ├─ [기존] extract_conversation() → sonnet → 요약 (tag + summary)
  └─ [신규] extract_user_messages() → sonnet → 행동 추출 (decisions, mistakes, patterns)
                                                    ↓
                                          work-log에 기록 + sync_cc → SQLite
                                                    ↓
                                    behavioral_signals 테이블 (별도)
                                                    ↓
                                    daily/weekly 코칭이 SQL 집계로 소비
```

### 변경 사항

1. **모델 업그레이드**: haiku → sonnet (요약 + 행동 추출 모두)
2. **신규 함수**: `extract_user_messages()` — transcript에서 user 메시지만 추출, 8000자 윈도우
3. **신규 함수**: `extract_behavioral_signals()` — sonnet에게 행동 신호 추출 요청
4. **work-log 포맷 확장**: 세션 섹션에 `**결정**:`, `**시행착오**:` 추가
5. **DB 스키마**: `behavioral_signals` 테이블 신규
6. **sync_cc.py**: 행동 신호를 behavioral_signals 테이블에 INSERT
7. **코칭 프롬프트**: 반복 패턴 집계 데이터를 data_section에 포함

### behavioral_signals 테이블

```sql
CREATE TABLE IF NOT EXISTS behavioral_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    signal_type TEXT NOT NULL,  -- 'decision', 'mistake', 'pattern'
    content TEXT NOT NULL,
    repo TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_signals_date ON behavioral_signals(date);
CREATE INDEX IF NOT EXISTS idx_signals_type ON behavioral_signals(signal_type);
```

### signal_type 정의

- **decision**: 사용자가 명시적 선택을 한 순간. "A 대신 B로 하자", "sonnet 쓰자"
- **mistake**: 되돌린 것, 교정한 것, 후회한 것. "아 이거 아니었네", "테스트 먼저 할걸"
- **pattern**: 세션 내 관찰되는 작업 습관. "설계 없이 바로 코딩", "에러 나고 나서야 로그 확인"

### 행동 추출 프롬프트 (sonnet)

입력: user 메시지만 추출한 텍스트 (8000자)
출력: JSON

```
다음은 Claude Code 세션에서 사용자가 보낸 메시지들이다.
레포: {repo}

{user_messages}

이 사용자의 행동 신호를 추출해라. 각 항목은 1줄, 20자 이내.
없으면 빈 배열.

JSON으로 출력:
{"decisions": [...], "mistakes": [...], "patterns": [...]}
```

### 코칭 소비 방식

daily_coach.py가 data_section에 추가:
```sql
-- 오늘의 행동 신호
SELECT signal_type, content FROM behavioral_signals WHERE date = ?

-- 최근 7일 반복 패턴 (2회 이상)
SELECT content, COUNT(*) as cnt FROM behavioral_signals
WHERE date >= ? AND signal_type IN ('mistake', 'pattern')
GROUP BY content HAVING cnt >= 2
ORDER BY cnt DESC LIMIT 5
```

### hook 스크립트 LLM subprocess 예외

`.claude/rules/correction-20260307-2030-no-subprocess-llm.md` 규칙의 예외:
session_logger.py는 hook 스크립트이며 스킬 스크립트가 아니다.
SessionEnd에서의 LLM 호출 2회(요약 + 행동 추출)를 허용된 예외로 명시한다.

### 비용

- 세션당 sonnet 2회: ~$0.10
- 일 10-15세션 기준: $1.0-1.5/일
