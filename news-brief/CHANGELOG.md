# Changelog

All notable changes to the news-brief skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
-

### Changed
-

### Fixed
-

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
