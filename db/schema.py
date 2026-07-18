"""Database schema initialization for PostgreSQL

Two-schema architecture:
  - private: all application tables (staging + normalized)
  - public:  analytics views and date dimension for Power BI
"""

SCHEMA_SQL = """
-- =============================================================
-- PRIVATE SCHEMA — Application tables
-- =============================================================

-- Categories table
CREATE TABLE IF NOT EXISTS private.categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES private.categories(id),
    color TEXT,
    icon TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Import batches table - tracks each CSV import
CREATE TABLE IF NOT EXISTS private.import_batches (
    id SERIAL PRIMARY KEY,
    filename TEXT,
    retained_file TEXT,
    format_id TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    row_count INTEGER DEFAULT 0,
    account TEXT
);

-- Transactions RAW/Staging table - immutable original data from CSV
CREATE TABLE IF NOT EXISTS private.transactions_raw (
    id SERIAL PRIMARY KEY,
    import_batch_id INTEGER REFERENCES private.import_batches(id),
    date DATE NOT NULL,
    description TEXT,
    account TEXT,
    counter_account TEXT,
    code TEXT,
    direction TEXT,
    amount NUMERIC(12, 2) NOT NULL,
    mutation_type TEXT,
    notes TEXT,
    balance_after NUMERIC(12, 2),
    hash TEXT UNIQUE
);

-- Transactions table - working table with user modifications (fully English)
CREATE TABLE IF NOT EXISTS private.transactions (
    id SERIAL PRIMARY KEY,
    raw_id INTEGER REFERENCES private.transactions_raw(id),
    date DATE NOT NULL,
    description TEXT,
    account TEXT,
    counter_account TEXT,
    code TEXT,
    direction TEXT,
    amount NUMERIC(12, 2) NOT NULL,
    mutation_type TEXT,
    notes TEXT,
    balance_after NUMERIC(12, 2),
    tag TEXT,
    category_id INTEGER REFERENCES private.categories(id),
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash TEXT UNIQUE,
    original_direction TEXT,
    is_transfer BOOLEAN DEFAULT FALSE,
    linked_transaction_id INTEGER REFERENCES private.transactions(id),
    is_incidental BOOLEAN DEFAULT FALSE
);

-- Categorization rules table
CREATE TABLE IF NOT EXISTS private.categorization_rules (
    id SERIAL PRIMARY KEY,
    pattern TEXT,
    field TEXT DEFAULT 'description',
    category_id INTEGER NOT NULL REFERENCES private.categories(id),
    counter_account TEXT,
    transaction_type TEXT,
    min_amount NUMERIC(12, 2),
    max_amount NUMERIC(12, 2),
    priority INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Budgets table
CREATE TABLE IF NOT EXISTS private.budgets (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES private.categories(id),
    amount NUMERIC(12, 2) NOT NULL,
    period TEXT DEFAULT 'monthly',
    year INTEGER,
    month INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recurring transactions table
CREATE TABLE IF NOT EXISTS private.recurring_transactions (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    direction TEXT NOT NULL,
    category_id INTEGER REFERENCES private.categories(id),
    account TEXT,
    frequency TEXT DEFAULT 'monthly',
    day_of_month INTEGER,
    day_of_week INTEGER,
    start_date DATE NOT NULL,
    end_date DATE,
    last_generated DATE,
    next_due DATE,
    reminder_days INTEGER DEFAULT 3,
    active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Financial goals table
CREATE TABLE IF NOT EXISTS private.goals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    target_amount NUMERIC(12, 2) NOT NULL,
    current_amount NUMERIC(12, 2) DEFAULT 0,
    deadline DATE,
    category TEXT,
    color TEXT DEFAULT '#4CAF50',
    icon TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Goal contributions table
CREATE TABLE IF NOT EXISTS private.goal_contributions (
    id SERIAL PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES private.goals(id),
    amount NUMERIC(12, 2) NOT NULL,
    date DATE NOT NULL,
    transaction_id INTEGER REFERENCES private.transactions(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts table
CREATE TABLE IF NOT EXISTS private.accounts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    account_number TEXT UNIQUE,
    type TEXT DEFAULT 'checking',
    institution TEXT,
    currency TEXT DEFAULT 'EUR',
    initial_balance NUMERIC(12, 2) DEFAULT 0,
    current_balance NUMERIC(12, 2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    is_transfer BOOLEAN DEFAULT FALSE,
    color TEXT DEFAULT '#2196F3',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Saved filters table
CREATE TABLE IF NOT EXISTS private.saved_filters (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    filter_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transfer patterns table
CREATE TABLE IF NOT EXISTS private.transfer_patterns (
    id SERIAL PRIMARY KEY,
    pattern TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Depreciations table
CREATE TABLE IF NOT EXISTS private.depreciations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    purchase_date DATE NOT NULL,
    purchase_amount NUMERIC(12, 2) NOT NULL,
    useful_life_months INTEGER NOT NULL,
    residual_value NUMERIC(12, 2) DEFAULT 0,
    category_id INTEGER REFERENCES private.categories(id),
    transaction_id INTEGER REFERENCES private.transactions(id),
    savings_account TEXT,
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schema migrations tracking
CREATE TABLE IF NOT EXISTS private.schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name TEXT UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indices
CREATE INDEX IF NOT EXISTS idx_transactions_date ON private.transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_raw_date ON private.transactions_raw(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON private.transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON private.transactions(account);
CREATE INDEX IF NOT EXISTS idx_transactions_description ON private.transactions(description);
CREATE INDEX IF NOT EXISTS idx_transactions_linked ON private.transactions(linked_transaction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_raw_fk ON private.transactions(raw_id);
CREATE INDEX IF NOT EXISTS idx_transactions_raw_hash ON private.transactions_raw(hash);
CREATE INDEX IF NOT EXISTS idx_transactions_direction ON private.transactions(direction);
CREATE INDEX IF NOT EXISTS idx_transactions_is_transfer ON private.transactions(is_transfer);
CREATE INDEX IF NOT EXISTS idx_budgets_category ON private.budgets(category_id);
CREATE INDEX IF NOT EXISTS idx_recurring_next_due ON private.recurring_transactions(next_due);
CREATE INDEX IF NOT EXISTS idx_goals_status ON private.goals(status);

-- =============================================================
-- PUBLIC SCHEMA — Analytics views and date dimension
-- =============================================================

-- Date dimension table (pre-populated 2020-2030)
CREATE TABLE IF NOT EXISTS public.dim_dates (
    date_key DATE PRIMARY KEY,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name TEXT NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    week_number INTEGER NOT NULL
);

-- Analytics view: transactions with denormalized category and account info
CREATE OR REPLACE VIEW public.v_transactions AS
SELECT
    t.id,
    t.date,
    t.description,
    t.account,
    t.counter_account,
    t.code,
    t.direction,
    t.amount,
    t.mutation_type,
    t.notes,
    t.balance_after,
    t.tag,
    t.is_transfer,
    t.is_incidental,
    t.imported_at,
    c.id AS category_id,
    c.name AS category_name,
    pc.name AS parent_category_name,
    c.color AS category_color,
    a.name AS account_name,
    a.type AS account_type
FROM private.transactions t
LEFT JOIN private.categories c ON t.category_id = c.id
LEFT JOIN private.categories pc ON c.parent_id = pc.id
LEFT JOIN private.accounts a ON t.account = a.account_number;

-- Analytics view: categories with resolved parent names
CREATE OR REPLACE VIEW public.v_categories AS
SELECT
    c.id,
    c.name,
    c.parent_id,
    p.name AS parent_name,
    c.color,
    c.icon
FROM private.categories c
LEFT JOIN private.categories p ON c.parent_id = p.id;

-- Analytics view: active accounts
CREATE OR REPLACE VIEW public.v_accounts AS
SELECT
    a.id,
    a.name,
    a.account_number,
    a.type,
    a.institution,
    a.currency,
    a.initial_balance,
    a.current_balance,
    a.is_transfer,
    a.color
FROM private.accounts a
WHERE a.is_active = TRUE;

-- Grant SELECT on all public views/tables to analytics_user
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user;
"""

