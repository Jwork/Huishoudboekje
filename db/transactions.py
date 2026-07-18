"""Transaction repository - handles all transaction-related database operations"""
import hashlib
import pandas as pd
from .connection import ConnectionManager


def _safe(val):
    """Return None if val is NaN/NaT/None, otherwise the value itself."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


class TransactionRepository(ConnectionManager):
    """Repository for transaction CRUD operations"""
    
    def import_csv(self, csv_file, progress_callback=None, filename=None, format_id=None,
                   retained_file=None):
        """Import transactions from a CSV file using the importer registry.

        Args:
            csv_file: Path to the CSV file on disk.
            progress_callback: Optional (current, total) callback.
            filename: Original upload filename (for the import_batch record).
            format_id: Importer id (e.g. 'ing_checking'). If None, auto-detect.
            retained_file: Path to the retained copy of the CSV file.

        Uses staging layer:
        1. Creates import_batch record
        2. Inserts raw data into transactions_raw (immutable)
        3. Creates working records in transactions (can be modified)
        """
        from importers import get_importer, detect_format

        # Resolve the importer
        importer = None
        if format_id:
            importer = get_importer(format_id)
        if importer is None:
            importer = detect_format(csv_file)
        if importer is None:
            raise ValueError(
                "Could not detect the CSV format. Please select the correct format from the dropdown."
            )

        # Let the importer parse the CSV into a standardized DataFrame
        df = importer.parse(csv_file)

        conn = self.connect()
        cursor = conn.cursor()

        # If the importer captured account friendly names, store them
        # Also mark as transfer account if the importer says so (e.g. savings importers)
        is_transfer_importer = getattr(importer, 'is_transfer_account', False)
        if hasattr(importer, 'account_names') and importer.account_names:
            for acct_num, acct_name in importer.account_names.items():
                if is_transfer_importer:
                    cursor.execute("""
                        INSERT INTO accounts (account_number, name, is_transfer)
                        VALUES (%s, %s, TRUE)
                        ON CONFLICT (account_number)
                        DO UPDATE SET name = EXCLUDED.name, is_transfer = TRUE
                          WHERE accounts.name = accounts.account_number
                             OR accounts.name IS NULL
                             OR accounts.is_transfer = FALSE
                    """, (acct_num, acct_name))
                else:
                    cursor.execute("""
                        INSERT INTO accounts (account_number, name)
                        VALUES (%s, %s)
                        ON CONFLICT (account_number)
                        DO UPDATE SET name = EXCLUDED.name
                          WHERE accounts.name = accounts.account_number
                             OR accounts.name IS NULL
                    """, (acct_num, acct_name))
        
        first_account = str(df['account'].iloc[0]) if len(df) > 0 and _safe(df['account'].iloc[0]) else None
        
        # Create import batch
        cursor.execute('''
            INSERT INTO import_batches (filename, retained_file, format_id, row_count, account)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (filename, retained_file, format_id or importer.id, len(df), first_account))
        batch_id = cursor.fetchone()['id']
        
        imported = 0
        duplicates = 0
        errors = 0
        
        def calculate_hash(row):
            """Build a hash from the key fields that identify a unique transaction."""
            parts = (
                str(row['date']),
                str(row['account']),
                str(row['amount']),
                str(row['description']),
                str(row.get('counter_account') or ''),
                str(row.get('notes') or ''),
            )
            return hashlib.md5('|'.join(parts).encode()).hexdigest()
        
        if not df.empty:
            df['hash'] = df.apply(calculate_hash, axis=1)
            
            # Only check duplicates for rows whose date overlaps with existing data
            cursor.execute('SELECT MAX(date) FROM transactions_raw')
            row_result = cursor.fetchone()
            max_existing_date = row_result['max'] if row_result else None
            
            if max_existing_date is not None:
                # Split: rows beyond the max existing date can't be duplicates
                overlap_mask = df['date'] <= pd.Timestamp(max_existing_date)
                df_overlap = df[overlap_mask]
                df_new = df[~overlap_mask]
                
                if not df_overlap.empty:
                    min_date = df_overlap['date'].min()
                    cursor.execute(
                        'SELECT hash FROM transactions_raw WHERE date >= %s AND date <= %s',
                        (min_date.strftime('%Y-%m-%d'), max_existing_date)
                    )
                    existing_hashes = set(r['hash'] for r in cursor.fetchall())
                    df_overlap_clean = df_overlap[~df_overlap['hash'].isin(existing_hashes)]
                    duplicates = len(df_overlap) - len(df_overlap_clean)
                    df_to_import = pd.concat([df_overlap_clean, df_new], ignore_index=True)
                else:
                    df_to_import = df_new
            else:
                # Empty database — nothing to check
                df_to_import = df
        else:
            df_to_import = df
        
        # Track hashes from this batch to detect duplicates within the import
        batch_hashes = set()
        
        for idx, row in df_to_import.iterrows():
            try:
                description = _safe(row['description'])
                amount = row['amount']
                direction = _safe(row['direction'])
                hash_val = row['hash']
                
                # Check for duplicates within this batch
                if hash_val in batch_hashes:
                    duplicates += 1
                    continue
                
                batch_hashes.add(hash_val)
                
                # Create a savepoint for this row so errors don't abort the whole transaction
                savepoint = f"sp_{idx}"
                cursor.execute(f"SAVEPOINT {savepoint}")
                
                date_str = row['date'].strftime('%Y-%m-%d')
                
                try:
                    # Insert into RAW table
                    cursor.execute('''
                        INSERT INTO transactions_raw (
                            import_batch_id, date, description, account, counter_account,
                            code, direction, amount, mutation_type, notes, balance_after, hash
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    ''', (
                        batch_id,
                        date_str,
                        description,
                        _safe(row['account']),
                        _safe(row['counter_account']),
                        _safe(row['code']),
                        direction,
                        amount,
                        _safe(row['mutation_type']),
                        _safe(row['notes']),
                        _safe(row['balance_after']),
                        hash_val
                    ))
                    raw_id = cursor.fetchone()['id']
                    
                    # Insert into WORKING table
                    cursor.execute('''
                        INSERT INTO transactions (
                            raw_id, date, description, account, counter_account, code, direction,
                            amount, mutation_type, notes, balance_after, tag, hash, original_direction, is_transfer
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                    ''', (
                        raw_id,
                        date_str,
                        description,
                        _safe(row['account']),
                        _safe(row['counter_account']),
                        _safe(row['code']),
                        direction,
                        amount,
                        _safe(row['mutation_type']),
                        _safe(row['notes']),
                        _safe(row['balance_after']),
                        _safe(row['tag']),
                        hash_val,
                        direction
                    ))
                    imported += 1
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                    
                except Exception as row_error:
                    # Rollback just this row's changes
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    print(f"Error importing row {idx}: {row_error}")
                    errors += 1
                
                if progress_callback and idx % 100 == 0:
                    progress_callback(idx, len(df))
                    
            except Exception as e:
                print(f"Error importing row {idx}: {e}")
                errors += 1
        
        conn.commit()
        self.close()
        
        return imported, duplicates, errors
    
    # Allowed sort columns to prevent SQL injection
    SORT_COLUMNS = {
        'date': 't.date',
        'merchant': 't.description',
        'description': 't.notes',
        'amount': 'ABS(t.amount)',
        'type': 't.direction',
        'category': 'c.name',
        'counter_account': 't.counter_account',
    }

    def _apply_filters(self, query, params, filters):
        """Apply filter clauses to a query. Shared by get_transactions and get_transaction_count."""
        if not filters:
            return query, params

        if 'account' in filters and filters['account']:
            query += ' AND t.account = %s'
            params.append(filters['account'])

        if 'start_date' in filters and filters['start_date']:
            query += ' AND t.date >= %s'
            params.append(filters['start_date'])

        if 'end_date' in filters and filters['end_date']:
            query += ' AND t.date <= %s'
            params.append(filters['end_date'])

        if 'category_id' in filters and filters['category_id']:
            query += ' AND t.category_id = %s'
            params.append(int(filters['category_id']))

        if 'type' in filters and filters['type']:
            query += ' AND t.direction = %s'
            params.append(filters['type'])

        if 'uncategorized' in filters and filters['uncategorized']:
            query += " AND (t.category_id IS NULL OR c.name = 'Uncategorized')"

        if 'search' in filters and filters['search']:
            query += ' AND (t.description ILIKE %s OR t.notes ILIKE %s OR c.name ILIKE %s OR t.counter_account ILIKE %s OR CAST(t.amount AS TEXT) ILIKE %s)'
            search_term = f"%{filters['search']}%"
            params.extend([search_term, search_term, search_term, search_term, search_term])

        if 'merchant' in filters and filters['merchant']:
            query += ' AND t.description = %s'
            params.append(filters['merchant'])

        if 'min_amount' in filters and filters['min_amount'] is not None and filters['min_amount'] != '':
            query += ' AND ABS(t.amount) >= %s'
            params.append(float(filters['min_amount']))

        if 'max_amount' in filters and filters['max_amount'] is not None and filters['max_amount'] != '':
            query += ' AND ABS(t.amount) <= %s'
            params.append(float(filters['max_amount']))

        if 'is_transfer' in filters and filters['is_transfer'] is not None and filters['is_transfer'] != '':
            query += ' AND t.is_transfer = %s'
            params.append(bool(int(filters['is_transfer'])))

        if 'is_incidental' in filters and filters['is_incidental'] is not None and filters['is_incidental'] != '':
            query += ' AND t.is_incidental = %s'
            params.append(bool(int(filters['is_incidental'])))

        return query, params

    def get_transactions(self, filters=None, page=1, per_page=None, sort_by=None, sort_dir=None):
        """Get transactions with optional filters, sorting, and pagination"""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = '''
            SELECT t.*,
                   c.name as category_name,
                   c.color as category_color,
                   COALESCE(t.original_direction, r.direction) as original_direction_val
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN transactions_raw r ON t.raw_id = r.id
            WHERE 1=1
        '''
        params = []

        query, params = self._apply_filters(query, params, filters)

        if filters and 'limit' in filters and filters['limit']:
            query += ' ORDER BY t.date DESC LIMIT %s'
            params.append(filters['limit'])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            self.close()
            return pd.DataFrame([dict(row) for row in rows])

        # Server-side sorting
        sort_column = self.SORT_COLUMNS.get(sort_by, 't.date')
        direction = 'ASC' if sort_dir == 'asc' else 'DESC'
        query += f' ORDER BY {sort_column} {direction}, t.id DESC'
        
        if per_page and per_page > 0:
            offset = (page - 1) * per_page
            query += ' LIMIT %s OFFSET %s'
            params.extend([per_page, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        self.close()
        
        return pd.DataFrame([dict(row) for row in rows])

    def get_transaction_count(self, filters=None):
        """Get total number of transactions matching filters"""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = '''
            SELECT COUNT(*) as count
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE 1=1
        '''
        params = []

        query, params = self._apply_filters(query, params, filters)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        self.close()
        
        return result['count']

    
    def get_transaction(self, transaction_id):
        """Get a single transaction by ID"""
        return self.fetchone(
            'SELECT * FROM transactions WHERE id = %s',
            (transaction_id,)
        )
    
    def get_transaction_description(self, transaction_id):
        """Get just the description for a transaction"""
        result = self.fetchone(
            'SELECT description FROM transactions WHERE id = %s',
            (transaction_id,)
        )
        return result['description'] if result else None
    
    def update_transaction_category(self, transaction_id, category_id):
        """Update transaction category"""
        self.execute_commit(
            'UPDATE transactions SET category_id = %s WHERE id = %s',
            (category_id, transaction_id)
        )
    
    def bulk_update_category(self, transaction_ids, category_id):
        """Update category for multiple transactions"""
        conn = self.connect()
        cursor = conn.cursor()
        count = 0
        for trans_id in transaction_ids:
            cursor.execute(
                'UPDATE transactions SET category_id = %s WHERE id = %s',
                (category_id, trans_id)
            )
            count += cursor.rowcount
        conn.commit()
        self.close()
        return count
    
    def update_transaction_notes(self, transaction_id, notes):
        """Update transaction notes"""
        self.execute_commit(
            'UPDATE transactions SET notes = %s WHERE id = %s',
            (notes, transaction_id)
        )
    
    def update_transaction_type(self, transaction_id, direction):
        """Update transaction direction (debit/credit)"""
        self.execute_commit(
            'UPDATE transactions SET direction = %s WHERE id = %s',
            (direction, transaction_id)
        )
    
    def update_transaction_transfer_status(self, transaction_id, is_transfer):
        """Update transaction transfer status"""
        self.execute_commit(
            'UPDATE transactions SET is_transfer = %s WHERE id = %s',
            (bool(is_transfer), transaction_id)
        )

    def update_transaction_incidental_status(self, transaction_id, is_incidental):
        """Update transaction incidental status"""
        self.execute_commit(
            'UPDATE transactions SET is_incidental = %s WHERE id = %s',
            (bool(is_incidental), transaction_id)
        )
    
    def get_transaction_by_id(self, transaction_id):
        """Get a single transaction by ID"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM transactions WHERE id = %s', (transaction_id,))
        row = cursor.fetchone()
        self.close()
        
        if row:
            return dict(row)
        return None
    
    def search_transactions(self, search_term, filters=None):
        """Full-text search on transactions"""
        conn = self.connect()
        
        query = '''
            SELECT t.*, c.name as category_name, c.color as category_color
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE (t.description ILIKE %s OR t.notes ILIKE %s OR t.account ILIKE %s)
        '''
        search_pattern = f'%{search_term}%'
        params = [search_pattern, search_pattern, search_pattern]
        
        if filters:
            if 'account' in filters and filters['account']:
                query += ' AND t.account = %s'
                params.append(filters['account'])
            
            if 'start_date' in filters and filters['start_date']:
                query += ' AND t.date >= %s'
                params.append(filters['start_date'])
            
            if 'end_date' in filters and filters['end_date']:
                query += ' AND t.date <= %s'
                params.append(filters['end_date'])
        
        query += ' ORDER BY t.date DESC'
        
        df = pd.read_sql_query(query, conn, params=params)
        self.close()
        return df
    
    def get_unique_merchants(self, filters=None):
        """Get unique merchant names with transaction counts"""
        conn = self.connect()
        
        where_clauses = ["t.description IS NOT NULL AND t.description != ''"]
        params = []
        
        if filters and 'account' in filters and filters['account']:
            where_clauses.append('t.account = %s')
            params.append(filters['account'])
        
        query = f'''
            SELECT t.description, COUNT(*) as count,
                   SUM(CASE WHEN t.category_id IS NULL OR c.name = 'Uncategorized' THEN 1 ELSE 0 END) as uncategorized
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE {' AND '.join(where_clauses)}
            GROUP BY t.description
            ORDER BY uncategorized DESC, count DESC
            LIMIT 100
        '''
        
        cursor = self.execute(query, params)
        rows = cursor.fetchall()
        self.close()
        
        merchants = []
        for row in rows:
            merchants.append({
                'name': row['description'],
                'count': row['count'],
                'uncategorized': row['uncategorized']
            })
        return merchants
    
    def get_unique_counter_accounts(self):
        """Get unique counter accounts (IBANs) with their most-used description/name.
        Includes both counter_account values and the user's own accounts."""
        rows = self.fetchall('''
            WITH all_accounts AS (
                SELECT counter_account AS iban, description, COUNT(*) AS cnt
                FROM transactions
                WHERE counter_account IS NOT NULL AND counter_account != ''
                GROUP BY counter_account, description
                UNION ALL
                SELECT account AS iban, account AS description, COUNT(*) AS cnt
                FROM transactions
                WHERE account IS NOT NULL AND account != ''
                GROUP BY account
            ),
            ranked AS (
                SELECT iban, description, cnt,
                       ROW_NUMBER() OVER (PARTITION BY iban ORDER BY cnt DESC) AS rn
                FROM all_accounts
            )
            SELECT r.iban,
                   COALESCE(a.name, r.description, r.iban) AS name,
                   (SELECT COUNT(*) FROM transactions t
                    WHERE t.counter_account = r.iban OR t.account = r.iban) AS total_count
            FROM ranked r
            LEFT JOIN accounts a ON a.account_number = r.iban
            WHERE r.rn = 1
            ORDER BY total_count DESC
        ''')
        
        result = []
        for row in rows:
            result.append({
                'iban': row['iban'],
                'name': row['name'] or row['iban'],
                'count': row['total_count']
            })
        return result
    
    def bulk_categorize_by_merchant(self, merchant, category_id):
        """Categorize all transactions from a specific merchant"""
        return self.execute_commit(
            'UPDATE transactions SET category_id = %s WHERE description = %s',
            (category_id, merchant)
        )
    
    def get_import_batches(self):
        """Get list of all import batches with date range from their transactions"""
        rows = self.fetchall('''
            SELECT b.id, b.filename, b.retained_file, b.format_id,
                   b.imported_at, b.row_count, b.account,
                   MIN(t.date) AS min_date,
                   MAX(t.date) AS max_date,
                   COUNT(t.id) AS transaction_count
            FROM import_batches b
            LEFT JOIN transactions_raw tr ON tr.import_batch_id = b.id
            LEFT JOIN transactions t ON t.raw_id = tr.id
            GROUP BY b.id, b.filename, b.retained_file, b.format_id,
                     b.imported_at, b.row_count, b.account
            ORDER BY b.imported_at DESC
        ''')
        return [dict(row) for row in rows]
    
    def delete_transactions(self, transaction_ids):
        """Delete multiple transactions by ID"""
        if not transaction_ids:
            return 0
        
        conn = self.connect()
        cursor = conn.cursor()
        
        count = 0
        for trans_id in transaction_ids:
            cursor.execute('DELETE FROM transactions WHERE id = %s', (trans_id,))
            count += cursor.rowcount
        
        conn.commit()
        self.close()
        return count
    
    def get_uncategorized_transactions(self, limit=None):
        """Get transactions without a category"""
        conn = self.connect()
        
        query = '''
            SELECT t.*, c.name as category_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.category_id IS NULL OR c.name = 'Uncategorized'
            ORDER BY t.date DESC
        '''
        params = []
        
        if limit:
            query += ' LIMIT %s'
            params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        self.close()
        return df
    
    def save_filter(self, name, filter_config):
        """Save a filter configuration"""
        import json
        
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO saved_filters (name, filter_json)
            VALUES (%s, %s) RETURNING id
        ''', (name, json.dumps(filter_config)))
        
        filter_id = cursor.fetchone()['id']
        conn.commit()
        self.close()
        return filter_id
    
    def get_saved_filters(self):
        """Get all saved filters"""
        import json
        
        rows = self.fetchall('SELECT * FROM saved_filters ORDER BY name')
        filters = []
        for row in rows:
            f = dict(row)
            f['config'] = json.loads(f['filter_json']) if f['filter_json'] else {}
            filters.append(f)
        return filters
    
    def delete_saved_filter(self, filter_id):
        """Delete a saved filter"""
        self.execute_commit('DELETE FROM saved_filters WHERE id = %s', (filter_id,))

    def rebuild_from_files(self):
        """Rebuild all transaction data from retained CSV files.
        
        Truncates transactions and transactions_raw, then re-imports
        all files tracked in import_batches that have a retained_file.
        Categories, rules, budgets etc. are preserved.
        
        Returns dict with summary of results.
        """
        import os
        from importers import get_importer, detect_format
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # Get all batches with retained files
        cursor.execute('''
            SELECT id, filename, retained_file, format_id
            FROM import_batches
            WHERE retained_file IS NOT NULL
            ORDER BY imported_at ASC
        ''')
        batches = cursor.fetchall()
        
        if not batches:
            self.close()
            return {'success': False, 'message': 'No retained CSV files found in import history.'}
        
        # Verify all files exist before truncating
        missing = []
        for batch in batches:
            if not os.path.exists(batch['retained_file']):
                missing.append(batch['retained_file'])
        
        if missing:
            self.close()
            return {
                'success': False,
                'message': f'Missing {len(missing)} file(s): {", ".join(missing[:5])}'
            }
        
        # Clear transaction data (preserve categories, rules, accounts, etc.)
        cursor.execute('DELETE FROM transactions')
        cursor.execute('DELETE FROM transactions_raw')
        cursor.execute('DELETE FROM import_batches')
        conn.commit()
        self.close()
        
        # Re-import each file
        total_imported = 0
        total_duplicates = 0
        total_errors = 0
        files_processed = 0
        
        for batch in batches:
            try:
                imported, duplicates, errors = self.import_csv(
                    batch['retained_file'],
                    filename=batch['filename'],
                    format_id=batch['format_id'],
                    retained_file=batch['retained_file']
                )
                total_imported += imported
                total_duplicates += duplicates
                total_errors += errors
                files_processed += 1
            except Exception as e:
                print(f"Error re-importing {batch['retained_file']}: {e}")
                total_errors += 1
        
        return {
            'success': True,
            'files_processed': files_processed,
            'imported': total_imported,
            'duplicates': total_duplicates,
            'errors': total_errors,
            'message': f'Rebuilt from {files_processed} files: {total_imported} imported, {total_duplicates} duplicates, {total_errors} errors'
        }
