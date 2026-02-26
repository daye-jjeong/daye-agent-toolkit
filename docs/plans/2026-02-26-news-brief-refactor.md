# News Brief v0.5.0 Refactoring Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** AI Trends 필드 스키마 정규화, 죽은 코드 제거, 문서 일괄 갱신으로 기술 부채 청산

**Architecture:** compose-newspaper.py의 AI Trends 매핑을 `url`/`source_name` 분리 스키마로 전환. 공유 유틸을 kst_utils.py에 통합. analyzer.py 삭제 후 문서를 현행 코드에 맞게 전면 갱신.

**Tech Stack:** Python 3.12+ (stdlib only), Markdown

---

### Task 1: kst_utils.py에 extract_domain() 추가

**Files:**
- Modify: `news-brief/scripts/kst_utils.py`

**Step 1: 유틸 함수 추가**

`kst_utils.py` 끝에 추가:

```python
def extract_domain(url: str) -> str:
    """Extract domain from URL, stripping 'www.' prefix.

    Returns the input as-is if not a valid HTTP(S) URL.
    """
    if not url or not url.startswith("http"):
        return url
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url
```

상단 import에 `from urllib.parse import urlparse` 추가.

**Step 2: 검증**

Run: `python3 -c "from kst_utils import extract_domain; print(extract_domain('https://www.openai.com/blog'))"`
Expected: `openai.com`

**Step 3: Commit**

```bash
git add news-brief/scripts/kst_utils.py
git commit -m "refactor(news-brief): extract_domain 유틸을 kst_utils.py에 추가"
```

---

### Task 2: compose-newspaper.py 필드 매핑 정규화

**Files:**
- Modify: `news-brief/scripts/compose-newspaper.py`

**Step 1: _extract_domain() 제거, kst_utils.extract_domain 사용**

import 변경:
```python
# Before
from kst_utils import format_pub_kst

# After
from kst_utils import extract_domain, format_pub_kst
```

`_extract_domain()` 함수 전체 삭제 (lines 169-175).
`from urllib.parse import urlparse` import도 삭제.

**Step 2: map_ai_trends_items() 필드 매핑 수정**

```python
def map_ai_trends_items(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Map AI Trends items → (main_items, community_items).

    Supports two input formats:
      - Writer vault format: name, source (URL), source_name, origin_source
      - Researcher format (fallback): name/title, url, source, origin_source
    """
    main, community = [], []
    for it in items:
        # URL: prefer explicit 'url', fallback to 'source' (writer vault format)
        url = it.get("url") or it.get("source", "")
        # Source name: prefer 'source_name', fallback to domain extraction
        source_name = it.get("source_name") or extract_domain(url)

        mapped = {
            "headline": it.get("name") or it.get("title", ""),
            "url": url,
            "source": source_name,
            "tag": it.get("category", ""),
            "published": format_pub_kst(it.get("published")),
            "summary": _clean_community_summary(it.get("summary", "")),
            "why": it.get("why", ""),
            "origin_source": it.get("origin_source", ""),
        }
        if _is_community(it):
            community.append(mapped)
        else:
            main.append(mapped)
    return main, community
```

**Step 3: map_community_items()에도 extract_domain 적용**

`map_community_items()`의 source 필드:
```python
"source": it.get("source", "") or extract_domain(it.get("url") or it.get("link", "")),
```

**Step 4: 검증**

Run: `cd news-brief/scripts && python3 compose-newspaper.py --general /tmp/general.json --ai-trends /tmp/ai_trends_data.json --ronik /tmp/ronik.json --community /tmp/community.json --output /tmp/test_composed.json`
Expected: `✅ /tmp/test_composed.json (6 sections)`

확인: `python3 -c "import json; d=json.load(open('/tmp/test_composed.json')); ai=[s for s in d['sections'] if 'AI' in s['title']][0]; print(ai['items'][0]['headline'], ai['items'][0]['url'][:50], ai['items'][0]['source'])"`
Expected: headline이 비어있지 않고, url이 http로 시작, source가 도메인명

