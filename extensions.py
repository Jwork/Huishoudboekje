# Extensions module - provides shared db instance for backward compatibility with routes
# Routes import 'db' from here; webapp.py creates and initializes the actual instance
from db import get_db

# Provide db singleton for routes that import from extensions
db = get_db()
