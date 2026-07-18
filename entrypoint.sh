#!/bin/bash
set -e

echo "🚀 Starting Expense Tracker..."

# Wait for database to be ready
echo "⏳ Waiting for database..."
until python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null; do
  echo "   Database not ready yet, retrying in 2s..."
  sleep 2
done
echo "✓ Database is ready"

# Run migrations
echo ""
python /app/migrations/runner.py

# Start the application
echo ""
echo "🌐 Starting web server..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 webapp:app
