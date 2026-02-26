# News Brief Refactoring Design

**Date:** 2026-02-26
**Status:** Approved
**Scope:** Code refactoring + documentation update (directory structure unchanged)

## Problem

news-brief 스킬이 v0.2 → v0.4로 빠르게 진화하면서 기술 부채가 누적됨:

1. **필드 의미 혼란**: `"source"` 필드가 스크립트마다 URL/이름으로 혼용
2. **크리티컬 버그**: `compose-newspaper.py`의 `map_ai_trends_items()`가 Researcher/Writer 출력 스키마와 불일치
3. **문서 정체**: VERSION, CHANGELOG, scripts-detail.md 등이 v0.2에 멈춤
4. **죽은 코드**: `analyzer.py`가 `enrich.py`로 대체되었으나 삭제되지 않음
5. **유틸 중복**: domain 추출 로직이 두 곳에 중복

## Design

### 1. AI Trends 필드 스키마 정규화

Writer vault JSON 출력 스키마를 변경하여 필드 의미를 명확히 분리:

| 필드 | 용도 | 예시 |
|------|------|------|
| `url` | 기사 원문 링크 | `https://openai.com/blog/...` |
| `source_name` | 출처 매체명 | `OpenAI Blog` |
| `origin_source` | 수집 RSS 소스명 | `Hacker News` (HN에서 발견한 경우) |
| `category` | 콘텐츠 주제 분류 | `Models`, `Tools`, `Open-source` |

`compose-newspaper.py`의 `map_ai_trends_items()` 변경:

```python
# Before (source를 URL로 해석)
"url": it.get("source", ""),
"source": _extract_domain(it.get("source", "")),

# After (명확한 필드 분리)
"url": it.get("url") or it.get("source", ""),
"source": it.get("source_name") or extract_domain(it.get("url") or it.get("source", "")),
```

Backward compatibility: `url`이 없으면 기존 `source`에서 폴백.

### 2. 코드 변경

#### compose-newspaper.py
- `map_ai_trends_items()`: 새 필드 스키마에 맞게 매핑 수정
- `_extract_domain()` 제거 → `kst_utils.extract_domain()` 사용

#### enrich.py
- `extract()`: `origin_source` 필드를 출력에 포함
- `apply()`: 변경 없음 (headline/summary/why만 갱신하므로 origin_source 보존됨)

#### kst_utils.py
- `extract_domain(url)` 유틸 추가 (compose-newspaper.py, news_brief.py 공용)

#### analyzer.py
- 삭제 (enrich.py + render_newspaper.py로 완전 대체)
- `__pycache__/` 내 캐시도 정리

### 3. 문서 변경

#### SKILL.md
- 버전 0.5.0으로 갱신
- Community 파이프라인 반영 (architecture diagram, input files, quick usage)
- Scripts 테이블에서 analyzer.py 제거
- `newspaper-schema.md` 참조 추가

#### VERSION
- `0.5.0`

#### CHANGELOG.md
- v0.3.0 (AI Trends 3-agent, compose, KST)
- v0.4.0 (breaking-alert, enrich.py, community/origin_source)
- v0.5.0 (리팩토링, 필드 정규화, analyzer 삭제)

#### researcher.md
- 출력 스키마에서 `source` → `source_name` + `url` 분리 명시
- `origin_source` 규칙 유지

#### writer.md
- vault JSON에 `url`/`source_name` 분리 반영

#### scripts-detail.md
- 전체 9개 스크립트 문서화 (analyzer.py 삭제 후 9개)

#### output-example.md
- 현행 JSON/HTML 예시로 교체

#### usage-examples.md
- analyzer.py 참조 제거
- community 파이프라인 추가

#### newspaper-schema.md (신규)
- compose-newspaper.py 입출력 JSON 스키마 문서

### 4. 변경하지 않는 것

- `news_brief.py` — 안정적, link/source 필드명은 General/Ronik 파이프라인 전용이므로 변경 불필요
- `render_newspaper.py`, `save_to_vault.py`, `ai_trends_ingest.py` — 하류 소비자, headline/url/source 읽기만 하므로 영향 없음
- `breaking-alert.py`, `fetch_weather.py` — 독립 파이프라인
- `references/` 디렉토리 구조 — flat 유지

### 5. 검증

- community.json + ai_trends_data.json + general.json + ronik.json으로 compose → enrich → render 전체 파이프라인 실행
- 6개 섹션(국제/국내/경제/AI테크/커뮤니티/로닉) 정상 생성 확인
- origin_source가 enrich round-trip 후에도 보존되는지 확인
