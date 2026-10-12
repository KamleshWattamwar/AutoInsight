"""Deterministic statistics for the dataset."""
import numpy as np
import pandas as pd


def _f(x, nd=4):
    """Convert to a plain rounded float; None for NaN/inf/non-numeric."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if np.isfinite(x) else None


def overview(df: pd.DataFrame, types: dict) -> dict:
    n = len(df)
    missing = df.isna().sum()
    return {
        "rows": n,
        "columns": df.shape[1],
        "duplicate_rows": int(df.duplicated().sum()),
        "total_missing_pct": _f(missing.sum() / df.size * 100, 2) if df.size else 0.0,
        "missing": {
            c: {"count": int(missing[c]), "pct": _f(missing[c] / n * 100, 2)}
            for c in df.columns if missing[c] > 0
        },
        "constant_columns": [c for c in df.columns if df[c].nunique(dropna=True) <= 1],
        "column_types": types,
    }