**Step 5: Commit**

```bash
git add news-brief/scripts/compose-newspaper.py
git commit -m "refactor(news-brief): AI Trends 필드 매핑 정규화 — url/source_name 분리"
```

---

### Task 3: enrich.py에 origin_source 보존

**Files:**
- Modify: `news-brief/scripts/enrich.py`

**Step 1: extract() 함수에 origin_source 포함**

`extract()` 함수의 `items_to_enrich[key]` dict에 필드 추가:

```python
items_to_enrich[key] = {
    "headline": headline,
    "summary": summary[:200] if summary else "",
    "url": item.get("url", ""),
    "source": item.get("source", ""),
    "tag": item.get("tag", ""),
    "origin_source": item.get("origin_source", ""),  # 추가
    "needs": needs,
}
```

**Step 2: 검증**

Run: `python3 enrich.py extract --input /tmp/test_composed.json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); items=[v for v in d['items'].values() if v.get('origin_source')]; print(f'{len(items)} items with origin_source')"`
Expected: `origin_source`가 있는 아이템 수 > 0

**Step 3: Commit**

```bash
git add news-brief/scripts/enrich.py
git commit -m "fix(news-brief): enrich.py extract에 origin_source 필드 보존"
```

---

### Task 4: analyzer.py 삭제

**Files:**
- Delete: `news-brief/scripts/analyzer.py`
- Delete: `news-brief/scripts/__pycache__/` (전체 정리)

**Step 1: 파일 삭제**

```bash
git rm news-brief/scripts/analyzer.py
rm -rf news-brief/scripts/__pycache__
echo "__pycache__/" >> news-brief/.gitignore  # 없으면 생성
```

**Step 2: analyzer.py 참조 검색 — 코드에서 import 없는지 확인**

Run: `grep -r "analyzer" news-brief/scripts/ --include="*.py" -l`
Expected: 결과 없음 (어떤 스크립트도 analyzer를 import하지 않음)

**Step 3: Commit**

```bash
git add -A news-brief/scripts/ news-brief/.gitignore
git commit -m "refactor(news-brief): analyzer.py 삭제 — enrich.py + render로 대체됨"
```

---

### Task 5: Researcher/Writer 프롬프트 스키마 업데이트

**Files:**
- Modify: `news-brief/references/ai_trends_team/researcher.md`
- Modify: `news-brief/references/ai_trends_team/writer.md`

**Step 1: researcher.md — 출력 스키마 정리**

구조화 항목의 JSON 예시를 변경:

```json
{
  "title": "제목 (반드시 한국어로 번역)",
  "url": "https://...",
  "source_name": "소스명 (OpenAI Blog, TechCrunch 등)",
  "origin_source": "수집 출처명 (rss_sources.json의 name 값 그대로)",
  "publishedAt": "YYYY-MM-DD",
  "summary_1line": "한국어 1줄 요약 (핵심만)",
  "why_it_matters": "왜 중요한가? (비즈니스/기술 관점, 1-2문장, 한국어)",
  "tags": ["agent", "llm", "open-source", ...],
  "category": "Models|Tools|Policy|Open-source|Business|Other"
}
```

기존 `"source"` 필드를 `"source_name"`으로 변경.
기존 `source` 설명("소스명")을 `source_name`으로 이동.

Output Format JSON의 items에도 동일 반영:
`"source": "..."` → `"source_name": "..."`

**Step 2: writer.md — vault JSON 스키마 정리**

vault 적재용 JSON의 items를 변경:

```json
{
  "name": "제목 (반드시 한국어)",
  "category": "Models|Tools|Policy|Open-source|Business|Other",
  "summary": "요약 (한국어, 2-3문장)",
  "why": "왜 중요한가? (1-2문장, 한국어)",
  "url": "https://...",
  "source_name": "소스 매체명",
  "origin_source": "수집 출처명 (Researcher 값 그대로 유지)",
  "tags": ["agent", "llm", ...]
}
```

