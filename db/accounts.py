"""Account repository - manages accounts, transfer accounts, and balances"""
import pandas as pd
from .connection import ConnectionManager


class AccountRepository(ConnectionManager):
    """Repository for account-related operations"""

    def get_accounts(self, include_counter_accounts=False):
        """Get accounts, optionally including counter-party accounts from transactions.

        When include_counter_accounts=False, returns only owned accounts
        (those appearing in the 'account' column of transactions).
        When True, also includes accounts that appear only in counter_account.
        """
        conn = self.connect()
        cursor = conn.cursor()

        if include_counter_accounts:
            cursor.execute("""
                WITH all_accounts AS (
                    SELECT DISTINCT account AS account_number FROM transactions
                    UNION
                    SELECT DISTINCT counter_account FROM transactions
                    WHERE counter_account IS NOT NULL AND counter_account != ''
                )
                SELECT
                    a.account_number,
                    COALESCE(acc.name, a.account_number) AS name,
                    COALESCE(acc.is_transfer, FALSE) AS is_transfer,
                    COALESCE(acc.is_active, TRUE) AS is_active,
                    acc.id,
                    COUNT(t.id) AS transaction_count
                FROM all_accounts a
                LEFT JOIN accounts acc ON a.account_number = acc.account_number
                LEFT JOIN transactions t ON t.account = a.account_number
                                         OR t.counter_account = a.account_number
                GROUP BY a.account_number, acc.name, acc.is_transfer, acc.is_active, acc.id
                ORDER BY transaction_count DESC
            """)
        else:
            cursor.execute("""
                SELECT DISTINCT
                    t.account AS account_number,
                    COALESCE(a.name, t.account) AS name,
                    COALESCE(a.is_transfer, FALSE) AS is_transfer,
                    COALESCE(a.is_active, TRUE) AS is_active,
                    a.id,
                    COUNT(t.id) AS transaction_count,
                    MIN(t.date) AS first_transaction,
                    MAX(t.date) AS last_transaction
                FROM transactions t
                LEFT JOIN accounts a ON t.account = a.account_number
                GROUP BY t.account, a.name, a.is_transfer, a.is_active, a.id
                ORDER BY transaction_count DESC
            """)

        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d['number'] = d['account_number']
            d['has_name'] = d['name'] != d['account_number']
            results.append(d)
        return results

    def set_account_name(self, account_number, name):
        """Set or update the friendly name for an account"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO accounts (account_number, name)
            VALUES (%s, %s)
            ON CONFLICT (account_number)
            DO UPDATE SET name = EXCLUDED.name
        """, (account_number, name))
        conn.commit()

    def toggle_transfer_account(self, account_number, is_transfer):
        """Set the is_transfer flag for an account"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO accounts (account_number, name, is_transfer)
            VALUES (%s, %s, %s)
            ON CONFLICT (account_number)
            DO UPDATE SET is_transfer = EXCLUDED.is_transfer
        """, (account_number, account_number, bool(is_transfer)))
        conn.commit()

    def get_transfer_accounts(self):
        """Get all accounts marked as transfer/savings accounts"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, account_number, name
            FROM accounts
            WHERE is_transfer = TRUE
            ORDER BY name
        """)
        return [dict(r) for r in cursor.fetchall()]

    def add_transfer_account(self, account_number, name=None):
        """Add an account and mark it as a transfer account"""
        conn = self.connect()
        cursor = conn.cursor()
        display_name = name or account_number
        cursor.execute("""
            INSERT INTO accounts (account_number, name, is_transfer)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (account_number)
            DO UPDATE SET is_transfer = TRUE, name = COALESCE(EXCLUDED.name, accounts.name)
        """, (account_number, display_name))
        conn.commit()

    def remove_transfer_account(self, account_id):
        """Remove the transfer flag from an account"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE accounts SET is_transfer = FALSE WHERE id = %s',
            (account_id,)
        )
        conn.commit()

    def is_transfer_account(self, account_number):
        """Check if an account number is marked as a transfer account"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT is_transfer FROM accounts WHERE account_number = %s',
            (account_number,)
        )
        row = cursor.fetchone()
        return bool(row['is_transfer']) if row else False

    def update_account_balance(self, account_number):
        """Recalculate and update the current balance for an account.

        balance = initial_balance + SUM(credit amounts) - SUM(debit amounts)
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN direction = 'credit' THEN amount ELSE 0 END), 0)
                - COALESCE(SUM(CASE WHEN direction = 'debit' THEN amount ELSE 0 END), 0)
                AS net
            FROM transactions
            WHERE account = %s
        """, (account_number,))
        net = cursor.fetchone()['net']

        cursor.execute("""
            UPDATE accounts
            SET current_balance = initial_balance + %s
            WHERE account_number = %s
        """, (net, account_number))
        conn.commit()

    def get_inter_account_cashflow(self, selected_accounts, start_date=None, end_date=None):
        """Get cash-flow edges between selected accounts.

        Returns a list of dicts: {from_account, to_account, total_amount, count}
        Each row represents the total money transferred from one account to another.
        """
        if not selected_accounts:
            return []

        conn = self.connect()
        cursor = conn.cursor()

        placeholders = ', '.join(['%s'] * len(selected_accounts))
        params = list(selected_accounts) + list(selected_accounts)

        date_filter = ''
        if start_date:
            date_filter += ' AND t.date >= %s'
            params.append(start_date)
        if end_date:
            date_filter += ' AND t.date <= %s'
            params.append(end_date)

        cursor.execute(f"""
            SELECT
                CASE WHEN t.direction = 'debit' THEN t.account ELSE t.counter_account END AS from_account,
                CASE WHEN t.direction = 'debit' THEN t.counter_account ELSE t.account END AS to_account,
                SUM(t.amount) AS total_amount,
                COUNT(*) AS count
            FROM transactions t
            WHERE t.is_transfer = TRUE
              AND t.account IN ({placeholders})
              AND t.counter_account IN ({placeholders})
              {date_filter}
            GROUP BY from_account, to_account
            ORDER BY total_amount DESC
        """, params)
        return [dict(r) for r in cursor.fetchall()]
