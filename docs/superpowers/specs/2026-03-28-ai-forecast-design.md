# AI 산업 주간 예측 (news-brief forecast 모듈)

## 개요

news-brief의 일일 뉴스페이퍼 데이터를 SQLite에 아카이브하고, 주간 시그널을 추출하여 AI 산업 예측을 자동 생성한다. 예측 결과를 기록하고 사후 검증하는 자가개선 루프를 포함한다.

## 설계 결정

| 결정 | 선택 | 이유 |
|------|------|------|
| 데이터 저장 | SQLite | 시계열 집계 쿼리 필요. JSON 아카이브는 매번 파싱 비용 |
| 통합 방식 | news-brief 확장 | 데이터 소스가 동일. 별도 스킬은 의존성만 추가 |
| 예측 주기 | 주간 (월요일) | 단기 피드백 루프. 안정 후 월간 확장 가능 |
| 예측 생성 | 자동 크론 + 자가개선 | LLM이 시그널 + 과거 오류 패턴을 보고 예측 생성 |
| 검증 타이밍 | 예측 생성 시 함께 | 주간 크론 1회에 검증 + 분석 + 생성을 묶음 |
| 기존 파이프라인 | 안 건드림 | JSON 파이프라인은 그대로, 끝에서 DB로 복사만 |

## 아키텍처

```
기존 파이프라인 (변경 없음):
  RSS → news_brief.py → compose.py → enrich.py → render.py → HTML + 텔레그램

추가:
  enrich 결과 JSON ──→ archive.py ──→ forecast.db (articles, article_entities)
                                           ↓
  매주 월요일 크론 ──→ forecast.py ──→ 시그널 추출 + 검증 + 예측 생성
                                           ↓
                                      텔레그램 전송
```

## 데이터베이스 스키마

DB 경로: `~/.local/share/news-brief/forecast.db`

### articles — 일일 뉴스 아카이브

```sql
CREATE TABLE articles (
  id          INTEGER PRIMARY KEY,
  date        TEXT NOT NULL,
  title       TEXT NOT NULL,
  headline    TEXT,
  url         TEXT UNIQUE NOT NULL,
  source      TEXT,
  section     TEXT,
  tag         TEXT,
  score       REAL,
  coverage    INTEGER DEFAULT 1,
  summary     TEXT,
  created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_articles_date ON articles(date);
CREATE INDEX idx_articles_section ON articles(section);
```

### article_entities — 기사별 엔티티

```sql
CREATE TABLE article_entities (
  article_id  INTEGER REFERENCES articles(id),
  entity      TEXT NOT NULL,
  PRIMARY KEY (article_id, entity)
);

CREATE INDEX idx_entities_entity ON article_entities(entity);
```

### forecasts — 주간 예측 세트

```sql
CREATE TABLE forecasts (
  id            INTEGER PRIMARY KEY,
  week          TEXT NOT NULL UNIQUE,
  created_at    TEXT DEFAULT (datetime('now')),
  signal_json   TEXT NOT NULL
);
```

### predictions — 개별 예측 항목

```sql
CREATE TABLE predictions (
  id            INTEGER PRIMARY KEY,
  forecast_id   INTEGER REFERENCES forecasts(id),
  claim         TEXT NOT NULL,
  confidence    REAL NOT NULL,
  reasoning     TEXT NOT NULL,
  deadline      TEXT NOT NULL,
  status        TEXT DEFAULT 'open',
  verified_at   TEXT,
  verification  TEXT
);

CREATE INDEX idx_predictions_status ON predictions(status);
CREATE INDEX idx_predictions_deadline ON predictions(deadline);
```

### improvement_log — 자가개선 기록

```sql
CREATE TABLE improvement_log (
  id            INTEGER PRIMARY KEY,
  week          TEXT NOT NULL,
  accuracy      REAL,
  bias_analysis TEXT,
  lesson        TEXT,
  created_at    TEXT DEFAULT (datetime('now'))
);
```

## 스크립트

### archive.py — 일일 아카이브

- 입력: enriched newspaper JSON (compose + enrich 완료 결과)
- 동작: articles + article_entities에 INSERT OR IGNORE
- 엔티티 추출: 기존 news_brief.py의 엔티티 추출 로직 재사용 (한국어 2+자, 영어 3+자)
- 실행: 뉴스페이퍼 크론 파이프라인 끝에 추가
- 의존: stdlib만 사용 (sqlite3)

### forecast.py — 주간 예측 파이프라인

서브커맨드 구조:

#### `forecast.py signals`
지난 7일 DB 데이터에서 시그널 추출. JSON 출력.

| 시그널 | 로직 |
|--------|------|
| 키워드 급증 | 이번 주 vs 직전 주 엔티티 빈도, 2배+ 증가 |
| 신규 엔티티 | 직전 4주 내 없었던 엔티티 |
| 커버리지 집중 | coverage 3+ 스토리 |
| 소스 분포 변화 | 섹션별 기사 수 비율 변화 |
| high-score 기사 | score 상위 10개 |

#### `forecast.py verify`
deadline이 지난 open 상태 predictions + 해당 기간 기사 목록을 추출.

