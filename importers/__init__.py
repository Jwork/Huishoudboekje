"""Importer registry — auto-discovery and format detection.

Usage:
    from importers import get_all_importers, get_importer, detect_format

    # Populate the UI dropdown
    formats = get_all_importers()          # [{'id': 'ing_checking', 'name': 'ING - Betaalrekening'}, ...]

    # Get a specific importer
    imp = get_importer('ing_checking')     # INGCheckingImporter instance

    # Auto-detect from a CSV file
    imp = detect_format('/path/to/file.csv')  # returns importer instance or None
"""
import pandas as pd
from .base import BaseImporter

# --- Register importers here (import triggers class registration) ---
from .ing_checking import INGCheckingImporter
from .ing_checking_en import INGCheckingENImporter
from .ing_savings import INGSavingsImporter

# Registry: id → importer instance (singleton per format)
_REGISTRY: dict[str, BaseImporter] = {}


def _register(cls: type[BaseImporter]):
    inst = cls()
    _REGISTRY[inst.id] = inst


# Auto-register all imported importer classes
_register(INGCheckingENImporter)   # New English format (most common now)
_register(INGCheckingImporter)     # Old Dutch format
_register(INGSavingsImporter)


# --- Public helpers ---

def get_all_importers() -> list[dict]:
    """Return list of {id, name} for all registered importers (for UI dropdown)."""
    return [{'id': imp.id, 'name': imp.name} for imp in _REGISTRY.values()]


def get_importer(format_id: str) -> BaseImporter | None:
    """Get an importer instance by its id, or None if not found."""
    return _REGISTRY.get(format_id)


def detect_format(csv_path: str) -> BaseImporter | None:
    """Read only the header row of a CSV and match against registered importers.

    Returns the first matching importer instance, or None if no match.
    Tries each importer's detect_columns — the one whose required columns
    are all present in the CSV header wins.
    """
    # Try common separators to read the header
    for sep in (';', ',', '\t'):
        try:
            df = pd.read_csv(csv_path, sep=sep, nrows=0)
            columns = set(df.columns)
            if len(columns) > 1:  # found the right separator
                break
        except Exception:
            continue
    else:
        return None

    for imp in _REGISTRY.values():
        if imp.detect_columns.issubset(columns):
            return imp

    return None
