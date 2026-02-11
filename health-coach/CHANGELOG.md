# Changelog

All notable changes to this skill will be documented in this file.

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
- Integrated Longevity (저속노화) skill features:
  - Daily routine management (morning/afternoon/evening/bedtime checklists)
  - Health metrics tracking (sleep, steps, workout, stress, water intake)
  - Weekly health report generation with trend analysis
  - Notion Health Check-in database integration
  - Automated cron job support for routine reminders and tracking
  - Comprehensive routines.json configuration with daily/weekly/monthly routines
  - setup_notion.py for Health Check-in database initialization
  - daily_routine.py for displaying daily checklists
  - track_health.py for logging health metrics
  - weekly_report.py for weekly health analysis

### Changed
- Updated skill version to 0.2.0
- Expanded README with Longevity command examples
- Updated SKILL.md documentation to include merged longevity capabilities
- Clarified role division: Health Coach (advice) + Longevity Manager (routines & tracking)

## [0.1.0] - 2026-02-03

### Added
- Initial release with core Health Coach features
- Exercise routine suggestions (disc-safe)
- Symptom pattern analysis
- PT homework guidance
- Lifestyle advice (sleep, diet, stress)
