# Changelog

All notable changes to this skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-02-11

### Changed
- **Notion → Obsidian vault**: Replaced all Notion API calls with local Obsidian vault I/O
- Data stored in `~/mingming-vault/taling/checklists/` as Dataview-queryable markdown
- Removed Notion API key dependency (`~/.config/notion/api_key_daye_personal`)
- No network dependency for storage (local-first)

### Added
- **scripts/taling_io.py**: Obsidian vault I/O helper (read/write markdown with frontmatter)
- `save_checklist_to_vault()` method replacing `update_notion_task()`
- Dataview-queryable frontmatter schema (type, date, status, passed, total, all_complete)
- New test class `TestObsidianVaultIO` with 6 tests
- New test class `TestTalingIO` with 8 standalone I/O tests

### Removed
- `_load_notion_key()`, `_find_notion_task()`, `_update_notion_task()`, `_create_notion_task()`, `_append_checklist_to_page()`
- `NOTION_TASKS_DB`, `NOTION_API_KEY_FILE` constants
- Notion API key file requirement

---

## [1.0.0] - 2026-02-03

### Added
- **checklist_automation.py**: Complete checklist automation with Notion + Google Form
- **test_checklist_automation.py**: 25 unit tests (100% pass rate)
- Automatic Notion Tasks DB updates with checklist status
- Google Form link auto-appended when ALL items complete
- ZIP file parsing and content classification
- Comprehensive error handling

### Architecture Analysis
- Analyzed Cron Polling vs Event-Driven Webhook approaches
- **Recommendation**: Keep Cron Polling (10min delay acceptable, simpler infra)
- Migration path documented for future Webhook adoption

### Documentation
- `docs/taling_checklist_automation_design.html` - Full technical design
- `docs/taling_checklist_migration_guide.md` - Setup and migration guide
- `docs/taling_message_templates.md` - Message format examples

### Task
- Notion Task: https://www.notion.so/Telegram-Form-2fc68ba6942181a997d3d4989c08f652

---

## [0.1.0] - 2026-02-02

### Architecture Change
- **Migration**: Message backup parser → Telegram Bot API
- **Reason**: Clawdbot message backup format incompatible with Telegram topic filtering
- **Impact**: Now requires `TELEGRAM_BOT_TOKEN` environment variable

### Features
- ✅ Auto-detect file uploads in topic 168
- ✅ 7-type file classification (pattern matching)
- ✅ Daily progress tracking (weekday-aware)
- ✅ Instant alerts on file upload
- ✅ 23:00 final report (deadline reminder)
- ✅ 학습후기 500-char validation (Mon/Wed/Fri)

### Files
- **Script**: `scripts/taling_auto_monitor_v2.py`
- **State**: `memory/taling_daily_status.json`
- **Logs**: `logs/taling_auto_monitor.log`
- **Cron**: See `cron_config.txt`

### Requirements
- Telegram Bot token (from @BotFather)
- Bot added to JARVIS HQ group
- `clawdbot` CLI (for alert sending)

### Token Economics
- **This approach**: 0 tokens (pure script)
- **Alternative (LLM)**: ~500 tokens/check × 78 checks/day = 39,000 tokens/day
- **60-day savings**: 2,340,000 tokens

---

# Historical Notes

## v2.0 / v1.0 Migration (Pre-SemVer)

### Initial Design
- Used Clawdbot message backup parsing
- Incompatible with Telegram topic structure
- Not implemented (discovered architecture issue during development)

### Lessons Learned
- Clawdbot message backup format is channel-agnostic
- Lacks Telegram-specific metadata (message_thread_id)
- Direct API access required for topic filtering
