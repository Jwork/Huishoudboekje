"""Base importer class - defines the contract all format importers must follow.

To add a new bank format:
1. Create a new file in importers/ (e.g. importers/rabobank.py)
2. Subclass BaseImporter
3. Set id, name, separator, encoding, detect_columns, column_map
4. Override parse() only if the format needs special handling beyond column mapping
5. Register in importers/__init__.py by importing the class

The standardized DataFrame returned by parse() must have these columns:
  date, description, account, counter_account, code, direction,
  amount, mutation_type, notes, balance_after, tag
"""
import abc
import pandas as pd


class BaseImporter(abc.ABC):
    """Abstract base class for CSV format importers."""

    # --- Subclasses MUST set these ---

    @property
    @abc.abstractmethod
    def id(self) -> str:
        """Unique identifier, e.g. 'ing_checking'."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable label shown in the UI dropdown, e.g. 'ING - Betaalrekening'."""

    @property
    @abc.abstractmethod
    def detect_columns(self) -> frozenset:
        """Set of CSV column names that uniquely identify this format.
        Used by auto-detect: if all of these columns are present the format matches."""

    @property
    @abc.abstractmethod
    def column_map(self) -> dict:
        """Mapping from CSV column name → standardized column name.
        Only include columns that exist in this format.
        Standard names: date, description, account, counter_account, code,
                        direction, amount, mutation_type, notes, balance_after, tag
        """

    # --- Defaults (override if needed) ---

    separator: str = ';'
    encoding: str = 'utf-8'

    # --- Public API ---

    def parse(self, csv_path: str) -> pd.DataFrame:
        """Read the CSV and return a DataFrame with standardized column names.

        The default implementation handles: reading, column renaming, date parsing,
        amount cleaning, direction normalization and missing-column fill.
        """
        df = self._read_csv(csv_path)
        df = self._rename_columns(df)
        df = self._parse_dates(df)
        df = self._clean_amounts(df)
        df = self._normalize_direction(df)
        df = self._fill_missing(df)
        return df

    # --- Helpers (reusable by subclasses) ---

    def _read_csv(self, csv_path: str) -> pd.DataFrame:
        return pd.read_csv(csv_path, sep=self.separator, encoding=self.encoding)

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename CSV-specific columns to standardized names using column_map."""
        rename = {}
        for csv_col, std_col in self.column_map.items():
            if csv_col in df.columns:
                rename[csv_col] = std_col
        df = df.rename(columns=rename)
        return df

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Auto-detect date format and convert to datetime.
        
        Handles dates stored as int (20260208), float (20260208.0), or string.
        """
        if 'date' not in df.columns:
            return df
        # Coerce to string first — handles int/float columns safely
        date_str = df['date'].astype(str).str.split('.').str[0]  # '20260208.0' → '20260208'
        sample = date_str.iloc[0]
        fmt = '%Y-%m-%d' if '-' in sample else '%Y%m%d'
        df['date'] = pd.to_datetime(date_str, format=fmt)
        return df

    def _clean_amounts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert comma-decimal strings to float for amount and balance_after."""
        for col in ('amount', 'balance_after'):
            if col not in df.columns:
                continue
            # pandas 3.x uses StringDtype instead of object for strings
            if pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].str.replace(',', '.').astype(float)
        return df

    def _fill_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all standard columns exist, filling with None where absent."""
        standard_cols = [
            'date', 'description', 'account', 'counter_account', 'code',
            'direction', 'amount', 'mutation_type', 'notes', 'balance_after', 'tag',
        ]
        for col in standard_cols:
            if col not in df.columns:
                df[col] = None
        return df

    # Direction value mapping — Dutch/English variants → canonical English
    _DIRECTION_MAP = {
        'af': 'debit',
        'bij': 'credit',
        'debit': 'debit',
        'credit': 'credit',
    }

    def _normalize_direction(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize direction column to canonical 'debit'/'credit' values.

        Handles Dutch (Af/Bij) and English (Debit/Credit) input.
        """
        if 'direction' not in df.columns:
            return df
        df['direction'] = (
            df['direction']
            .astype(str)
            .str.strip()
            .str.lower()
            .map(self._DIRECTION_MAP)
            .fillna('debit')
        )
        return df
