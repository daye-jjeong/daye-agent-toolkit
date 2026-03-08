# pantry-manager → life-dashboard SQLite 통합

**Date:** 2026-03-08 | **Status:** approved

## Design

### 목표
- pantry-manager의 데이터 저장소를 Obsidian vault → life-dashboard-mcp SQLite로 전환
- 유통기한 알림 책임을 life-coach로 이관
- pantry-manager는 온디맨드 CRUD/레시피/장보기만 담당

### 변경 범위

**1. life-dashboard-mcp** — 테이블 + DB 함수 추가
- `schema.sql`에 `pantry_items` 테이블
- `db.py`에 pantry CRUD 함수

**2. pantry-manager** — vault → SQLite 전환
- `pantry_io.py` 삭제
- `check_expiry.py`, `weekly_check.py` 삭제 (life-coach로 이관)
- 나머지 스크립트 → db.py import로 전환
- `SKILL.md`, `references/usage-examples.md` 업데이트

**3. life-coach** — 유통기한 섹션 추가
- `daily_coach.py`에 pantry 유통기한 데이터 + 섹션 추가
- `SKILL.md` 업데이트

### pantry_items 스키마

```sql
CREATE TABLE IF NOT EXISTS pantry_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    location TEXT NOT NULL,
    purchase_date TEXT,
    expiry_date TEXT,
    status TEXT DEFAULT '재고 있음',
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(name, location)
);
```

### 삭제 대상

| 파일 | 이유 |
|------|------|
| `pantry_io.py` | vault I/O → db.py로 대체 |
| `check_expiry.py` | life-coach daily_coach가 흡수 |
| `weekly_check.py` | life-coach weekly_coach가 흡수 |

### 건드리지 않는 것
- `parse_receipt.py` — OCR 로직 그대로, import만 변경
- MCP `server.py` — pantry 도구 미포함
- life-coach `cron.json` — 기존 cron이 이미 유통기한 데이터 포함하게 됨
