# Changelog

All notable changes to the news-brief skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [0.2.0] - 2026-02-09

### Added
- Unified news-brief skill merging two predecessor skills
- Combined RSS aggregation (news_brief.py) + LLM analysis (analyzer.py) into single pipeline
- Shared references: rss_feeds.txt, keywords.txt, impact_prompt.txt
- Comprehensive SKILL.md documentation with unified architecture
- Full pipeline: fetch → dedupe → analyze → format → Telegram

### Changed
- Removed "jarvis-" prefixes from all references and documentation
- Unified testing and deployment model
- Single cron job instead of two separate invocations
- Improved output formatting with emoji indicators

### Fixed
- Consolidated configuration management (single feeds/keywords list)

## [0.1.0] - 2026-02-03

Initial release (prior to merge):

### News Brief Component
- RSS feed aggregation with feedparser
- Title normalization and deduplication
- Keyword-based filtering
- JSON output for downstream analysis
- Support for Korean titles and content

### News Analyzer Component
- LLM-powered impact analysis scaffold (Phase 2 pending)
- Telegram formatting template
- Impact scoring framework (opportunity, risk, action)
- Support for Ronik-specific analysis (robotics, kitchen automation, retail)
- Prioritization scaffold for urgency-based ranking

### Documentation
- Individual SKILL.md files for each component
- VERSION and CHANGELOG tracking
- Reference files: rss_feeds.txt, keywords.txt, impact_prompt.txt
- Usage examples and cron setup instructions

## Historical Context

This unified skill merges two predecessor skills created 2026-02-03:

1. **jarvis-news-brief** (v0.1.0)
   - Deterministic RSS pipeline
   - Focus: aggregation, deduplication, filtering
   - Output: JSON for analyzer

2. **jarvis-news-analyzer** (v0.1.0)
   - LLM analysis scaffold
   - Focus: impact scoring, prioritization, formatting
   - Input: JSON from briefer
   - Output: Telegram message

**Rationale for merge:**
- Tightly coupled components (output of one = input of other)
- Single pipeline responsibility
- Shared configuration and references
- Simplified testing and deployment
- Reduced maintenance overhead
