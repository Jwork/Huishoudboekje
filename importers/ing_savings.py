"""ING Spaarrekening (savings account) CSV importer.

Expected CSV columns (semicolon-separated):
  Datum, Omschrijving, Rekening, Rekening naam, Af Bij, Bedrag,
  Saldo na mutatie
  
Savings CSVs may lack: Code, Tegenrekening, Mutatiesoort, Mededelingen, Tag
"""
from .base import BaseImporter


class INGSavingsImporter(BaseImporter):

    id = 'ing_savings'
    name = 'ING - Spaarrekening'
    separator = ';'
    is_transfer_account = True

    detect_columns = frozenset({'Omschrijving', 'Rekening naam'})

    column_map = {
        'Datum':            'date',
        'Omschrijving':     'description',
        'Rekening':         'account',
        'Tegenrekening':    'counter_account',
        'Af Bij':           'direction',
        'Bedrag':           'amount',
        'Mutatiesoort':     'mutation_type',
        'Mededelingen':     'notes',
        'Saldo na mutatie': 'balance_after',
        'Tag':              'tag',
    }

    def parse(self, csv_path):
        """Parse CSV and store the account friendly name from 'Rekening naam'."""
        raw = self._read_csv(csv_path)
        # Capture 'Rekening naam' before we rename columns – this is the
        # account friendly name (e.g. "Oranje Spaarrekening").
        self.account_names = {}
        if 'Rekening naam' in raw.columns and 'Rekening' in raw.columns:
            for _, row in raw[['Rekening', 'Rekening naam']].drop_duplicates().iterrows():
                acct = str(row['Rekening']).strip()
                name = str(row['Rekening naam']).strip()
                if acct and name:
                    self.account_names[acct] = name

        df = self._rename_columns(raw)
        df = self._parse_dates(df)
        df = self._clean_amounts(df)
        df = self._normalize_direction(df)
        df = self._fill_missing(df)
        return df
