"""ING Betaalrekening (checking account) CSV importer.

Expected CSV columns (semicolon-separated):
  Datum, Naam / Omschrijving, Rekening, Tegenrekening, Code,
  Af Bij, Bedrag (EUR), Mutatiesoort, Mededelingen, Saldo na mutatie, Tag
"""
from .base import BaseImporter


class INGCheckingImporter(BaseImporter):

    id = 'ing_checking'
    name = 'ING - Betaalrekening'
    separator = ';'

    detect_columns = frozenset({'Naam / Omschrijving', 'Code'})

    column_map = {
        'Datum':                'date',
        'Naam / Omschrijving':  'description',
        'Rekening':             'account',
        'Tegenrekening':        'counter_account',
        'Code':                 'code',
        'Af Bij':               'direction',
        'Bedrag (EUR)':         'amount',
        'Mutatiesoort':         'mutation_type',
        'Mededelingen':         'notes',
        'Saldo na mutatie':     'balance_after',
        'Tag':                  'tag',
    }

    def _rename_columns(self, df):
        """Handle the alternate amount column name 'Bedrag' used in some older exports."""
        # Some ING exports use 'Bedrag' instead of 'Bedrag (EUR)'
        if 'Bedrag (EUR)' not in df.columns and 'Bedrag' in df.columns:
            df = df.rename(columns={'Bedrag': 'amount'})
        return super()._rename_columns(df)
