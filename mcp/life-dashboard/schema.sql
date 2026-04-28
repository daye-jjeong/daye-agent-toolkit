CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    work_hours REAL,
    session_count INTEGER,
    tag_breakdown TEXT,
    repos TEXT,
    first_session TEXT,
    last_session_end TEXT,
    summary TEXT,
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

-- ── Work Tracking ──────────────────────────

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    repo TEXT,
    branch TEXT,
    tag TEXT,
    summary TEXT,
    summary_source TEXT DEFAULT 'pending',
    status TEXT DEFAULT 'in_progress',
    follow_up TEXT,
    start_at TEXT NOT NULL,
    end_at TEXT,
    duration_min INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    has_tests INTEGER DEFAULT 0,
    has_commits INTEGER DEFAULT 0,
    token_total INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date)
);

CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_summary_source ON sessions(summary_source);

CREATE TABLE IF NOT EXISTS session_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    topic TEXT,
    user_messages TEXT,
    agent_messages TEXT,
    files_changed TEXT,
    commands TEXT,
    errors TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date),
    FOREIGN KEY (source, session_id, date)
        REFERENCES sessions(source, session_id, date)
        ON DELETE CASCADE
);

-- ── Session Topics (1:N from sessions) ──────────

CREATE TABLE IF NOT EXISTS session_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    topic_order INTEGER NOT NULL DEFAULT 0,
    tag TEXT,
    summary TEXT NOT NULL,
    repo TEXT,
    start_at TEXT,
    end_at TEXT,
    duration_estimate_min INTEGER,
    status TEXT DEFAULT 'completed',
    follow_up TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, session_id, date, topic_order),
    FOREIGN KEY (source, session_id, date)
        REFERENCES sessions(source, session_id, date)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_topics_date ON session_topics(date);
CREATE INDEX IF NOT EXISTS idx_session_topics_tag ON session_topics(tag);
CREATE INDEX IF NOT EXISTS idx_session_topics_fk ON session_topics(source, session_id, date);

-- ── Projects ──────────────────────────────────

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    repo TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(name, repo)
);

-- ── Tasks (replaces session_topics) ───────────

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    tag TEXT NOT NULL,
    summary TEXT NOT NULL,
    repo TEXT,
    segments TEXT NOT NULL DEFAULT '[]',
    duration_min INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed',
    follow_up TEXT,
    project_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);

-- ── Todos (prospective, 사용자 관리 할일) ───────

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done_definition TEXT,
    status TEXT NOT NULL DEFAULT 'backlog',
    priority INTEGER,
    project_id INTEGER,
    parent_id INTEGER,
    category TEXT,
    quarter TEXT,
    deadline TEXT,
    estimated_min INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at TEXT,
    done_at TEXT,
    deferred_reason TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (parent_id) REFERENCES todos(id)
);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_deadline ON todos(deadline);
CREATE INDEX IF NOT EXISTS idx_todos_category ON todos(category);
CREATE INDEX IF NOT EXISTS idx_todos_parent ON todos(parent_id);

-- ── Daily Checkins (매일 아침/저녁 의식 기록) ──

CREATE TABLE IF NOT EXISTS daily_checkins (
    date TEXT PRIMARY KEY,
    morning_wip_ids TEXT,
    morning_intent TEXT,
    evening_reflection TEXT,
    available_min INTEGER CHECK (available_min IS NULL OR available_min >= 0),
    energy TEXT CHECK (energy IS NULL OR energy IN ('low','mid','high')),
    blockers TEXT,
    available_status TEXT NOT NULL DEFAULT 'unknown' CHECK (available_status IN ('answered','skipped','unknown')),
    energy_status TEXT NOT NULL DEFAULT 'unknown' CHECK (energy_status IN ('answered','skipped','unknown')),
    blockers_status TEXT NOT NULL DEFAULT 'unknown' CHECK (blockers_status IN ('answered','skipped','unknown')),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    date TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    content TEXT NOT NULL,
    reasoning TEXT,
    repo TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(session_id, signal_type, content)
);

