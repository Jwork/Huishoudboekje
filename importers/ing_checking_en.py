"""ING Betaalrekening — English CSV export (semicolon-separated, with extra fields).

This is the newer ING export format with English column headers.
Download description: "CSV format with semicolon as separator and the extra fields
'Balance after transaction' and 'Tag'."

Expected CSV columns (semicolon-separated, values may be quoted):
  Date, Name / Description, Account, Counterparty, Code,
  Debit/credit, Amount (EUR), Transaction type, Notifications,
  Resulting balance, Tag

Direction values: "Debit" / "Credit" — normalized to "debit" / "credit"
by the base class _normalize_direction() method.
"""
from .base import BaseImporter


class INGCheckingENImporter(BaseImporter):

    id = 'ing_checking_en'
    name = 'ING - Betaalrekening (EN/nieuw)'
    separator = ';'

    detect_columns = frozenset({'Name / Description', 'Debit/credit', 'Resulting balance'})

    column_map = {
        'Date':                 'date',
        'Name / Description':   'description',
        'Account':              'account',
        'Counterparty':         'counter_account',
        'Code':                 'code',
        'Debit/credit':         'direction',
        'Amount (EUR)':         'amount',
        'Transaction type':     'mutation_type',
        'Notifications':        'notes',
        'Resulting balance':    'balance_after',
        'Tag':                  'tag',
    }

    def _rename_columns(self, df):
        """Handle alternate amount column name and rename."""
        if 'Amount (EUR)' not in df.columns and 'Amount' in df.columns:
            df = df.rename(columns={'Amount': 'amount'})
        return super()._rename_columns(df)
