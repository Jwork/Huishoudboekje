"""Migration runner - executes pending migrations in order"""
import os
import sys
import importlib.util
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import ConnectionManager

def get_migration_files():
    """Get all migration files in order"""
    migrations_dir = Path(__file__).parent
    files = sorted([f for f in migrations_dir.glob('*.py') 
                   if f.name != '__init__.py' and f.name != 'runner.py'])
    return files

def create_migrations_table(conn):
    """Create table to track applied migrations"""
    cursor = conn.cursor()
    cursor.execute("SET search_path TO private, public")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS private.schema_migrations (
            id SERIAL PRIMARY KEY,
            migration_name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()

def get_applied_migrations(conn):
    """Get list of already applied migrations"""
    cursor = conn.cursor()
    cursor.execute("SELECT migration_name FROM private.schema_migrations ORDER BY migration_name")
    applied = [row['migration_name'] for row in cursor.fetchall()]
    cursor.close()
    return applied

def mark_migration_applied(conn, migration_name):
    """Mark a migration as applied"""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO private.schema_migrations (migration_name) VALUES (%s) ON CONFLICT DO NOTHING",
        (migration_name,)
    )
    conn.commit()
    cursor.close()

def run_migrations():
    """Run all pending migrations"""
    print("🔄 Running database migrations...")
    
    db = ConnectionManager()
    conn = db.connect()
    
    try:
        create_migrations_table(conn)
        applied = get_applied_migrations(conn)
        migration_files = get_migration_files()
        
        if not migration_files:
            print("✓ No migrations found")
            return
        
        pending = [f for f in migration_files if f.stem not in applied]
        
        if not pending:
            print("✓ All migrations already applied")
            return
        
        for migration_file in pending:
            print(f"\n📝 Applying migration: {migration_file.stem}")
            
            # Load migration module
            spec = importlib.util.spec_from_file_location(migration_file.stem, migration_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Run migration
            module.up(conn)
            mark_migration_applied(conn, migration_file.stem)
            print(f"✓ Migration {migration_file.stem} applied successfully")
        
        print(f"\n✓ Applied {len(pending)} migration(s)")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    run_migrations()