CREATE INDEX IF NOT EXISTS idx_signals_v2_date ON signals(date);
CREATE INDEX IF NOT EXISTS idx_signals_v2_type ON signals(signal_type);

-- ── Coaching ────────────────────────────────────

CREATE TABLE IF NOT EXISTS coaching_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    period_type TEXT NOT NULL,
    content TEXT NOT NULL,
    sections TEXT NOT NULL,
    escalation_level INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_coaching_date ON coaching_entries(date);

CREATE TABLE IF NOT EXISTS task_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggested_date TEXT NOT NULL,
    description TEXT NOT NULL,
    estimated_min INTEGER,
    priority INTEGER,
    source_type TEXT NOT NULL,
    origin_session_id TEXT,
    status TEXT DEFAULT 'pending',
    resolved_date TEXT,
    resolved_session_id TEXT,
    resolution_method TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(suggested_date, description)
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON task_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_tasks_date ON task_suggestions(suggested_date);

CREATE TABLE IF NOT EXISTS followup_chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_session_id TEXT NOT NULL,
    origin_date TEXT NOT NULL,
    origin_repo TEXT,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    resolved_date TEXT,
    resolved_session_id TEXT,
    resolution_note TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(origin_session_id, origin_date, description)
);

CREATE INDEX IF NOT EXISTS idx_followup_status ON followup_chains(status);
CREATE INDEX IF NOT EXISTS idx_followup_origin_date ON followup_chains(origin_date);

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

CREATE TABLE IF NOT EXISTS finance_sold_investments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    product_type TEXT,
    institution TEXT,
    invested REAL DEFAULT 0,
    sold_value REAL,
    return_pct REAL,
    sold_date TEXT,
    reason TEXT,
    source TEXT DEFAULT 'banksalad',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(product_name, institution, sold_date)
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

-- ── Finance (price snapshots + merchant categories) ──

CREATE TABLE IF NOT EXISTS finance_price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    date TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'KRW',
    source TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(product_name, date)
);

CREATE INDEX IF NOT EXISTS idx_price_snap_date ON finance_price_snapshots(date);

CREATE TABLE IF NOT EXISTS finance_merchant_categories (
    merchant TEXT PRIMARY KEY,
    category_l1 TEXT NOT NULL,
    category_l2 TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- ── Health ──────────────────────────────────

CREATE TABLE IF NOT EXISTS health_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    exercises TEXT,
    feeling TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, timestamp, type)
);

CREATE TABLE IF NOT EXISTS health_symptoms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL,
    trigger_factor TEXT,
    duration TEXT,
    status TEXT DEFAULT '진행중',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, timestamp, type)
);

CREATE TABLE IF NOT EXISTS health_pt_homework (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise TEXT NOT NULL,
    sets_reps TEXT,
    notes TEXT,
    status TEXT DEFAULT '할 일',
    assigned_date TEXT NOT NULL,
    completed_date TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(exercise, assigned_date)
);

CREATE TABLE IF NOT EXISTS health_check_ins (
    date TEXT PRIMARY KEY,
    sleep_hours REAL,
    sleep_quality INTEGER,
    steps INTEGER,
    workout INTEGER DEFAULT 0,
    stress INTEGER,
    water_ml INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS health_meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    food_items TEXT,
    portion TEXT,
    skipped INTEGER DEFAULT 0,
    calories INTEGER,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, timestamp, meal_type)
);

CREATE INDEX IF NOT EXISTS idx_health_exercises_date ON health_exercises(date);
CREATE INDEX IF NOT EXISTS idx_health_symptoms_date ON health_symptoms(date);
CREATE INDEX IF NOT EXISTS idx_health_meals_date ON health_meals(date);

-- ── Pantry ─────────────────────────────────────

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

CREATE INDEX IF NOT EXISTS idx_pantry_expiry ON pantry_items(expiry_date);
CREATE INDEX IF NOT EXISTS idx_pantry_status ON pantry_items(status);