기존 `"source": "https://..."` → `"url": "https://..."` + `"source_name"` 분리.

**Step 3: Commit**

```bash
git add news-brief/references/ai_trends_team/researcher.md news-brief/references/ai_trends_team/writer.md
git commit -m "docs(news-brief): researcher/writer 프롬프트 필드 스키마 정규화"
```

---

### Task 6: VERSION + CHANGELOG 갱신

**Files:**
- Modify: `news-brief/VERSION`
- Modify: `news-brief/CHANGELOG.md`

**Step 1: VERSION → 0.5.0**

파일 내용을 `0.5.0`으로 교체.

**Step 2: CHANGELOG — v0.3.0 ~ v0.5.0 추가**

`[Unreleased]` 섹션을 비우고 아래 추가:

```markdown
## [0.5.0] - 2026-02-26

### Changed
- AI Trends 스키마 정규화: `source` → `url` + `source_name` 분리
- `map_ai_trends_items()` backward-compatible 필드 매핑
- `extract_domain()` 유틸을 kst_utils.py로 통합

### Removed
- `analyzer.py` 삭제 (enrich.py + render_newspaper.py로 대체)

### Fixed
- `enrich.py extract`에서 `origin_source` 필드 보존
- compose-newspaper.py 필드 매핑 불일치 수정

### Docs
- SKILL.md 전면 갱신 (community 파이프라인, 필드 스키마)
- newspaper-schema.md 신규 생성
- scripts-detail.md 전체 스크립트 문서화
- usage-examples.md, output-example.md 현행화
- researcher.md, writer.md 필드 스키마 정규화

## [0.4.0] - 2026-02-21

### Added
- `enrich.py`: 영어→한국어 번역 + 요약(why) 파이프라인
- `breaking-alert.py`: 15분 간격 속보 알림 (keyword scoring, LLM 0 tokens)
- `origin_source` 필드: 수집 출처 추적 (커뮤니티 섹션 분류용)
- `community_feeds.txt`, `community_keywords.txt`: Reddit RSS 별도 수집
- `compose-newspaper.py`에 `--community` 입력 채널

### Changed
- HN을 AI-Tech 카테고리로 복원 (커뮤니티에서 분리)
- 커뮤니티 소스에서 HN 제거, Reddit만 유지

## [0.3.0] - 2026-02-15

### Added
- `compose-newspaper.py`: 3-pipeline JSON 조합 (General + AI + Ronik)
- `render_newspaper.py`: JSON → 신문 스타일 HTML 렌더링
- `save_to_vault.py`: Obsidian vault 저장
- `fetch_weather.py`: Open-Meteo 날씨 + 옷차림 (0 tokens)
- `ai_trends_ingest.py`: AI 트렌드 vault 적재
- `kst_utils.py`: KST 시간 변환 유틸
- AI Trends 3-agent team (researcher/writer/executor)
- Story clustering + entity-based scoring in news_brief.py
```

**Step 3: Commit**

```bash
git add news-brief/VERSION news-brief/CHANGELOG.md
git commit -m "docs(news-brief): VERSION 0.5.0 + CHANGELOG v0.3-v0.5 추가"
```

---

### Task 7: SKILL.md 전면 갱신

**Files:**
- Modify: `news-brief/SKILL.md`

**Step 1: 헤더 + Architecture 갱신**

버전을 `0.5.0 | Updated: 2026-02-26`으로 변경.

