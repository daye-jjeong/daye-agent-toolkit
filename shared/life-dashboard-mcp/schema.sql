CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT,
    repo TEXT,
    tag TEXT,
    summary TEXT,
    start_at TEXT NOT NULL,
    end_at TEXT,
    duration_min INTEGER,
    file_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    has_tests INTEGER DEFAULT 0,
    has_commits INTEGER DEFAULT 0,
    token_total INTEGER DEFAULT 0,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(start_at);
CREATE INDEX IF NOT EXISTS idx_activities_source ON activities(source);
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_session ON activities(source, session_id);

CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    work_hours REAL,
    session_count INTEGER,
    tag_breakdown TEXT,
    repos TEXT,
    first_session TEXT,
    last_session_end TEXT,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS coach_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

INSERT OR IGNORE INTO coach_state (key, value) VALUES
    ('escalation_level', '0'),
    ('consecutive_overwork_days', '0'),
    ('consecutive_no_exercise_days', '0');
