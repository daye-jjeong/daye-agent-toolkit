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

-- ── Finance (banksalad import) ──────────────

CREATE TABLE IF NOT EXISTS finance_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    time TEXT,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    tx_type TEXT,
    category_l1 TEXT,
    category_l2 TEXT,
    merchant TEXT,
    payment TEXT,
    memo TEXT,
    import_key TEXT NOT NULL UNIQUE,
    source TEXT DEFAULT 'banksalad',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_fin_tx_date ON finance_transactions(date);
CREATE INDEX IF NOT EXISTS idx_fin_tx_category ON finance_transactions(category_l1);

CREATE TABLE IF NOT EXISTS finance_investments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    product_type TEXT,
    institution TEXT,
    invested REAL DEFAULT 0,
    current_value REAL DEFAULT 0,
    return_pct REAL DEFAULT 0,
    currency TEXT DEFAULT 'KRW',
    source TEXT DEFAULT 'banksalad',
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(product_name, institution)
);

CREATE TABLE IF NOT EXISTS finance_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_name TEXT NOT NULL,
    loan_type TEXT,
    institution TEXT,
    principal REAL DEFAULT 0,
    outstanding REAL DEFAULT 0,
    interest_rate REAL DEFAULT 0,
    start_date TEXT,
    end_date TEXT,
    source TEXT DEFAULT 'banksalad',
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(loan_name, institution, principal)
);
