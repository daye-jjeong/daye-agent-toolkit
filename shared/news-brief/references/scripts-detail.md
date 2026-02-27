# News Brief Scripts Detail

## `news_brief.py`

**Purpose:** RSS 수집 + 키워드 필터 + 스토리 클러스터링 + 스코어링

**Inputs:**
- `--feeds` (required): RSS 피드 URL 목록 파일
- `--keywords` (optional): 키워드 필터 파일
- `--max-items` (default: 5): 최대 출력 아이템 수
- `--since` (default: 0): 최근 N시간 이내 필터 (0=전체)
- `--output-format` (default: text): `text` (Telegram) 또는 `json` (compose 입력)
- `--no-rank`: 레거시 dedupe 모드 (클러스터링 대신 단순 중복 제거)

**Output:** JSON 배열 → `[{title, link, source, published, domain, tag, description, score, coverage}]`

## `kst_utils.py`

**Purpose:** KST 시간 변환 + 도메인 추출 공유 유틸

**Functions:**
- `parse_pub_date(raw)` → RSS 날짜 파싱 (RFC 2822, ISO 8601)
- `to_kst(dt)` / `format_kst(dt)` → KST 변환 + 포맷
- `format_pub_kst(raw)` → 날짜 문자열 → KST 포맷 문자열
- `extract_domain(url)` → URL에서 도메인 추출 (www. 제거)

## `compose-newspaper.py`

**Purpose:** 4-input 파이프라인 JSON → 신문 스키마 조합

**Inputs:**
- `--general`: General 파이프라인 JSON
- `--ai-trends`: AI Trends 파이프라인 JSON
- `--ronik`: Ronik 파이프라인 JSON
- `--community`: Community 파이프라인 JSON (Reddit via news_brief.py)
- `--highlight`: 오늘의 핵심 한줄 (optional)
- `--output`: 출력 파일 (미지정시 stdout)

**Output:** newspaper-schema.md 섹션 3 참고

**Key Logic:**
- General → 국제/국내/경제/기타 섹션 분리
- AI Trends → origin_source 기반 AI·테크 vs 커뮤니티 분리
- Community → Reddit 아이템 + AI Trends 커뮤니티 합산

## `enrich.py`

**Purpose:** compose 출력에서 번역/요약 필요 아이템 추출 → 적용

**Modes:**
- `extract --input FILE`: 영어 제목, RSS 바이라인, why 미작성 아이템 추출
- `apply --input FILE --enrichments FILE [--output FILE]`: 번역/요약 결과 적용

**Key Logic:**
- `_is_english()`: ASCII 비율 60% 초과 → 영어 판정
- `_is_raw_rss()`: 연합뉴스 바이라인, HTML 엔티티, 15자 미만 → RSS 원문 판정

## `render_newspaper.py`

**Purpose:** compose JSON → 신문 스타일 HTML 렌더링

**Inputs:**
- `--input`: compose JSON 파일 (미지정시 stdin)
- `--weather`: fetch_weather.py 출력 JSON (optional)
- `--output`: HTML 출력 파일 (미지정시 stdout)

**Output:** 밍밍 데일리 HTML (Noto Serif KR/Sans KR 폰트, 반응형)

## `fetch_weather.py`

**Purpose:** Open-Meteo API → 현재 날씨 + 옷차림 추천 (LLM 0 tokens)

**Inputs:**
- `--location` (default: 서울): 도시명
- `--output`: JSON 출력 파일

**Output:** `{location, date, current_temp, feels_like, high, low, humidity, condition, wind, outfit}`

## `save_to_vault.py`

**Purpose:** compose JSON → Obsidian vault 마크다운 저장

**Inputs:**
- `--input`: compose JSON 파일
- `--weather`: 날씨 JSON (optional)
- `--vault-dir` (default: ~/openclaw/vault): vault 경로

**Output:** `{vault-dir}/reports/news-brief/YYYY-MM-DD.md`

## `ai_trends_ingest.py`

**Purpose:** AI Trends Writer JSON → vault 마크다운 저장

**Input:** stdin으로 Writer vault JSON 수신

**Output:** `{vault-dir}/reports/ai-trends/YYYY-MM-DD.md`

## `breaking-alert.py`

**Purpose:** 15분 간격 속보 알림 (keyword scoring, LLM 0 tokens)

**Inputs:**
- `--sources`: rss_sources.json 경로
- `--keywords`: 고신호 키워드 파일
- `--since` (default: 1): 최근 N시간 이내
- `--dry-run`: Telegram 미전송

**Key Logic:**
- Tiered keyword scoring (🔴 high / 🟡 medium)
- Word boundary 매칭으로 오탐 방지
- `~/.cache/news-brief/seen.json`으로 중복 알림 방지
