"""Transfer repository - handles transfer detection, marking, and linking"""
from .connection import ConnectionManager


class TransferRepository(ConnectionManager):
    """Repository for transfer-related operations"""

    def auto_mark_transfer_transactions(self):
        """Automatically mark transactions as transfers based on transfer accounts,
        own-account cross-references, and transfer patterns.

        Returns the number of transactions marked.
        """
        conn = self.connect()
        cursor = conn.cursor()
        total_marked = 0

        # 1. Mark by transfer account (counter_account matches a transfer account)
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND counter_account IN (
                  SELECT account_number FROM accounts WHERE is_transfer = TRUE
              )
        """)
        total_marked += cursor.rowcount

        # 2. Mark by transfer account (own account matches a transfer account)
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND account IN (
                  SELECT account_number FROM accounts WHERE is_transfer = TRUE
              )
        """)
        total_marked += cursor.rowcount

        # 3. Mark where counter_account is one of the user's own accounts
        #    (i.e. counter_account appears in the account column of other transactions)
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND counter_account IN (
                  SELECT DISTINCT account FROM transactions
              )
        """)
        total_marked += cursor.rowcount

        # 4. Mark where counter_account matches a known account name
        #    (handles cases like ING savings where counter_account has the name)
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND counter_account IN (
                  SELECT name FROM accounts WHERE is_transfer = TRUE
              )
        """)
        total_marked += cursor.rowcount

        # 5. Mark where description exactly matches a transfer account name
        #    (handles ING "Oranje Spaarrekening" etc. with empty counter_account)
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND (counter_account IS NULL OR counter_account = '')
              AND description IN (
                  SELECT name FROM accounts WHERE is_transfer = TRUE
              )
        """)
        total_marked += cursor.rowcount

        # 6. Mark checking-side transactions that have a matching pair
        #    on a transfer account (same amount, same/adjacent date, opposite direction)
        cursor.execute("""
            UPDATE transactions t
            SET is_transfer = TRUE
            WHERE t.is_transfer = FALSE
              AND (t.counter_account IS NULL OR t.counter_account = '')
              AND EXISTS (
                  SELECT 1 FROM transactions s
                  WHERE s.is_transfer = TRUE
                    AND s.account IN (SELECT account_number FROM accounts WHERE is_transfer = TRUE)
                    AND s.amount = t.amount
                    AND s.direction != t.direction
                    AND ABS(s.date - t.date) <= 1
              )
        """)
        total_marked += cursor.rowcount

        # 7. Mark by ING giro transfer code 'GT' to/from savings accounts.
        #    Only match GT transactions whose description matches a transfer account name
        #    OR whose notes reference 'spaarrekening' (savings account).
        #    GT is also used for regular online payments, so we can't blanket-mark all GT.
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND LOWER(code) = 'gt'
              AND (
                  description IN (SELECT name FROM accounts WHERE is_transfer = TRUE)
                  OR LOWER(notes) LIKE '%spaarrekening%'
              )
        """)
        total_marked += cursor.rowcount

        # 8. Mark by transfer patterns (merchant description match)
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND LOWER(description) LIKE ANY (
                  SELECT '%' || LOWER(pattern) || '%' FROM transfer_patterns
              )
        """)
        total_marked += cursor.rowcount

        conn.commit()
        return total_marked

    def auto_link_transfer_pairs(self):
        """Find and link matching transfer pairs automatically.

        Pairs are matched by:
        - Opposite direction (debit ↔ credit)
        - Same amount
        - Same date (or within 1 day)
        - account of one = counter_account of the other

        Returns the number of pairs linked.
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            WITH candidates AS (
                SELECT
                    t1.id AS id1,
                    t2.id AS id2
                FROM transactions t1
                JOIN transactions t2 ON t1.id < t2.id
                WHERE t1.is_transfer = TRUE
                  AND t2.is_transfer = TRUE
                  AND t1.linked_transaction_id IS NULL
                  AND t2.linked_transaction_id IS NULL
                  AND t1.amount = t2.amount
                  AND t1.direction != t2.direction
                  AND ABS(t1.date - t2.date) <= 1
                  AND (
                      (t1.account = t2.counter_account AND t1.counter_account = t2.account)
                      OR (t1.account = t2.counter_account)
                      OR (t1.counter_account = t2.account)
                  )
            )
            SELECT * FROM candidates
        """)
        pairs = cursor.fetchall()

        linked = 0
        for pair in pairs:
            cursor.execute(
                'UPDATE transactions SET linked_transaction_id = %s WHERE id = %s AND linked_transaction_id IS NULL',
                (pair['id2'], pair['id1'])
            )
            cursor.execute(
                'UPDATE transactions SET linked_transaction_id = %s WHERE id = %s AND linked_transaction_id IS NULL',
                (pair['id1'], pair['id2'])
            )
            linked += 1

        conn.commit()
        return linked

    def get_linked_transfers(self):
        """Get all pairs of linked transfer transactions"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                t1.id AS id1, t1.date AS date1, t1.description AS desc1,
                t1.account AS account1, t1.direction AS direction1,
                t1.amount AS amount1,
                t2.id AS id2, t2.date AS date2, t2.description AS desc2,
                t2.account AS account2, t2.direction AS direction2,
                t2.amount AS amount2
            FROM transactions t1
            JOIN transactions t2 ON t1.linked_transaction_id = t2.id
            WHERE t1.id < t2.id
            ORDER BY t1.date DESC
        """)
        return [dict(r) for r in cursor.fetchall()]

    def link_transfer_pair(self, transaction_id_1, transaction_id_2):
        """Manually link two transactions as a transfer pair"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE transactions SET linked_transaction_id = %s, is_transfer = TRUE WHERE id = %s',
            (transaction_id_2, transaction_id_1)
        )
        cursor.execute(
            'UPDATE transactions SET linked_transaction_id = %s, is_transfer = TRUE WHERE id = %s',
            (transaction_id_1, transaction_id_2)
        )
        conn.commit()

    def unlink_transfer_pair(self, transaction_id):
        """Remove transfer link from a transaction (and its partner)"""
        conn = self.connect()
        cursor = conn.cursor()
        # Find the partner
        cursor.execute(
            'SELECT linked_transaction_id FROM transactions WHERE id = %s',
            (transaction_id,)
        )
        row = cursor.fetchone()
        if row and row['linked_transaction_id']:
            partner_id = row['linked_transaction_id']
            cursor.execute(
                'UPDATE transactions SET linked_transaction_id = NULL WHERE id = %s',
                (partner_id,)
            )
        cursor.execute(
            'UPDATE transactions SET linked_transaction_id = NULL WHERE id = %s',
            (transaction_id,)
        )
        conn.commit()

    def find_unlinked_transfer_pairs(self):
        """Find potential transfer pairs that haven't been linked yet"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                t1.id AS id1, t1.date AS date1, t1.description AS desc1,
                t1.account AS account1, t1.direction AS direction1,
                t1.amount AS amount1,
                t2.id AS id2, t2.date AS date2, t2.description AS desc2,
                t2.account AS account2, t2.direction AS direction2,
                t2.amount AS amount2
            FROM transactions t1
            JOIN transactions t2 ON t1.id < t2.id
            WHERE t1.is_transfer = TRUE
              AND t2.is_transfer = TRUE
              AND t1.linked_transaction_id IS NULL
              AND t2.linked_transaction_id IS NULL
              AND t1.amount = t2.amount
              AND t1.direction != t2.direction
              AND ABS(t1.date - t2.date) <= 1
            ORDER BY t1.date DESC
            LIMIT 50
        """)
        return [dict(r) for r in cursor.fetchall()]

    def mark_transfer_account_transactions(self, account_number):
        """Mark all transactions involving a specific account as transfers"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND (account = %s OR counter_account = %s)
        """, (account_number, account_number))
        count = cursor.rowcount
        conn.commit()
        return count

    def get_transfer_patterns(self):
        """Get all transfer merchant patterns"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM transfer_patterns ORDER BY pattern')
        return [dict(r) for r in cursor.fetchall()]

    def add_transfer_pattern(self, pattern, name=None):
        """Add a merchant pattern that indicates a transfer"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO transfer_patterns (pattern, name) VALUES (%s, %s) ON CONFLICT (pattern) DO NOTHING RETURNING id',
            (pattern, name)
        )
        result = cursor.fetchone()
        conn.commit()
        return result['id'] if result else None

    def remove_transfer_pattern(self, pattern_id):
        """Remove a transfer pattern"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM transfer_patterns WHERE id = %s', (pattern_id,))
        conn.commit()

    def mark_transfer_pattern_transactions(self, pattern):
        """Mark transactions matching a merchant pattern as transfers"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET is_transfer = TRUE
            WHERE is_transfer = FALSE
              AND LOWER(description) LIKE %s
        """, (f'%{pattern.lower()}%',))
        count = cursor.rowcount
        conn.commit()
        return count

    def mark_as_transfer(self, transaction_id, is_transfer=True):
        """Manually mark a single transaction as a transfer (or unmark)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE transactions SET is_transfer = %s WHERE id = %s',
            (bool(is_transfer), transaction_id)
        )
        conn.commit()

    def link_transfers(self, transaction_id_1, transaction_id_2):
        """Alias for link_transfer_pair"""
        return self.link_transfer_pair(transaction_id_1, transaction_id_2)

    def unlink_transfer(self, transaction_id):
        """Alias for unlink_transfer_pair"""
        return self.unlink_transfer_pair(transaction_id)