- 입력: 없음 (DB에서 직접 조회)
- 동작: deadline <= today인 open predictions를 조회하고, 각 prediction의 생성일~deadline 기간의 articles를 함께 추출
- 출력: `[{prediction, related_articles}]` JSON
- 판정은 이 스크립트가 하지 않음. LLM 크론 에이전트가 출력을 보고 hit/miss/expired를 판정한 뒤, `forecast.py update-status --id <id> --status hit --verification "근거"` 로 DB를 업데이트

#### `forecast.py update-status`
LLM이 판정한 결과를 DB에 기록.

- 입력: `--id`, `--status` (hit/miss/expired), `--verification`
- 동작: predictions 테이블 업데이트

#### `forecast.py analyze`
누적 적중률 + 편향 패턴 분석.

- predictions 전체에서 hit/miss 비율 계산
- 카테고리별, confidence 구간별 적중률
- 반복되는 오류 패턴 식별 (예: "발표 시점 과대예측")
- improvement_log에 기록
- 출력: 분석 결과 JSON

#### `forecast.py report`
텔레그램 전송용 포맷 생성.

- verify + analyze + signals 결과를 통합
- 텔레그램 메시지 형식으로 포맷팅

## 주간 크론 흐름

스케줄: `0 9 * * 1` (매주 월요일 09:00 KST)

```
1. forecast.py verify   → deadline 지난 예측 판정
2. forecast.py analyze  → 적중률 + 편향 분석 → improvement_log 기록
3. forecast.py signals  → 이번 주 시그널 추출
4. LLM이 시그널 + improvement_log 최근 3건을 보고 예측 3~5개 생성
5. predictions 테이블에 저장
6. forecast.py report   → 텔레그램 메시지 포맷
7. 텔레그램 전송
```

4~5번은 LLM(크론 에이전트)이 수행. forecast.py는 데이터 준비만.

## 자가개선 루프

```
예측 생성 (week N)
    ↓
1주 경과
    ↓
검증 (week N+1): 뉴스 데이터로 hit/miss 판정
    ↓
분석: 누적 적중률 + 편향 패턴
    ↓
improvement_log에 lesson 기록
    ↓
새 예측 생성 시 최근 3건의 lesson을 컨텍스트로 제공
    ↓
LLM이 과거 실수를 인지하고 보정된 예측 생성
```

## 텔레그램 출력 포맷

```
📊 AI 주간 예측 — 2026-W13

── 지난 예측 검증 ──
✅ HIT: Anthropic Claude 신모델 발표 (confidence: 0.8)
❌ MISS: Google Gemini 오픈소스 전환 (confidence: 0.6)
⏰ EXPIRED: Meta LLaMA 4 출시 (confidence: 0.5)

누적 적중률: 62% (8/13)

── 자가분석 ──
편향: 제품 발표 시점을 평균 1주 빠르게 예측하는 경향
교훈: 발표 시그널이 있어도 deadline을 +1주 보수적으로 잡기

── 이번 주 시그널 ──
• "Claude" 언급 3.2배 급증 (전주 대비)
• 신규 엔티티: "Claude Channel", "Anthropic MCP"
• AI·테크 섹션 비중 41% → 58%

── 새 예측 ──
1. [0.75] Anthropic이 2주 내 MCP 관련 대형 업데이트 발표
   → 근거: Claude/MCP 엔티티 동시 급증 + 공식 블로그 3건
2. [0.60] OpenAI가 4월 내 GPT-5 프리뷰 공개
   → 근거: o4 키워드 등장 + GPT-5 루머 coverage 3+
3. [0.45] Google DeepMind 오픈소스 모델 신규 출시
   → 근거: Gemma 관련 신규 엔티티 등장, 낮은 커버리지
```

## 크론 설정

cron.json에 추가:

```json
{
  "name": "weekly-forecast",
  "schedule": "0 9 * * 1",
  "target": "weekly-forecast",
  "reason": "cron: weekly-forecast",
  "instructions": "news-brief 스킬의 '주간 예측' 섹션을 따르세요.",
  "recipients": ["daye"]
}
```

일일 뉴스페이퍼 크론 instructions에 archive.py 실행 단계 추가.

## 파일 구조

```
shared/news-brief/
  scripts/
    archive.py          ← NEW: enriched JSON → DB 적재
    forecast.py         ← NEW: signals / verify / analyze / report
  references/
    forecast-schema.md  ← NEW: DB 스키마 + 시그널/예측 JSON 스키마
  SKILL.md              ← UPDATE: forecast 섹션 추가
  cron.json             ← UPDATE: weekly-forecast 크론 추가
```

## 제약사항

- archive.py, forecast.py는 stdlib만 사용 (sqlite3, json, argparse)
- LLM subprocess 호출 금지 (스크립트는 데이터 준비만, LLM 판단은 크론 에이전트가 수행)
- 첫 주간 예측은 배포 후 최소 7일 데이터 축적 후 가능
- 예측 개수: 주당 3~5개 (과다 예측 방지)
- confidence는 0.0~1.0 범위, 0.5 미만도 허용 (불확실성 인정)
