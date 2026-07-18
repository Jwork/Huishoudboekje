"""Database module for expense tracker - PostgreSQL only"""
from .connection import ConnectionManager, get_connection_string
from .schema import init_database, SCHEMA_SQL, DEFAULT_CATEGORIES
from .transactions import TransactionRepository
from .categories import CategoryRepository
from .accounts import AccountRepository
from .budgets import BudgetRepository
from .transfers import TransferRepository
from .reports import ReportRepository
from .depreciations import DepreciationRepository


class Database:
    """Main database class that aggregates all repositories and provides a unified API"""
    
    def __init__(self):
        self._transactions = TransactionRepository()
        self._categories = CategoryRepository()
        self._accounts = AccountRepository()
        self._budgets = BudgetRepository()
        self._transfers = TransferRepository()
        self._reports = ReportRepository()
        self._depreciations = DepreciationRepository()
    
    def init(self):
        """Initialize the database schema and default data"""
        init_database()
    
    # ===================
    # Transaction Methods
    # ===================
    
    def import_csv(self, csv_file, progress_callback=None, filename=None, format_id=None, retained_file=None):
        """Import transactions from CSV file and auto-categorize them"""
        result = self._transactions.import_csv(csv_file, progress_callback, filename, format_id=format_id, retained_file=retained_file)
        
        # Auto-apply rules to newly imported transactions (and any existing uncategorized ones)
        try:
            self.auto_categorize_transactions()
        except Exception as e:
            # Don't fail the import if categorization fails, just print/log
            print(f"Auto-categorization failed: {e}")
            
        return result
    
    def get_transactions(self, filters=None, page=1, per_page=None, sort_by='date', sort_dir='desc'):
        """Get transactions with optional filters, sorting, and pagination"""
        return self._transactions.get_transactions(filters, page, per_page, sort_by=sort_by, sort_dir=sort_dir)
    
    def update_transaction_category(self, transaction_id, category_id):
        """Update category for a transaction"""
        self._transactions.update_transaction_category(transaction_id, category_id)
    
    def bulk_update_category(self, transaction_ids, category_id):
        """Update category for multiple transactions"""
        return self._transactions.bulk_update_category(transaction_ids, category_id)
    
    def update_transaction_notes(self, transaction_id, notes):
        """Update notes for a transaction"""
        self._transactions.update_transaction_notes(transaction_id, notes)

    def update_transaction_type(self, transaction_id, trans_type):
        """Update transaction direction (debit/credit)"""
        self._transactions.update_transaction_type(transaction_id, trans_type)
    
    def update_transaction_transfer_status(self, transaction_id, is_transfer):
        """Update transaction transfer status"""
        self._transactions.update_transaction_transfer_status(transaction_id, bool(is_transfer))

    def update_transaction_incidental_status(self, transaction_id, is_incidental):
        """Update transaction incidental status"""
        self._transactions.update_transaction_incidental_status(transaction_id, is_incidental)
    
    def get_transaction_by_id(self, transaction_id):
        """Get a single transaction by ID"""
        return self._transactions.get_transaction_by_id(transaction_id)
    
    def delete_transactions(self, transaction_ids):
        """Delete multiple transactions"""
        self._transactions.delete_transactions(transaction_ids)
    
    def get_dashboard_stats(self, filters=None):
        """Get aggregated statistics for the dashboard"""
        return self._reports.get_dashboard_stats(filters)
    
    def get_uncategorized_transactions(self, limit=100):
        """Get transactions without a category"""
        return self._transactions.get_uncategorized_transactions(limit)
    
    def get_transaction_count(self, filters=None):
        """Get total number of transactions matching filters"""
        return self._transactions.get_transaction_count(filters)
    
    def get_transaction(self, transaction_id):
        """Get a single transaction by ID"""
        return self._transactions.get_transaction(transaction_id)
    
    def get_unique_merchants(self, filters=None):
        """Get unique merchant names with transaction counts"""
        return self._transactions.get_unique_merchants(filters)
    
    def search_transactions(self, search_term, filters=None):
        """Full-text search on transactions"""
        return self._transactions.search_transactions(search_term, filters)
    
    def bulk_categorize_by_merchant(self, merchant, category_id):
        """Categorize all transactions from a specific merchant"""
        return self._transactions.bulk_categorize_by_merchant(merchant, category_id)
    
    def get_import_batches(self):
        """Get list of all import batches"""
        return self._transactions.get_import_batches()
    
    def rebuild_from_files(self, progress_callback=None):
        """Rebuild the database from retained CSV files"""
        return self._transactions.rebuild_from_files()
    
    # ==================
    # Category Methods
    # ==================
    
    def get_categories(self):
        """Get all categories"""
        return self._categories.get_categories()
    
    def get_category(self, category_id):
        """Get a single category by ID"""
        return self._categories.get_category(category_id)
    
    def get_category_by_name(self, name, parent_id=None):
        """Get category by name and optional parent_id"""
        return self._categories.get_category_by_name(name, parent_id)
    
    def add_category(self, name, parent_id=None, color='#808080', icon=None):
        """Add a new category"""
        return self._categories.add_category(name, parent_id, color, icon)
    
    def update_category(self, category_id, name):
        """Update category name"""
        self._categories.update_category(category_id, name)
    
    def delete_category(self, category_id):
        """Delete a category"""
        return self._categories.delete_category(category_id)
    
    def get_category_summary(self, filters=None):
        """Get spending summary by category"""
        return self._categories.get_category_summary(filters)
    
    def add_categorization_rule(self, pattern, category_id, field='description', priority=0, min_amount=None, max_amount=None, transaction_type=None, counter_account=None):
        """Add an auto-categorization rule"""
        return self._categories.add_categorization_rule(pattern, category_id, field, priority, min_amount, max_amount, transaction_type, counter_account)
    
    def update_categorization_rule(self, rule_id, **kwargs):
        """Update a categorization rule"""
        self._categories.update_categorization_rule(rule_id, **kwargs)
    
    def get_categorization_rules(self, active_only=True):
        """Get all categorization rules"""
        return self._categories.get_categorization_rules(active_only)
    
    def delete_categorization_rule(self, rule_id):
        """Delete a categorization rule"""
        self._categories.delete_categorization_rule(rule_id)
    
    def auto_categorize_transactions(self):
        """Apply auto-categorization rules to uncategorized transactions"""
        return self._categories.auto_categorize_transactions()
    
    def get_rule_match_counts(self):
        """Get match counts for all rules"""
        return self._categories.get_rule_match_counts()
    
    def test_rule(self, **kwargs):
        """Preview which transactions a rule would match"""
        return self._categories.test_rule(**kwargs)
    
    def find_conflicting_rules(self, **kwargs):
        """Find existing rules that overlap with given criteria"""
        return self._categories.find_conflicting_rules(**kwargs)
    
    def reorder_rule_priorities(self, rule_ids_ordered):
        """Reorder rule priorities"""
        self._categories.reorder_rule_priorities(rule_ids_ordered)
    
    def get_unique_counter_accounts(self):
        """Get unique counter accounts with their most-used description name"""
        return self._transactions.get_unique_counter_accounts()
    
    # =================
    # Account Methods
    # =================
    
    def get_accounts(self, include_counter_accounts=False):
        """Get all accounts; optionally include counter accounts"""
        return self._accounts.get_accounts(include_counter_accounts)
    
    def set_account_name(self, account_number, name):
        """Set friendly name for an account"""
        self._accounts.set_account_name(account_number, name)
    
    def toggle_transfer_account(self, account_number, is_transfer):
        """Set or toggle is_transfer flag for an account"""
        return self._accounts.toggle_transfer_account(account_number, is_transfer)
    
    def get_transfer_accounts(self):
        """Get accounts marked as transfer accounts"""
        return self._accounts.get_transfer_accounts()

    def add_transfer_account(self, account_number, name=None):
        """Add a transfer account with optional friendly name"""
        return self._accounts.add_transfer_account(account_number, name)

    def remove_transfer_account(self, account_id):
        """Remove transfer flag from an account"""
        return self._accounts.remove_transfer_account(account_id)
    
    def is_transfer_account(self, account_number):
        """Check if an account is marked as a transfer account"""
        return self._accounts.is_transfer_account(account_number)

    def get_inter_account_cashflow(self, selected_accounts, start_date=None, end_date=None):
        """Get cashflow between selected accounts"""
        return self._accounts.get_inter_account_cashflow(selected_accounts, start_date, end_date)
    
    # ================
    # Budget Methods
    # ================
    
    def get_budgets(self):
        """Get all budgets with current spending"""
        return self._budgets.get_budgets()
    
    def set_budget(self, category_id, amount, period='monthly'):
        """Set or update a budget for a category"""
        return self._budgets.set_budget(category_id, amount, period)
    
    def delete_budget(self, budget_id):
        """Delete a budget"""
        self._budgets.delete_budget(budget_id)
    
    def get_budget_status(self, category_id=None):
        """Get budget status (spent vs budgeted)"""
        return self._budgets.get_budget_status(category_id)
    
    # ==============
    # Goal Methods
    # ==============
    
    def get_goals(self):
        """Get all financial goals"""
        return self._budgets.get_goals()
    
    def add_goal(self, name, target_amount, target_date=None, category_id=None):
        """Add a new financial goal"""
        return self._budgets.add_goal(name, target_amount, target_date, category_id)
    
    def update_goal(self, goal_id, **kwargs):
        """Update a goal"""
        self._budgets.update_goal(goal_id, **kwargs)
    
    def delete_goal(self, goal_id):
        """Delete a goal"""
        self._budgets.delete_goal(goal_id)
    
    def add_goal_contribution(self, goal_id, amount, date=None, notes=None):
        """Add a contribution to a goal"""
        return self._budgets.add_goal_contribution(goal_id, amount, date, notes)
    
    def get_goal_contributions(self, goal_id):
        """Get contributions for a goal"""
        return self._budgets.get_goal_contributions(goal_id)
    
    # ====================
    # Recurring Methods
    # ====================
    
    def get_recurring_transactions(self):
        """Get all recurring transaction definitions"""
        return self._budgets.get_recurring_transactions()
    
    def add_recurring_transaction(self, description, amount, transaction_type, 
                                   frequency, next_due, category_id=None):
        """Add a recurring transaction definition"""
        return self._budgets.add_recurring_transaction(
            description, amount, transaction_type, frequency, next_due, category_id
        )
    
    def update_recurring_transaction(self, recurring_id, **kwargs):
        """Update a recurring transaction"""
        self._budgets.update_recurring_transaction(recurring_id, **kwargs)
    
    def delete_recurring_transaction(self, recurring_id):
        """Delete a recurring transaction"""
        self._budgets.delete_recurring_transaction(recurring_id)
    
    # ==================
    # Transfer Methods
    # ==================
    
    def auto_mark_transfer_transactions(self):
        """Automatically mark transactions as transfers based on transfer accounts"""
        return self._transfers.auto_mark_transfer_transactions()
    
    def auto_link_transfer_pairs(self):
        """Automatically link matching transfer pairs"""
        return self._transfers.auto_link_transfer_pairs()
    
    def get_linked_transfers(self):
        """Get all linked transfer pairs"""
        return self._transfers.get_linked_transfers()

    def link_transfer_pair(self, transaction_id_1, transaction_id_2):
        """Manually link two transactions as a transfer pair"""
        return self._transfers.link_transfer_pair(transaction_id_1, transaction_id_2)

    def unlink_transfer_pair(self, transaction_id):
        """Remove transfer link from a transaction"""
        return self._transfers.unlink_transfer_pair(transaction_id)
    def find_unlinked_transfer_pairs(self):
        """Find potential transfer pairs that are not yet linked"""
        return self._transfers.find_unlinked_transfer_pairs()

    def mark_transfer_account_transactions(self, account_number):
        """Mark transactions related to a transfer account"""
        return self._transfers.mark_transfer_account_transactions(account_number)

    def get_transfer_patterns(self):
        """Get all transfer merchant patterns"""
        return self._transfers.get_transfer_patterns()

    def add_transfer_pattern(self, pattern, name=None):
        """Add a merchant pattern treated as transfer"""
        return self._transfers.add_transfer_pattern(pattern, name)

    def remove_transfer_pattern(self, pattern_id):
        """Remove a transfer merchant pattern"""
        return self._transfers.remove_transfer_pattern(pattern_id)

    def mark_transfer_pattern_transactions(self, pattern):
        """Mark transactions matching a pattern as transfers"""
        return self._transfers.mark_transfer_pattern_transactions(pattern)
    
    def mark_as_transfer(self, transaction_id, is_transfer=True):
        """Manually mark a transaction as a transfer"""
        self._transfers.mark_as_transfer(transaction_id, is_transfer)
    
    def link_transfers(self, transaction_id_1, transaction_id_2):
        """Manually link two transactions as a transfer pair"""
        self._transfers.link_transfers(transaction_id_1, transaction_id_2)
    
    def unlink_transfer(self, transaction_id):
        """Remove transfer link from a transaction"""
        self._transfers.unlink_transfer(transaction_id)
    
    # =================
    # Report Methods
    # =================
    
    def get_summary(self, filters=None):
        """Get financial summary"""
        return self._reports.get_summary(filters)
    
    def get_monthly_comparison(self, months=6):
        """Compare spending across multiple months"""
        return self._reports.get_monthly_comparison(months)
    
    def get_category_trends(self, category_id, months=6):
        """Get spending trend for a specific category"""
        return self._reports.get_category_trends(category_id, months)
    
    def get_cash_flow_forecast(self, months=3):
        """Get cash flow forecast based on recurring transactions"""
        return self._reports.get_cash_flow_forecast(months)
    
    def get_annual_summary(self, year=None):
        """Get annual summary by month"""
        return self._reports.get_annual_summary(year)
    
    def get_savings_flow(self, start_date=None, end_date=None, account=None):
        """Get net savings flow per month"""
        return self._reports.get_savings_flow(start_date, end_date, account)
    
    def get_savings_flow_total(self, start_date=None, end_date=None, account=None):
        """Get aggregate savings flow totals for a period"""
        return self._reports.get_savings_flow_total(start_date, end_date, account)

    def get_savings_per_account(self, start_date=None, end_date=None, account=None):
        """Get savings in/out per savings account"""
        return self._reports.get_savings_per_account(start_date, end_date, account)
    
    def get_category_breakdown(self, start_date=None, end_date=None, direction='debit', account=None):
        """Get spending/income by parent category"""
        return self._reports.get_category_breakdown(start_date, end_date, direction, account)
    
    def get_subcategory_breakdown(self, parent_id, start_date=None, end_date=None, direction='debit', account=None):
        """Get subcategory breakdown within a parent"""
        return self._reports.get_subcategory_breakdown(parent_id, start_date, end_date, direction, account)
    
    def get_monthly_trend(self, start_date=None, end_date=None, account=None):
        """Get monthly income/expense trend for a date range"""
        return self._reports.get_monthly_trend(start_date, end_date, account)
    
    def get_category_trend(self, category_id, start_date=None, end_date=None, account=None):
        """Get spending trend for a category over a date range"""
        return self._reports.get_category_trend(category_id, start_date, end_date, account)

    def get_budget_overview(self, start_date=None, end_date=None, account=None):
        """Get structured budget overview using category tree"""
        return self._reports.get_budget_overview(start_date, end_date, account)

    # ======================
    # Depreciation Methods
    # ======================
    
    def add_depreciation(self, name, purchase_date, purchase_amount, 
                         useful_life_months, residual_value=0, category_id=None, notes=None):
        """Add a new depreciation asset"""
        return self._depreciations.add_depreciation(
            name, purchase_date, purchase_amount, useful_life_months,
            residual_value, category_id, notes
        )
    
    def update_depreciation(self, depreciation_id, **kwargs):
        """Update depreciation asset fields"""
        self._depreciations.update_depreciation(depreciation_id, **kwargs)
    
    def delete_depreciation(self, depreciation_id):
        """Delete a depreciation asset"""
        self._depreciations.delete_depreciation(depreciation_id)
    
    def get_depreciations(self, active_only=True):
        """Get all depreciation assets"""
        return self._depreciations.get_depreciations(active_only)
    
    def get_depreciation(self, depreciation_id):
        """Get a single depreciation asset by ID"""
        return self._depreciations.get_depreciation(depreciation_id)
    
    def calculate_depreciation(self, depreciation_id, as_of_date=None):
        """Calculate depreciation values for an asset"""
        return self._depreciations.calculate_depreciation(depreciation_id, as_of_date)
    
    def get_depreciation_summary(self, as_of_date=None):
        """Get summary of all active depreciations"""
        return self._depreciations.get_depreciation_summary(as_of_date)
    
    def get_monthly_depreciation_schedule(self, depreciation_id):
        """Get month-by-month depreciation schedule for an asset"""
        return self._depreciations.get_monthly_depreciation_schedule(depreciation_id)
    
    def get_year_depreciation_expense(self, year=None):
        """Get total depreciation expense for a year"""
        return self._depreciations.get_year_depreciation_expense(year)
    
    # =================
    # Filter Methods
    # =================
    
    def save_filter(self, name, filter_config):
        """Save a filter configuration"""
        return self._transactions.save_filter(name, filter_config)
    
    def get_saved_filters(self):
        """Get all saved filters"""
        return self._transactions.get_saved_filters()
    
    def delete_saved_filter(self, filter_id):
        """Delete a saved filter"""
        self._transactions.delete_saved_filter(filter_id)


# Singleton instance for backward compatibility
_db_instance = None

def get_db():
    """Get the database singleton instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


__all__ = [
    'Database',
    'get_db',
    'ConnectionManager',
    'get_connection_string',
    'init_database',
    'SCHEMA_SQL',
    'DEFAULT_CATEGORIES',
    'TransactionRepository',
    'CategoryRepository',
    'AccountRepository',
    'BudgetRepository',
    'TransferRepository',
    'ReportRepository',
    'DepreciationRepository'
]