Architecture diagram에 community 파이프라인 반영:
```
Pipeline 1 (General):  news_brief.py --output-format json  ─┐
Pipeline 2 (AI):       AI Trends Team (3-agent)              ├→ compose-newspaper.py → enrich.py → render_newspaper.py → HTML
Pipeline 3 (Ronik):    news_brief.py --output-format json  ─┤                                     save_to_vault.py    → Vault
Community  (Reddit):   news_brief.py --output-format json  ─┘                                                         → Telegram
Pipeline 4 (Breaking): breaking-alert.py (*/15 cron)
```

**Step 2: Input Files 섹션 — 이미 community 추가됨, 확인만**

Community 서브섹션이 Pipeline 1과 Pipeline 2 사이에 있는지 확인.

**Step 3: Scripts 테이블에서 analyzer.py 제거**

| `analyzer.py` 행 삭제 |

**Step 4: Implementation Status 갱신**

| Phase | Status | Description |
|-------|--------|-------------|
| 1. RSS + Dedup | Complete | news_brief.py |
| 2. Compose + KST | Complete | compose-newspaper.py, kst_utils.py |
| 3. AI Trends Team | Complete | 3-agent (researcher/writer/executor) |
| 4. Enrich + Render | Complete | enrich.py, render_newspaper.py |
| 5. Breaking Alert | Complete | breaking-alert.py |
| 6. Community (Reddit) | Complete | news_brief.py + community feeds |
| 7. Cron Deployment | Pending | Validation needed |

**Step 5: Commit**

```bash
git add news-brief/SKILL.md
git commit -m "docs(news-brief): SKILL.md v0.5.0 전면 갱신"
```

---

### Task 8: newspaper-schema.md 신규 생성

**Files:**
- Create: `news-brief/references/newspaper-schema.md`

**Step 1: 스키마 문서 작성**

내용:
1. `news_brief.py` JSON 출력 스키마 (General/Ronik/Community 공통)
2. AI Trends Writer vault JSON 스키마
3. `compose-newspaper.py` 출력 스키마 (render 입력)
4. `enrich.py` extract/apply 스키마
5. 필드 의미 사전 (url, source, source_name, origin_source, tag, category)

각 스키마에 JSON 예시 포함.

**Step 2: Commit**

```bash
git add news-brief/references/newspaper-schema.md
git commit -m "docs(news-brief): newspaper-schema.md 신규 — JSON 스키마 문서"
```

---

### Task 9: scripts-detail.md 전면 재작성

**Files:**
- Modify: `news-brief/references/scripts-detail.md`

**Step 1: 전체 재작성**

현행 9개 스크립트 문서화 (analyzer.py 삭제됨):
1. `news_brief.py` — RSS 수집 + 클러스터링 + 스코어링
2. `kst_utils.py` — KST 시간 변환 + 도메인 추출 유틸
3. `compose-newspaper.py` — 4-input 파이프라인 조합
4. `enrich.py` — 번역/요약 추출 + 적용
5. `render_newspaper.py` — JSON → HTML 렌더링
6. `fetch_weather.py` — 날씨 + 옷차림
7. `save_to_vault.py` — Obsidian vault 저장
8. `ai_trends_ingest.py` — AI Trends vault 적재
9. `breaking-alert.py` — 속보 알림

각 스크립트: Purpose, Inputs (CLI args), Output, Key Functions.

**Step 2: Commit**

```bash
git add news-brief/references/scripts-detail.md
git commit -m "docs(news-brief): scripts-detail.md 전면 재작성 — 9개 스크립트"
```

---

### Task 10: output-example.md + usage-examples.md 갱신

**Files:**
- Modify: `news-brief/references/output-example.md`
- Modify: `news-brief/references/usage-examples.md`

**Step 1: output-example.md — 현행 예시로 교체**

구 analyzer.py 기반 텍스트 예시 삭제.
신규 내용:
1. `news_brief.py --output-format json` 출력 예시 (2-3개 아이템)
2. `compose-newspaper.py` 출력 예시 (sections 구조)
3. `enrich.py extract` 출력 예시
4. 최종 HTML 신문의 구조 설명

