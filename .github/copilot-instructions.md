# Copilot Instructions for Expense Tracker

## ⛔ CRITICAL: Production Data Protection

**NEVER** access, read, query, or modify:
- `C:\apps\expenses\` - Production deployment folder
- Production PostgreSQL database
- Any `.env` files with credentials
- **Docker containers or databases** - Do NOT run `docker exec`, `psql`, or query the running database

**ONLY** work with:
- Source code in `C:\Users\joost\Projects\Expenses`
- Test/dummy data in the `data/` folder (for generating test data only)

## Project Architecture

This is a Flask-based expense tracking application using **PostgreSQL** and **Docker**.

### Database
- **PostgreSQL 15** - Primary database (NUMERIC(12,2) for exact decimal amounts)
- **Connection**: Via `DATABASE_URL` environment variable
- **No SQLite** - Fully migrated to PostgreSQL

### Project Structure

```
Expenses/
├── webapp.py              # Main Flask app - registers blueprints
├── extensions.py          # Shared db singleton for routes
├── utils.py               # Shared utilities
├── db/                    # PostgreSQL database module
│   ├── __init__.py        # Database class (unified API)
│   ├── connection.py      # PostgreSQL connection manager
│   ├── schema.py          # Schema DDL and init
│   ├── transactions.py    # Transaction repository
│   ├── categories.py      # Category repository
│   ├── accounts.py        # Account repository
│   ├── budgets.py         # Budget & goals repository
│   ├── transfers.py       # Transfer detection
│   ├── reports.py         # Reporting repository
│   └── depreciations.py   # Depreciation calculations
├── routes/                # Flask Blueprints
│   ├── main.py            # Dashboard, Reports
│   ├── transactions.py    # Transactions, Import
│   ├── accounts.py        # Accounts, Cashflow
│   ├── budgets.py         # Budgets, Goals, Recurring
│   ├── categories.py      # Category management
│   └── depreciations.py   # Asset depreciation tracking
├── templates/             # Jinja2 HTML templates
├── docker-compose.yml     # Docker Compose deployment
├── Dockerfile             # Container build
└── requirements.txt       # Python dependencies
```

## Code Guidelines

### Database Access
- **Routes** import `db` from `extensions.py`
- **NO direct SQL in routes** - use repository methods
- All database operations go through `db/` module
- Use `NUMERIC(12,2)` for monetary amounts (no floats)

### Adding New Features

1. **New Blueprint/Route**
   - Register in `webapp.py`
   - Add nav link in `templates/base.html`

2. **New Repository Method**
   - Add to appropriate `db/*.py` file
   - Expose via `db/__init__.py` Database class

3. **New Dependency**
   - Add to `requirements.txt`
   - Rebuild Docker image: `docker-compose build`

### Deployment

```powershell
# Start/restart the application
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose up -d --build

# Stop the application
docker-compose down
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Auto-set in docker-compose |
| `SECRET_KEY` | Flask session secret | Yes (set in .env) |

## Code Style

- Flask Blueprints for route organization
- Repository pattern for database access
- Templates extend `base.html`
- Tailwind CSS via CDN
- Dutch ING CSV format support
