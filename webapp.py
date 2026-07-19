import os
import logging
import traceback
import urllib.parse
from logging.handlers import RotatingFileHandler
from flask import Flask, session, render_template, request

# Define log path in debug folder (mounted volume)
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

# Configure logging
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)

# File handler
file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=10)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Console handler (stdout)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Attach to the root logger to capture all logs (Flask, Werkzeug, etc.)
root_logger = logging.getLogger()
root_logger.handlers = [] # Clear existing handlers
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
root_logger.setLevel(logging.DEBUG)

app = Flask(__name__)
app.logger.info('Expense Tracker startup: Logger initialized in /debug/app.log')

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler to catch and log all unhandled exceptions"""
    # Pass through HTTP errors
    if hasattr(e, 'code') and e.code != 500:
        app.logger.warning(f"HTTP Error {e.code}: {e}")
        return e
    
    # Log non-HTTP errors with traceback
    app.logger.error(f"Unhandled Exception: {e}", exc_info=True)
    
    # Pre-fill for email crash reporting
    tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    tb_encoded = urllib.parse.quote(tb_str)
    
    return render_template("base.html", error="Er is een onverwachte fout opgetreden. Rapporteer dit probleem alstublieft.", traceback_encoded=tb_encoded), 500

app.secret_key = os.environ.get('SECRET_KEY', 'expense_tracker_secret_key_2024')

startup_error = None
tb_encoded = None
try:
    from db import Database, init_database
    db = Database()
    with app.app_context():
        init_database()
        app.logger.info('Database initialized successfully')
except Exception as e:
    app.logger.critical(f"Failed during startup: {e}", exc_info=True)
    startup_error = e
    tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    tb_encoded = urllib.parse.quote(tb_str)

if startup_error:
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return render_template("base.html", error=f"Applicatie kon niet starten: {startup_error}", traceback_encoded=tb_encoded), 500
else:
    # Import blueprints after db is set up
    from routes import main, transactions, accounts, categories, rules, dashboard
    
    # Register Blueprints
    app.register_blueprint(main.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(transactions.bp)
    app.register_blueprint(accounts.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(rules.bp)

    @app.route('/crash-test')
    def crash_test():
        raise Exception("This is a deliberate crash for testing the mailto link!")

# Log before every request
@app.before_request
def log_request_info():
    if request.path.startswith('/static'):
        return
    app.logger.debug(f"Request: {request.method} {request.path}")

@app.context_processor
def inject_global_data():
    """Make account list and active account available to all templates"""
    try:
        if 'db' not in globals() or db is None:
            return {'all_accounts': [], 'active_account': None, 'active_account_name': None}
        
        all_accounts = db.get_accounts()
        active_account = session.get('active_account', None)
        
        # Get friendly name for active account
        active_account_name = None
        if active_account:
            for acc in all_accounts:
                if acc['number'] == active_account:
                    active_account_name = acc['name']
                    break
        
        return {
            'all_accounts': all_accounts,
            'active_account': active_account,
            'active_account_name': active_account_name
        }
    except Exception as e:
        app.logger.error(f"Error in context processor: {e}", exc_info=True)
        return {'all_accounts': [], 'active_account': None, 'active_account_name': None}

if __name__ == '__main__':
    print("Starting Expense Tracker Web App...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