**Step 2: usage-examples.md — analyzer.py 제거, community 추가**

모든 `analyzer.py` 참조를 삭제.
현행 파이프라인 커맨드로 교체:
```bash
# General
python3 news_brief.py --feeds general_feeds.txt --keywords general_keywords.txt \
  --max-items 15 --since 24 --output-format json > /tmp/general.json

# Ronik
python3 news_brief.py --feeds rss_feeds.txt --keywords keywords.txt \
  --max-items 15 --since 24 --output-format json > /tmp/ronik.json

# Community (Reddit)
python3 news_brief.py --feeds community_feeds.txt --keywords community_keywords.txt \
  --max-items 10 --since 24 --output-format json > /tmp/community.json

# Weather
python3 fetch_weather.py --output /tmp/weather.json

# Compose
python3 compose-newspaper.py --general /tmp/general.json \
  --ai-trends /tmp/ai_trends.json --ronik /tmp/ronik.json \
  --community /tmp/community.json --output /tmp/composed.json

# Enrich (extract → agent → apply)
python3 enrich.py extract --input /tmp/composed.json > /tmp/to_enrich.json
# Agent generates /tmp/enrichments.json
python3 enrich.py apply --input /tmp/composed.json \
  --enrichments /tmp/enrichments.json --output /tmp/composed.json

# Render
python3 render_newspaper.py --input /tmp/composed.json \
  --weather /tmp/weather.json --output /tmp/mingming_daily.html
```

**Step 3: Commit**

```bash
git add news-brief/references/output-example.md news-brief/references/usage-examples.md
git commit -m "docs(news-brief): output-example + usage-examples 현행화"
```

---

### Task 11: 전체 파이프라인 검증 + 최종 커밋

**Step 1: 파이프라인 E2E 실행**

```bash
cd news-brief/scripts

# 1. General
python3 news_brief.py --feeds ../references/general_feeds.txt \
  --keywords ../references/general_keywords.txt \
  --max-items 5 --since 24 --output-format json > /tmp/verify_general.json

# 2. Ronik
python3 news_brief.py --feeds ../references/rss_feeds.txt \
  --keywords ../references/keywords.txt \
  --max-items 5 --since 24 --output-format json > /tmp/verify_ronik.json

# 3. Community
python3 news_brief.py --feeds ../references/community_feeds.txt \
  --keywords ../references/community_keywords.txt \
  --max-items 5 --since 24 --output-format json > /tmp/verify_community.json

# 4. Weather
python3 fetch_weather.py --output /tmp/verify_weather.json

# 5. Compose (AI Trends는 기존 /tmp/ai_trends_data.json 재활용)
python3 compose-newspaper.py \
  --general /tmp/verify_general.json \
  --ai-trends /tmp/ai_trends_data.json \
  --ronik /tmp/verify_ronik.json \
  --community /tmp/verify_community.json \
  --output /tmp/verify_composed.json

# 6. Enrich extract
python3 enrich.py extract --input /tmp/verify_composed.json > /tmp/verify_extract.json

# 7. Render
python3 render_newspaper.py \
  --input /tmp/verify_composed.json \
  --weather /tmp/verify_weather.json \
  --output /tmp/verify_newspaper.html
```

**Step 2: 검증 체크리스트**

- [ ] compose 출력: 6개 섹션 (국제, 국내, 경제, AI·테크, 커뮤니티, 로닉)
- [ ] AI·테크 섹션: headline 비어있지 않음, url이 http로 시작
- [ ] 커뮤니티 섹션: Reddit 아이템 존재
- [ ] enrich extract: origin_source 필드 포함된 아이템 존재
- [ ] HTML 렌더링: 정상 생성 (open으로 브라우저 확인)

**Step 3: 미커밋 변경 확인 후 최종 커밋**

```bash
git status
# 모든 변경이 이미 커밋되었으면 skip
# 남은 변경이 있으면 커밋
```