DEFAULT_CATEGORIES = [
    # Format: (name, parent_name, color) - parent_name None for top-level
    # Income categories
    ('Income', None, '#4CAF50'),
    ('Salary', 'Income', '#66BB6A'),
    ('Bonus', 'Income', '#81C784'),
    ('Refund', 'Income', '#A5D6A7'),
    
    # Expense categories
    ('Housing', None, '#2196F3'),
    ('Rent/Mortgage', 'Housing', '#42A5F5'),
    ('Utilities', 'Housing', '#64B5F6'),
    ('Home Maintenance', 'Housing', '#90CAF9'),
    
    ('Transportation', None, '#FF9800'),
    ('Fuel', 'Transportation', '#FFA726'),
    ('Public Transport', 'Transportation', '#FFB74D'),
    ('Car Maintenance', 'Transportation', '#FFCC80'),
    
    ('Food & Dining', None, '#F44336'),
    ('Groceries', 'Food & Dining', '#EF5350'),
    ('Restaurants', 'Food & Dining', '#E57373'),
    ('Coffee & Snacks', 'Food & Dining', '#EF9A9A'),
    
    ('Shopping', None, '#9C27B0'),
    ('Clothing', 'Shopping', '#AB47BC'),
    ('Electronics', 'Shopping', '#BA68C8'),
    ('Personal Care', 'Shopping', '#CE93D8'),
    
    ('Entertainment', None, '#FF5722'),
    ('Movies & Streaming', 'Entertainment', '#FF7043'),
    ('Sports & Hobbies', 'Entertainment', '#FF8A65'),
    ('Travel', 'Entertainment', '#FFAB91'),
    
    ('Healthcare', None, '#00BCD4'),
    ('Doctor', 'Healthcare', '#26C6DA'),
    ('Pharmacy', 'Healthcare', '#4DD0E1'),
    ('Insurance', 'Healthcare', '#80DEEA'),
    
    ('Financial', None, '#607D8B'),
    ('Bank Fees', 'Financial', '#78909C'),
    ('Interest', 'Financial', '#90A4AE'),
    ('Taxes', 'Financial', '#B0BEC5'),
    
    ('Other', None, '#9E9E9E'),
    ('Uncategorized', 'Other', '#BDBDBD'),
]


