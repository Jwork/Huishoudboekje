"""Budget, recurring-transaction, and goal repository"""
import pandas as pd
from datetime import date, datetime
from .connection import ConnectionManager


class BudgetRepository(ConnectionManager):
    """Repository for budgets, recurring transactions, and financial goals"""

    # ========================
    # Budgets
    # ========================

    def get_budgets(self):
        """Get all budgets with current spending for the current month"""
        conn = self.connect()
        cursor = conn.cursor()
        today = date.today()

        cursor.execute("""
            SELECT
                b.id,
                b.category_id,
                c.name AS category_name,
                p.name AS parent_category_name,
                b.amount AS budget_amount,
                b.period,
                COALESCE(SUM(
                    CASE WHEN t.direction = 'debit'
                              AND t.is_transfer = FALSE
                              AND EXTRACT(YEAR FROM t.date) = %s
                              AND EXTRACT(MONTH FROM t.date) = %s
                    THEN t.amount ELSE 0 END
                ), 0) AS spent
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            LEFT JOIN categories p ON c.parent_id = p.id
            LEFT JOIN transactions t ON t.category_id = c.id
            GROUP BY b.id, b.category_id, c.name, p.name, b.amount, b.period
            ORDER BY c.name
        """, (today.year, today.month))
        rows = cursor.fetchall()
        return [dict(r) for r in rows] if rows else []

    def set_budget(self, category_id, amount, period='monthly'):
        """Create or update a budget for a category"""
        conn = self.connect()
        cursor = conn.cursor()
        # Check if budget exists for this category
        cursor.execute(
            'SELECT id FROM budgets WHERE category_id = %s',
            (category_id,)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                'UPDATE budgets SET amount = %s, period = %s WHERE id = %s',
                (amount, period, existing['id'])
            )
            budget_id = existing['id']
        else:
            cursor.execute(
                'INSERT INTO budgets (category_id, amount, period) VALUES (%s, %s, %s) RETURNING id',
                (category_id, amount, period)
            )
            budget_id = cursor.fetchone()['id']
        conn.commit()
        return budget_id

    def delete_budget(self, budget_id):
        """Delete a budget"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM budgets WHERE id = %s', (budget_id,))
        conn.commit()

    def get_budget_status(self, category_id=None):
        """Get budget status (spent vs budgeted) for the current month"""
        conn = self.connect()
        cursor = conn.cursor()
        today = date.today()

        where_clause = ''
        params = [today.year, today.month]
        if category_id:
            where_clause = 'AND b.category_id = %s'
            params.append(category_id)

        cursor.execute(f"""
            SELECT
                b.id,
                b.category_id,
                c.name AS category_name,
                b.amount AS budget_amount,
                COALESCE(SUM(
                    CASE WHEN t.direction = 'debit'
                              AND t.is_transfer = FALSE
                    THEN t.amount ELSE 0 END
                ), 0) AS spent,
                b.period
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            LEFT JOIN transactions t ON t.category_id = c.id
                AND EXTRACT(YEAR FROM t.date) = %s
                AND EXTRACT(MONTH FROM t.date) = %s
            WHERE 1=1 {where_clause}
            GROUP BY b.id, b.category_id, c.name, b.amount, b.period
        """, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows] if rows else []

    # ========================
    # Recurring Transactions
    # ========================

    def get_recurring_transactions(self):
        """Get all recurring transaction definitions"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, c.name AS category_name
            FROM recurring_transactions r
            LEFT JOIN categories c ON r.category_id = c.id
            ORDER BY r.next_due ASC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows] if rows else []

    def add_recurring_transaction(self, description, amount, transaction_type,
                                  frequency, next_due, category_id=None):
        """Add a recurring transaction definition.

        Args:
            transaction_type: 'debit' or 'credit' — stored in 'direction' column.
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recurring_transactions
                (description, amount, direction, frequency, next_due,
                 category_id, start_date, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (description, amount, transaction_type, frequency, next_due,
              category_id, next_due))
        result = cursor.fetchone()
        conn.commit()
        return result['id']

    def update_recurring_transaction(self, recurring_id, **kwargs):
        """Update a recurring transaction definition"""
        if not kwargs:
            return

        # Map 'type' kwarg to 'direction' column if used
        if 'type' in kwargs:
            kwargs['direction'] = kwargs.pop('type')

        conn = self.connect()
        cursor = conn.cursor()
        set_parts = []
        params = []
        for key, value in kwargs.items():
            set_parts.append(f'{key} = %s')
            params.append(value)
        params.append(recurring_id)
        cursor.execute(
            f"UPDATE recurring_transactions SET {', '.join(set_parts)} WHERE id = %s",
            params
        )
        conn.commit()

    def delete_recurring_transaction(self, recurring_id):
        """Delete a recurring transaction definition"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM recurring_transactions WHERE id = %s', (recurring_id,))
        conn.commit()

    # ========================
    # Financial Goals
    # ========================

    def get_goals(self):
        """Get all financial goals"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.*,
                   COALESCE(SUM(gc.amount), 0) AS total_contributed
            FROM goals g
            LEFT JOIN goal_contributions gc ON gc.goal_id = g.id
            GROUP BY g.id
            ORDER BY g.priority DESC, g.created_at DESC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows] if rows else []

    def add_goal(self, name, target_amount, target_date=None, category_id=None):
        """Add a new financial goal"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO goals (name, target_amount, deadline, category)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (name, target_amount, target_date, category_id))
        result = cursor.fetchone()
        conn.commit()
        return result['id']

    def update_goal(self, goal_id, **kwargs):
        """Update a goal with given keyword arguments"""
        if not kwargs:
            return
        conn = self.connect()
        cursor = conn.cursor()
        set_parts = []
        params = []
        for key, value in kwargs.items():
            set_parts.append(f'{key} = %s')
            params.append(value)
        params.append(goal_id)
        cursor.execute(
            f"UPDATE goals SET {', '.join(set_parts)} WHERE id = %s",
            params
        )
        conn.commit()

    def delete_goal(self, goal_id):
        """Delete a goal and its contributions"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM goal_contributions WHERE goal_id = %s', (goal_id,))
        cursor.execute('DELETE FROM goals WHERE id = %s', (goal_id,))
        conn.commit()

    def add_goal_contribution(self, goal_id, amount, date_val=None, notes=None):
        """Add a contribution to a goal"""
        conn = self.connect()
        cursor = conn.cursor()
        contribution_date = date_val or date.today().isoformat()
        cursor.execute("""
            INSERT INTO goal_contributions (goal_id, amount, date, notes)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (goal_id, amount, contribution_date, notes))
        result = cursor.fetchone()

        # Update goal current_amount
        cursor.execute("""
            UPDATE goals SET current_amount = (
                SELECT COALESCE(SUM(amount), 0) FROM goal_contributions WHERE goal_id = %s
            ) WHERE id = %s
        """, (goal_id, goal_id))
        conn.commit()
        return result['id']

    def get_goal_contributions(self, goal_id):
        """Get contributions for a specific goal"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM goal_contributions
            WHERE goal_id = %s
            ORDER BY date DESC
        """, (goal_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows] if rows else []
