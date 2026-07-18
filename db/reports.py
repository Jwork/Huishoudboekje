"""Reporting repository - dashboard stats, summaries, trends"""
from datetime import date, timedelta
from .connection import ConnectionManager


class ReportRepository(ConnectionManager):
    """Repository for reporting and analytics queries"""

    def get_dashboard_stats(self, filters=None):
        """Get aggregated statistics for the dashboard.

        Returns dict with: total_income, total_expenses, net, transaction_count, etc.
        """
        filters = filters or {}
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = FALSE']
        params = []

        if filters.get('start_date'):
            where_clauses.append('t.date >= %s')
            params.append(filters['start_date'])
        if filters.get('end_date'):
            where_clauses.append('t.date <= %s')
            params.append(filters['end_date'])
        if filters.get('account'):
            where_clauses.append('t.account = %s')
            params.append(filters['account'])

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f"""
            SELECT
                COALESCE(SUM(CASE WHEN t.direction = 'credit' THEN t.amount ELSE 0 END), 0) AS total_income,
                COALESCE(SUM(CASE WHEN t.direction = 'debit'  THEN t.amount ELSE 0 END), 0) AS total_expenses,
                COUNT(t.id) AS transaction_count,
                COUNT(DISTINCT t.account) AS account_count,
                MIN(t.date) AS first_date,
                MAX(t.date) AS last_date
            FROM transactions t
            WHERE {where_sql}
        """, params)
        row = cursor.fetchone()

        stats = dict(row) if row else {}
        stats['net'] = float(stats.get('total_income', 0)) - float(stats.get('total_expenses', 0))
        # Convert Decimals to floats for JSON
        for key in ('total_income', 'total_expenses'):
            if key in stats and stats[key] is not None:
                stats[key] = float(stats[key])
        return stats

    def get_summary(self, filters=None):
        """Get financial summary, same as dashboard_stats (alias)"""
        return self.get_dashboard_stats(filters)

    def get_monthly_comparison(self, months=6):
        """Compare income and expenses across the last N months.

        Returns a list of dicts: [{month, year, income, expenses, net}, ...]
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                EXTRACT(YEAR FROM t.date)::int AS year,
                EXTRACT(MONTH FROM t.date)::int AS month,
                COALESCE(SUM(CASE WHEN t.direction = 'credit' THEN t.amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN t.direction = 'debit'  THEN t.amount ELSE 0 END), 0) AS expenses
            FROM transactions t
            WHERE t.is_transfer = FALSE
              AND t.date >= (CURRENT_DATE - INTERVAL '%s months')::date
            GROUP BY year, month
            ORDER BY year DESC, month DESC
            LIMIT %s
        """, (months, months))

        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['income'] = float(d['income'])
            d['expenses'] = float(d['expenses'])
            d['net'] = d['income'] - d['expenses']
            result.append(d)
        return result

    def get_category_trends(self, category_id, months=6):
        """Get spending trend for a specific category over several months"""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                EXTRACT(YEAR FROM t.date)::int AS year,
                EXTRACT(MONTH FROM t.date)::int AS month,
                COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            WHERE t.category_id = %s
              AND t.is_transfer = FALSE
              AND t.date >= (CURRENT_DATE - INTERVAL '%s months')::date
            GROUP BY year, month
            ORDER BY year, month
        """, (category_id, months))

        rows = cursor.fetchall()
        return [{'year': r['year'], 'month': r['month'], 'total': float(r['total'])} for r in rows]

    def get_cash_flow_forecast(self, months=3):
        """Get cash flow forecast based on recurring transactions.

        Projects income and expenses for the next N months using
        active recurring transaction definitions.
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT description, amount, direction, frequency, next_due
            FROM recurring_transactions
            WHERE active = TRUE
              AND (end_date IS NULL OR end_date >= CURRENT_DATE)
        """)
        recurring = cursor.fetchall()

        today = date.today()
        forecast = []
        for month_offset in range(months):
            m = today.month + month_offset
            y = today.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1

            income = 0.0
            expenses = 0.0
            for r in recurring:
                amt = float(r['amount'])
                if r['direction'] == 'credit':
                    income += amt
                else:
                    expenses += amt

            forecast.append({
                'year': y, 'month': m,
                'income': income, 'expenses': expenses,
                'net': income - expenses
            })

        return forecast

    def get_annual_summary(self, year=None):
        """Get annual summary broken down by month.

        Returns a list of 12 monthly entries with income, expenses, net.
        """
        if year is None:
            year = date.today().year

        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                EXTRACT(MONTH FROM t.date)::int AS month,
                COALESCE(SUM(CASE WHEN t.direction = 'credit' THEN t.amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN t.direction = 'debit'  THEN t.amount ELSE 0 END), 0) AS expenses
            FROM transactions t
            WHERE t.is_transfer = FALSE
              AND EXTRACT(YEAR FROM t.date) = %s
            GROUP BY month
            ORDER BY month
        """, (year,))

        rows = {r['month']: r for r in cursor.fetchall()}

        result = []
        for m in range(1, 13):
            if m in rows:
                r = rows[m]
                result.append({
                    'month': m,
                    'income': float(r['income']),
                    'expenses': float(r['expenses']),
                    'net': float(r['income']) - float(r['expenses'])
                })
            else:
                result.append({'month': m, 'income': 0.0, 'expenses': 0.0, 'net': 0.0})
        return result

    def get_savings_flow(self, start_date=None, end_date=None, account=None):
        """Get net savings flow per month.

        Measures money moved into/out of savings by looking at transfer
        transactions from the checking-account side:
        - debit transfers = money sent to savings (savings_in)
        - credit transfers = money received from savings (savings_out)

        Returns list of dicts: [{year, month, savings_in, savings_out, net_savings}]
        """
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = TRUE']
        params = []

        if start_date:
            where_clauses.append('t.date >= %s')
            params.append(start_date)
        if end_date:
            where_clauses.append('t.date <= %s')
            params.append(end_date)
        if account:
            where_clauses.append('t.account = %s')
            params.append(account)

        # Only count from the non-savings (checking) account side to avoid double-counting.
        # Checking-side transfers may have empty counter_account (e.g. ING GT code),
        # so we filter by the source account NOT being a transfer/savings account.
        where_clauses.append("""
            NOT EXISTS (
                SELECT 1 FROM accounts a
                WHERE a.account_number = t.account
                  AND a.is_transfer = TRUE
            )
        """)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f"""
            SELECT
                EXTRACT(YEAR FROM t.date)::int AS year,
                EXTRACT(MONTH FROM t.date)::int AS month,
                COALESCE(SUM(CASE WHEN t.direction = 'debit' THEN t.amount ELSE 0 END), 0) AS savings_in,
                COALESCE(SUM(CASE WHEN t.direction = 'credit' THEN t.amount ELSE 0 END), 0) AS savings_out
            FROM transactions t
            WHERE {where_sql}
            GROUP BY year, month
            ORDER BY year, month
        """, params)

        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['savings_in'] = float(d['savings_in'])
            d['savings_out'] = float(d['savings_out'])
            d['net_savings'] = d['savings_in'] - d['savings_out']
            result.append(d)
        return result

    def get_savings_flow_total(self, start_date=None, end_date=None, account=None):
        """Get aggregate savings flow for a period (single totals, not per-month)."""
        rows = self.get_savings_flow(start_date, end_date, account)
        totals = {'savings_in': 0.0, 'savings_out': 0.0, 'net_savings': 0.0}
        for r in rows:
            totals['savings_in'] += r['savings_in']
            totals['savings_out'] += r['savings_out']
            totals['net_savings'] += r['net_savings']
        return totals

    def get_savings_per_account(self, start_date=None, end_date=None, account=None):
        """Get savings in/out broken down by savings account name.

        Returns list of dicts: [{name, savings_in, savings_out, net}]
        """
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = TRUE']
        params = []

        if start_date:
            where_clauses.append('t.date >= %s')
            params.append(start_date)
        if end_date:
            where_clauses.append('t.date <= %s')
            params.append(end_date)
        if account:
            where_clauses.append('t.account = %s')
            params.append(account)

        where_clauses.append("""
            NOT EXISTS (
                SELECT 1 FROM accounts a
                WHERE a.account_number = t.account
                  AND a.is_transfer = TRUE
            )
        """)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f"""
            SELECT
                COALESCE(NULLIF(t.counter_account, ''), t.description) AS name,
                COALESCE(SUM(CASE WHEN t.direction = 'debit' THEN t.amount ELSE 0 END), 0) AS savings_in,
                COALESCE(SUM(CASE WHEN t.direction = 'credit' THEN t.amount ELSE 0 END), 0) AS savings_out
            FROM transactions t
            WHERE {where_sql}
            GROUP BY name
            ORDER BY savings_in DESC
        """, params)

        result = []
        for r in cursor.fetchall():
            d = dict(r)
            d['savings_in'] = float(d['savings_in'])
            d['savings_out'] = float(d['savings_out'])
            d['net'] = d['savings_in'] - d['savings_out']
            result.append(d)
        return result

    def get_category_breakdown(self, start_date=None, end_date=None, direction='debit', account=None):
        """Get spending/income aggregated by parent category.

        Subcategories are rolled up into their parent.
        Returns list of dicts: [{category_id, name, color, icon, total, percentage}]
        """
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = FALSE', f"t.direction = %s"]
        params = [direction]

        if start_date:
            where_clauses.append('t.date >= %s')
            params.append(start_date)
        if end_date:
            where_clauses.append('t.date <= %s')
            params.append(end_date)
        if account:
            where_clauses.append('t.account = %s')
            params.append(account)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f"""
            SELECT
                COALESCE(parent.id, c.id) AS category_id,
                COALESCE(parent.name, c.name) AS name,
                COALESCE(parent.color, c.color, '#808080') AS color,
                COALESCE(parent.icon, c.icon) AS icon,
                COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN categories parent ON c.parent_id = parent.id
            WHERE {where_sql}
            GROUP BY COALESCE(parent.id, c.id),
                     COALESCE(parent.name, c.name),
                     COALESCE(parent.color, c.color, '#808080'),
                     COALESCE(parent.icon, c.icon)
            ORDER BY total DESC
        """, params)

        rows = cursor.fetchall()
        result = []
        grand_total = sum(float(r['total']) for r in rows) if rows else 0

        for r in rows:
            total = float(r['total'])
            result.append({
                'category_id': r['category_id'],
                'name': r['name'] or 'Niet-gecategoriseerd',
                'color': r['color'] or '#808080',
                'icon': r['icon'],
                'total': total,
                'percentage': round(total / grand_total * 100, 1) if grand_total else 0
            })
        return result

    def get_subcategory_breakdown(self, parent_id, start_date=None, end_date=None, direction='debit', account=None):
        """Get breakdown of subcategories within a parent category.

        Returns list of dicts: [{category_id, name, total, percentage}]
        """
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = FALSE', 't.direction = %s']
        params = [direction]

        # Include transactions categorized directly to the parent OR to its children
        where_clauses.append('(c.id = %s OR c.parent_id = %s)')
        params.extend([parent_id, parent_id])

        if start_date:
            where_clauses.append('t.date >= %s')
            params.append(start_date)
        if end_date:
            where_clauses.append('t.date <= %s')
            params.append(end_date)
        if account:
            where_clauses.append('t.account = %s')
            params.append(account)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f"""
            SELECT
                c.id AS category_id,
                c.name AS name,
                COALESCE(c.color, '#808080') AS color,
                COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE {where_sql}
            GROUP BY c.id, c.name, c.color
            ORDER BY total DESC
        """, params)

        rows = cursor.fetchall()
        result = []
        grand_total = sum(float(r['total']) for r in rows) if rows else 0

        for r in rows:
            total = float(r['total'])
            result.append({
                'category_id': r['category_id'],
                'name': r['name'],
                'color': r['color'] or '#808080',
                'total': total,
                'percentage': round(total / grand_total * 100, 1) if grand_total else 0
            })
        return result

    def get_monthly_trend(self, start_date=None, end_date=None, account=None):
        """Get monthly income/expense trend for a date range.

        Unlike get_monthly_comparison (which uses last N months from today),
        this accepts explicit date boundaries.

        Returns list of dicts: [{year, month, income, expenses, net}]
        """
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = FALSE']
        params = []

        if start_date:
            where_clauses.append('t.date >= %s')
            params.append(start_date)
        if end_date:
            where_clauses.append('t.date <= %s')
            params.append(end_date)
        if account:
            where_clauses.append('t.account = %s')
            params.append(account)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f"""
            SELECT
                EXTRACT(YEAR FROM t.date)::int AS year,
                EXTRACT(MONTH FROM t.date)::int AS month,
                COALESCE(SUM(CASE WHEN t.direction = 'credit' THEN t.amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN t.direction = 'debit'  THEN t.amount ELSE 0 END), 0) AS expenses
            FROM transactions t
            WHERE {where_sql}
            GROUP BY year, month
            ORDER BY year, month
        """, params)

        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['income'] = float(d['income'])
            d['expenses'] = float(d['expenses'])
            d['net'] = d['income'] - d['expenses']
            result.append(d)
        return result

    def get_category_trend(self, category_id, start_date=None, end_date=None, account=None):
        """Get spending trend for a category over a date range (includes subcategories).

        Unlike get_category_trends (which uses last N months), this accepts
        explicit date boundaries and rolls up subcategories.
        """
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = FALSE', '(c.id = %s OR c.parent_id = %s)']
        params = [category_id, category_id]

        if start_date:
            where_clauses.append('t.date >= %s')
            params.append(start_date)
        if end_date:
            where_clauses.append('t.date <= %s')
            params.append(end_date)
        if account:
            where_clauses.append('t.account = %s')
            params.append(account)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f"""
            SELECT
                EXTRACT(YEAR FROM t.date)::int AS year,
                EXTRACT(MONTH FROM t.date)::int AS month,
                COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE {where_sql}
            GROUP BY year, month
            ORDER BY year, month
        """, params)

        rows = cursor.fetchall()
        return [{'year': r['year'], 'month': r['month'], 'total': float(r['total'])} for r in rows]

    def get_budget_overview(self, start_date=None, end_date=None, account=None):
        """Get a structured budget overview using the category tree.

        Uses transaction direction (debit/credit) to determine income vs expenses.
        Returns a nested structure: {income: [...], expenses: [...], totals: {...}}
        where each section has groups (mid-level categories) with child items.
        """
        conn = self.connect()
        cursor = conn.cursor()

        where_clauses = ['t.is_transfer = FALSE']
        params = []

        if start_date:
            where_clauses.append('t.date >= %s')
            params.append(start_date)
        if end_date:
            where_clauses.append('t.date <= %s')
            params.append(end_date)
        if account:
            where_clauses.append('t.account = %s')
            params.append(account)

        where_sql = ' AND '.join(where_clauses)

        # Get totals per leaf category, split by direction
        cursor.execute(f"""
            SELECT
                t.direction,
                t.category_id,
                c.name AS category_name,
                c.color AS category_color,
                c.parent_id,
                COALESCE(parent.name, c.name) AS group_name,
                COALESCE(parent.color, c.color, '#808080') AS group_color,
                COALESCE(parent.parent_id, c.parent_id) AS root_parent_id,
                COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN categories parent ON c.parent_id = parent.id
            WHERE {where_sql}
            GROUP BY t.direction, t.category_id, c.name, c.color, c.parent_id,
                     parent.name, parent.color, parent.parent_id
            ORDER BY total DESC
        """, params)

        rows = cursor.fetchall()

        # Calculate number of months in the period for averages
        if start_date and end_date:
            from datetime import date as dt_date
            if isinstance(start_date, str):
                s = dt_date.fromisoformat(start_date)
            else:
                s = start_date
            if isinstance(end_date, str):
                e = dt_date.fromisoformat(end_date)
            else:
                e = end_date
            month_count = max(1, (e.year - s.year) * 12 + e.month - s.month + 1)
        else:
            month_count = 1

        # Build the tree per direction
        def build_tree(direction_rows):
            groups = {}
            uncategorized_total = 0.0
            for r in direction_rows:
                total = float(r['total'])
                cat_id = r['category_id']
                cat_name = r['category_name'] or 'Niet-gecategoriseerd'
                parent_id = r['parent_id']
                group_name = r['group_name'] or 'Niet-gecategoriseerd'
                group_color = r['group_color'] or '#808080'

                if cat_id is None:
                    uncategorized_total += total
                    continue

                if parent_id is None:
                    # Root or standalone category
                    group_key = cat_name
                    if group_key not in groups:
                        groups[group_key] = {
                            'name': cat_name,
                            'color': r['category_color'] or '#808080',
                            'items': [],
                            'subtotal': 0.0,
                        }
                    groups[group_key]['subtotal'] += total
                    groups[group_key]['items'].append({
                        'name': cat_name,
                        'color': r['category_color'] or '#808080',
                        'total': total,
                        'monthly_avg': total / month_count,
                    })
                else:
                    if group_name not in groups:
                        groups[group_name] = {
                            'name': group_name,
                            'color': group_color,
                            'items': [],
                            'subtotal': 0.0,
                        }
                    groups[group_name]['subtotal'] += total
                    groups[group_name]['items'].append({
                        'name': cat_name,
                        'color': r['category_color'] or '#808080',
                        'total': total,
                        'monthly_avg': total / month_count,
                    })

            if uncategorized_total > 0:
                groups['Niet-gecategoriseerd'] = {
                    'name': 'Niet-gecategoriseerd',
                    'color': '#9ca3af',
                    'items': [{
                        'name': 'Niet-gecategoriseerd',
                        'color': '#9ca3af',
                        'total': uncategorized_total,
                        'monthly_avg': uncategorized_total / month_count,
                    }],
                    'subtotal': uncategorized_total,
                }

            result = sorted(groups.values(), key=lambda g: g['subtotal'], reverse=True)
            for g in result:
                g['monthly_avg'] = g['subtotal'] / month_count
                g['items'] = sorted(g['items'], key=lambda i: i['total'], reverse=True)
            return result

        credit_rows = [r for r in rows if r['direction'] == 'credit']
        debit_rows = [r for r in rows if r['direction'] == 'debit']

        income_groups = build_tree(credit_rows)
        expense_groups = build_tree(debit_rows)

        total_income = sum(g['subtotal'] for g in income_groups)
        total_expenses = sum(g['subtotal'] for g in expense_groups)

        return {
            'income': income_groups,
            'expenses': expense_groups,
            'totals': {
                'income': total_income,
                'expenses': total_expenses,
                'net': total_income - total_expenses,
                'income_monthly': total_income / month_count,
                'expenses_monthly': total_expenses / month_count,
                'net_monthly': (total_income - total_expenses) / month_count,
            },
            'month_count': month_count,
        }