def init_schema(conn):
    """Initialize database schema (private tables + public views/dimensions)"""
    cursor = conn.cursor()
    cursor.execute(SCHEMA_SQL)
    conn.commit()


def populate_date_dimension(conn):
    """Populate the public.dim_dates table with dates from 2020 to 2030"""
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM public.dim_dates')
    result = cursor.fetchone()
    
    if result['count'] == 0:
        print("Populating date dimension table (2020-2030)...")
        cursor.execute("""
            INSERT INTO public.dim_dates (date_key, year, quarter, month, month_name,
                                          day_of_month, day_of_week, day_name, is_weekend, week_number)
            SELECT
                d::date AS date_key,
                EXTRACT(YEAR FROM d)::int AS year,
                EXTRACT(QUARTER FROM d)::int AS quarter,
                EXTRACT(MONTH FROM d)::int AS month,
                TO_CHAR(d, 'Month') AS month_name,
                EXTRACT(DAY FROM d)::int AS day_of_month,
                EXTRACT(ISODOW FROM d)::int AS day_of_week,
                TO_CHAR(d, 'Day') AS day_name,
                EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend,
                EXTRACT(WEEK FROM d)::int AS week_number
            FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day') AS d
            ON CONFLICT DO NOTHING
        """)
        conn.commit()
        print(f"✓ Populated {cursor.rowcount} dates")


def seed_default_categories(conn):
    """Insert default categories if none exist, respecting parent-child relationships"""
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM private.categories')
    result = cursor.fetchone()
    
    if result['count'] == 0:
        # Track inserted category IDs by name
        category_ids = {}
        
        # Insert categories, parents first
        for name, parent_name, color in DEFAULT_CATEGORIES:
            parent_id = category_ids.get(parent_name) if parent_name else None
            
            cursor.execute(
                'INSERT INTO private.categories (name, parent_id, color) VALUES (%s, %s, %s) RETURNING id',
                (name, parent_id, color)
            )
            cat_id = cursor.fetchone()['id']
            category_ids[name] = cat_id
        
        conn.commit()


def init_database():
    """Initialize the database schema and seed default data"""
    from .connection import ConnectionManager
    
    cm = ConnectionManager()
    conn = cm.connect()
    
    init_schema(conn)
    populate_date_dimension(conn)
    seed_default_categories(conn)
    
    # Re-grant SELECT on public tables (covers newly created views)
    cursor = conn.cursor()
    try:
        cursor.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user')
        conn.commit()
    except Exception:
        conn.rollback()  # analytics_user may not exist in dev without init-db.sql
    
    cm.close()
