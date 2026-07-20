"""Add notes_pattern to categorization_rules and drop field"""

def up(conn):
    cursor = conn.cursor()
    cursor.execute("SET search_path TO private, public")
    
    # Check if notes_pattern already exists
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'private' AND table_name = 'categorization_rules' AND column_name = 'notes_pattern'
    """)
    has_notes_pattern = cursor.fetchone() is not None
    
    if not has_notes_pattern:
        # Add the new column
        cursor.execute("ALTER TABLE categorization_rules ADD COLUMN notes_pattern TEXT")
        
        # Migrate existing rules where field='notes'
        cursor.execute("""
            UPDATE categorization_rules 
            SET notes_pattern = pattern, pattern = NULL 
            WHERE field = 'notes'
        """)
        
        # Drop the old field column
        cursor.execute("ALTER TABLE categorization_rules DROP COLUMN field")
        
    conn.commit()
    cursor.close()

def down(conn):
    cursor = conn.cursor()
    cursor.execute("SET search_path TO private, public")
    
    # Re-add the field column
    cursor.execute("ALTER TABLE categorization_rules ADD COLUMN field TEXT DEFAULT 'description'")
    
    # Migrate data back
    cursor.execute("""
        UPDATE categorization_rules 
        SET pattern = notes_pattern, field = 'notes' 
        WHERE notes_pattern IS NOT NULL AND pattern IS NULL
    """)
    
    # Drop the notes_pattern column
    cursor.execute("ALTER TABLE categorization_rules DROP COLUMN notes_pattern")
    
    conn.commit()
    cursor.close()
