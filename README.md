# Expense Tracker - Home Finance Manager

A comprehensive personal finance management application with PostgreSQL database storage, automatic categorization, and visual analytics.

## Features

- 💰 **Dashboard** - Quick overview of income, expenses, and trends
- 💳 **Transaction Management** - Import, view, and search all transactions
- 🏷️ **Smart Categorization** - Automatic categorization with custom rules
- 📊 **Visual Reports** - Charts and graphs for spending analysis
- 🗃️ **PostgreSQL Database** - Reliable storage with exact decimal precision
- 💰 **Budget Tracking** - Set and monitor budgets per category
- 🔄 **Recurring Transactions** - Track bills and subscriptions
- 🎯 **Financial Goals** - Savings goals with progress tracking
- 🌐 **Web Interface** - Modern Flask-based web UI
- 🐳 **Docker Support** - Easy deployment with Docker Compose

## Quick Start with Docker

1. Start the application:
```powershell
docker-compose up -d
```

2. Open http://localhost:5000 in your browser

3. Import your bank CSV files through the web interface

## Development Installation

1. Create a virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

3. Set up PostgreSQL database:
```powershell
# Set connection string (example for local PostgreSQL)
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/expenses"
```

4. Run the web application:
```powershell
python webapp.py
```
Then open http://localhost:5000 in your browser.

## Features Overview

### Import Transactions
- Import CSV files (ING bank format)
- Automatic duplicate detection
- Preserves transaction history

### Categorization
- 30+ pre-defined categories
- Automatic categorization based on patterns
- Add custom categories and rules
- Manual category assignment

### Reports & Analytics
- Monthly income/expense trends
- Category spending breakdown
- Account-wise summaries
- Visual charts and graphs

### Filtering
- Filter by date range
- Filter by account
- Filter by category
- Search transactions

## Database Schema

The app uses PostgreSQL with the following tables:
- `transactions` - All financial transactions (with NUMERIC amounts for precision)
- `transactions_raw` - Immutable raw import data
- `categories` - Expense/income categories (hierarchical)
- `categorization_rules` - Auto-categorization patterns
- `budgets` - Monthly budget limits per category
- `recurring_transactions` - Bills and subscriptions
- `goals` - Financial savings goals
- `goal_contributions` - Contributions to goals
- `accounts` - Account information with transfer flags
- `depreciations` - Asset depreciation tracking

## File Structure

- `webapp.py` - Flask web application entry point
- `db/` - Database module (PostgreSQL)
  - `connection.py` - Connection management
  - `schema.py` - Schema definitions
  - `transactions.py` - Transaction repository
  - `categories.py` - Category repository
  - `accounts.py` - Account repository
  - `budgets.py` - Budget and goals repository
  - `transfers.py` - Transfer detection
  - `reports.py` - Reporting repository
  - `depreciations.py` - Depreciation calculations
- `routes/` - Flask Blueprints
- `templates/` - HTML templates for web UI
- `docker-compose.yml` - Docker deployment configuration
- `Dockerfile` - Container build configuration

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | Flask session secret | `expense_tracker_secret_key_2024` |
