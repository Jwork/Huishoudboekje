"""Category repository - handles categories and auto-categorization rules"""
import pandas as pd
from .connection import ConnectionManager


class CategoryRepository(ConnectionManager):
    """Repository for category and categorization-rule operations"""

    # ========================
    # Category CRUD
    # ========================

    def get_categories(self):
        """Get all categories with parent names resolved"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, p.name AS parent_name
            FROM categories c
            LEFT JOIN categories p ON c.parent_id = p.id
            ORDER BY COALESCE(p.name, c.name), c.name
        """)
        rows = cursor.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def get_category(self, category_id):
        """Get a single category by ID"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, p.name AS parent_name
            FROM categories c
            LEFT JOIN categories p ON c.parent_id = p.id
            WHERE c.id = %s
        """, (category_id,))
        return cursor.fetchone()

    def get_category_by_name(self, name, parent_id=None):
        """Get category by name and optional parent_id"""
        conn = self.connect()
        cursor = conn.cursor()
        if parent_id is not None:
            cursor.execute(
                'SELECT * FROM categories WHERE name = %s AND parent_id = %s',
                (name, parent_id)
            )
        else:
            cursor.execute(
                'SELECT * FROM categories WHERE name = %s AND parent_id IS NULL',
                (name,)
            )
        return cursor.fetchone()

    def add_category(self, name, parent_id=None, color=None, icon=None):
        """Add a new category"""
        if not color or color == '#808080':
            import hashlib
            colors = [
                '#F44336', '#E91E63', '#9C27B0', '#673AB7', '#3F51B5', 
                '#2196F3', '#03A9F4', '#00BCD4', '#009688', '#4CAF50', 
                '#8BC34A', '#CDDC39', '#FFC107', '#FF9800', '#FF5722', 
                '#795548', '#607D8B'
            ]
            hash_val = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
            color = colors[hash_val % len(colors)]

        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO categories (name, parent_id, color, icon) VALUES (%s, %s, %s, %s) RETURNING id',
            (name, parent_id, color, icon)
        )
        result = cursor.fetchone()
        conn.commit()
        return result['id']

    def update_category(self, category_id, name):
        """Update category name"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE categories SET name = %s WHERE id = %s', (name, category_id))
        conn.commit()

    def delete_category(self, category_id):
        """Delete a category and all its descendants recursively.
        Returns (success: bool, message: str) tuple."""
        conn = self.connect()
        cursor = conn.cursor()
        # Check category exists
        cursor.execute('SELECT name FROM categories WHERE id = %s', (category_id,))
        row = cursor.fetchone()
        if not row:
            return False, f'Category #{category_id} not found'
        cat_name = row['name']

        # Collect all descendant IDs recursively
        all_ids = []
        queue = [category_id]
        while queue:
            current = queue.pop()
            all_ids.append(current)
            cursor.execute('SELECT id FROM categories WHERE parent_id = %s', (current,))
            for child in cursor.fetchall():
                queue.append(child['id'])

        # Uncategorize transactions for all affected categories
        cursor.execute('UPDATE transactions SET category_id = NULL WHERE category_id = ANY(%s)', (all_ids,))
        # Delete associated rules
        cursor.execute('DELETE FROM categorization_rules WHERE category_id = ANY(%s)', (all_ids,))
        # Delete all categories (children first due to FK, but ANY handles it)
        cursor.execute('DELETE FROM categories WHERE id = ANY(%s)', (all_ids,))
        conn.commit()

        count = len(all_ids)
        if count == 1:
            return True, f'Deleted category "{cat_name}"'
        return True, f'Deleted category "{cat_name}" and {count - 1} subcategories'

    # ========================
    # Category Summary
    # ========================

    def get_category_summary(self, filters=None):
        """Get spending summary grouped by category.

        Returns a DataFrame with columns:
            category_id, category_name, parent_name, color,
            total_amount, transaction_count
        Filters can contain: start_date, end_date, account, direction, etc.
        """
        filters = filters or {}

        where_clauses = [
            "t.is_transfer = FALSE"
        ]
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
        if filters.get('direction'):
            where_clauses.append('t.direction = %s')
            params.append(filters['direction'])
        else:
            # Default: show expenses (debit)
            where_clauses.append("t.direction = 'debit'")

        where_sql = ' AND '.join(where_clauses)

        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                c.id AS category_id,
                c.name AS category_name,
                p.name AS parent_name,
                c.color,
                COALESCE(SUM(t.amount), 0) AS total_amount,
                COUNT(t.id) AS transaction_count
            FROM categories c
            LEFT JOIN categories p ON c.parent_id = p.id
            LEFT JOIN transactions t ON t.category_id = c.id
                AND {where_sql}
            GROUP BY c.id, c.name, p.name, c.color
            HAVING COUNT(t.id) > 0
            ORDER BY total_amount DESC
        """, params)
        rows = cursor.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ========================
    # Categorization Rules
    # ========================

    def add_categorization_rule(self, pattern, category_id, field='description',
                                priority=0, min_amount=None, max_amount=None,
                                transaction_type=None, counter_account=None):
        """Add an auto-categorization rule"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO categorization_rules
                (pattern, category_id, field, priority, min_amount, max_amount,
                 transaction_type, counter_account)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (pattern, category_id, field, priority,
              min_amount, max_amount, transaction_type, counter_account))
        result = cursor.fetchone()
        conn.commit()
        return result['id']

    def update_categorization_rule(self, rule_id, **kwargs):
        """Update a categorization rule with given keyword arguments"""
        if not kwargs:
            return

        conn = self.connect()
        cursor = conn.cursor()

        set_parts = []
        params = []
        for key, value in kwargs.items():
            set_parts.append(f'{key} = %s')
            params.append(value)

        params.append(rule_id)
        cursor.execute(
            f"UPDATE categorization_rules SET {', '.join(set_parts)} WHERE id = %s",
            params
        )
        conn.commit()

    def get_categorization_rules(self, active_only=True):
        """Get categorization rules, optionally only active ones"""
        conn = self.connect()
        cursor = conn.cursor()

        where = 'WHERE active = TRUE' if active_only else ''
        cursor.execute(f"""
            SELECT r.*, c.name AS category_name, p.name AS parent_category_name
            FROM categorization_rules r
            JOIN categories c ON r.category_id = c.id
            LEFT JOIN categories p ON c.parent_id = p.id
            {where}
            ORDER BY r.priority DESC, r.id
        """)
        rows = cursor.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def delete_categorization_rule(self, rule_id):
        """Delete a categorization rule"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM categorization_rules WHERE id = %s', (rule_id,))
        conn.commit()

    # ========================
    # Auto-categorization
    # ========================

    def auto_categorize_transactions(self):
        """Apply active categorization rules to uncategorized transactions.

        Rules are evaluated in priority order (highest first).
        Returns the number of transactions categorized.
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Fetch active rules ordered by priority
        cursor.execute("""
            SELECT id, pattern, field, category_id, counter_account,
                   transaction_type, min_amount, max_amount
            FROM categorization_rules
            WHERE active = TRUE
            ORDER BY priority DESC, id
        """)
        rules = cursor.fetchall()

        if not rules:
            return 0

        total_categorized = 0

        for rule in rules:
            conditions = ['category_id IS NULL']
            params = []

            if rule['pattern']:
                field = rule.get('field', 'description') or 'description'
                conditions.append(f"LOWER({field}) LIKE %s")
                params.append(f"%{rule['pattern'].lower()}%")

            if rule.get('counter_account'):
                conditions.append('counter_account = %s')
                params.append(rule['counter_account'])

            if rule.get('transaction_type'):
                conditions.append('direction = %s')
                params.append(rule['transaction_type'])

            if rule.get('min_amount') is not None:
                conditions.append('amount >= %s')
                params.append(rule['min_amount'])
            if rule.get('max_amount') is not None:
                conditions.append('amount <= %s')
                params.append(rule['max_amount'])

            where_sql = ' AND '.join(conditions)

            cursor.execute(
                f"UPDATE transactions SET category_id = %s WHERE {where_sql}",
                [rule['category_id']] + params
            )
            total_categorized += cursor.rowcount

        conn.commit()
        return total_categorized

    def get_rule_match_counts(self):
        """Get match counts for each rule: total matches and uncategorized matches.

        Returns dict: { rule_id: {'total': N, 'uncategorized': M} }
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, pattern, field, category_id, counter_account,
                   transaction_type, min_amount, max_amount
            FROM categorization_rules
            WHERE active = TRUE
            ORDER BY id
        """)
        rules = cursor.fetchall()
        counts = {}

        for rule in rules:
            conditions = []
            params = []

            if rule['pattern']:
                field = rule.get('field', 'description') or 'description'
                conditions.append(f"LOWER({field}) LIKE %s")
                params.append(f"%{rule['pattern'].lower()}%")

            if rule.get('counter_account'):
                conditions.append('counter_account = %s')
                params.append(rule['counter_account'])

            if rule.get('transaction_type'):
                conditions.append('direction = %s')
                params.append(rule['transaction_type'])

            if rule.get('min_amount') is not None:
                conditions.append('amount >= %s')
                params.append(rule['min_amount'])
            if rule.get('max_amount') is not None:
                conditions.append('amount <= %s')
                params.append(rule['max_amount'])

            if not conditions:
                counts[rule['id']] = {'total': 0, 'uncategorized': 0}
                continue

            where_sql = ' AND '.join(conditions)

            cursor.execute(
                f"SELECT COUNT(*) as cnt FROM transactions WHERE {where_sql}",
                params
            )
            total = cursor.fetchone()['cnt']

            cursor.execute(
                f"SELECT COUNT(*) as cnt FROM transactions WHERE {where_sql} AND category_id IS NULL",
                params
            )
            uncat = cursor.fetchone()['cnt']

            counts[rule['id']] = {'total': total, 'uncategorized': uncat}

        return counts

    def test_rule(self, **kwargs):
        """Preview which transactions a rule would match.

        Returns dict with 'total', 'uncategorized', and 'sample' (up to 10 rows).
        """
        field = kwargs.get('field', 'description') or 'description'
        pattern = kwargs.get('pattern')
        counter_account = kwargs.get('counter_account')
        transaction_type = kwargs.get('transaction_type')
        min_amount = kwargs.get('min_amount')
        max_amount = kwargs.get('max_amount')

        conditions = []
        params = []

        if pattern:
            conditions.append(f"LOWER({field}) LIKE %s")
            params.append(f"%{pattern.lower()}%")
        if counter_account:
            conditions.append('counter_account = %s')
            params.append(counter_account)
        if transaction_type:
            conditions.append('direction = %s')
            params.append(transaction_type)
        if min_amount is not None:
            conditions.append('amount >= %s')
            params.append(min_amount)
        if max_amount is not None:
            conditions.append('amount <= %s')
            params.append(max_amount)

        if not conditions:
            return {'total': 0, 'uncategorized': 0, 'sample': []}

        where_sql = ' AND '.join(conditions)

        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) as cnt FROM transactions WHERE {where_sql}", params)
        total = cursor.fetchone()['cnt']

        cursor.execute(
            f"SELECT COUNT(*) as cnt FROM transactions WHERE {where_sql} AND category_id IS NULL",
            params
        )
        uncategorized = cursor.fetchone()['cnt']

        cursor.execute(
            f"""SELECT id, date, description, counter_account, direction, amount
                FROM transactions WHERE {where_sql}
                ORDER BY date DESC LIMIT 10""",
            params
        )
        sample = [dict(r) for r in cursor.fetchall()]
        # Convert date objects to strings for JSON serialization
        for row in sample:
            if row.get('date'):
                row['date'] = str(row['date'])
            if row.get('amount') is not None:
                row['amount'] = float(row['amount'])

        return {'total': total, 'uncategorized': uncategorized, 'sample': sample}

    def find_conflicting_rules(self, **kwargs):
        """Find existing rules that overlap with the given criteria.

        Returns a list of conflicting rule dicts.
        """
        field = kwargs.get('field', 'description') or 'description'
        pattern = kwargs.get('pattern')
        counter_account = kwargs.get('counter_account')
        transaction_type = kwargs.get('transaction_type')
        min_amount = kwargs.get('min_amount')
        max_amount = kwargs.get('max_amount')
        exclude_rule_id = kwargs.get('exclude_rule_id')

        conditions = ['active = TRUE']
        params = []

        if pattern:
            conditions.append("LOWER(pattern) LIKE %s AND field = %s")
            params.extend([f"%{pattern.lower()}%", field])
        if counter_account:
            conditions.append('counter_account = %s')
            params.append(counter_account)
        if transaction_type:
            conditions.append('transaction_type = %s')
            params.append(transaction_type)
        if exclude_rule_id:
            conditions.append('id != %s')
            params.append(exclude_rule_id)

        where_sql = ' AND '.join(conditions)
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute(
            f"""SELECT r.*, c.name AS category_name
                FROM categorization_rules r
                JOIN categories c ON r.category_id = c.id
                WHERE {where_sql}
                ORDER BY r.priority DESC""",
            params
        )
        conflicts = []
        for row in cursor.fetchall():
            r = dict(row)
            # Clean for JSON
            for k in ('min_amount', 'max_amount'):
                if r.get(k) is not None:
                    r[k] = float(r[k])
            conflicts.append(r)
        return conflicts

    def reorder_rule_priorities(self, rule_ids_ordered):
        """Reorder rule priorities so that the first ID gets the highest priority"""
        conn = self.connect()
        cursor = conn.cursor()
        total = len(rule_ids_ordered)
        for idx, rule_id in enumerate(rule_ids_ordered):
            priority = total - idx  # first gets highest
            cursor.execute(
                'UPDATE categorization_rules SET priority = %s WHERE id = %s',
                (priority, rule_id)
            )
        conn.commit()
