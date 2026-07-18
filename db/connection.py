"""Database connection management for PostgreSQL"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection_string():
    """Get PostgreSQL connection string from environment or default"""
    return os.environ.get(
        'DATABASE_URL',
        'postgresql://expenses:expenses@localhost:5432/expenses'
    )


class ConnectionManager:
    """Manages PostgreSQL database connections"""
    
    def __init__(self):
        self.conn = None
        self._connection_string = get_connection_string()
    
    def connect(self):
        """Create database connection with dict cursor and set search_path"""
        self.conn = psycopg2.connect(
            self._connection_string,
            cursor_factory=RealDictCursor
        )
        # Set search_path so unqualified table names resolve to private first, then public
        cursor = self.conn.cursor()
        cursor.execute("SET search_path TO private, public")
        cursor.close()
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def execute(self, query, params=None):
        """Execute a query and return cursor"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        return cursor
    
    def execute_commit(self, query, params=None):
        """Execute a query, commit, and return affected rows"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        rowcount = cursor.rowcount
        conn.commit()
        self.close()
        return rowcount
    
    def fetchone(self, query, params=None):
        """Execute query and fetch one row"""
        cursor = self.execute(query, params)
        result = cursor.fetchone()
        self.close()
        return result
    
    def fetchall(self, query, params=None):
        """Execute query and fetch all rows"""
        cursor = self.execute(query, params)
        results = cursor.fetchall()
        self.close()
        return results
    
    def insert_returning(self, query, params=None):
        """Execute INSERT with RETURNING and return the id"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        result = cursor.fetchone()
        conn.commit()
        self.close()
        return result['id'] if result else None
