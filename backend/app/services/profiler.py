"""Deterministic statistics for the dataset."""
from scipy import stats
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

def numeric_stats(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return {}
    q1, q3 = s.quantile([0.25, 0.75])
    return {
        "mean": _f(s.mean()),
        "median": _f(s.median()),
        "std": _f(s.std()),
        "min": _f(s.min()),
        "max": _f(s.max()),
        "q1": _f(q1),
        "q3": _f(q3),
        "skewness": _f(stats.skew(s)) if len(s) > 2 else None,
        "kurtosis": _f(stats.kurtosis(s)) if len(s) > 3 else None,
    }

def categorical_stats(s: pd.Series, top: int = 5) -> dict:
    s = s.dropna()
    if s.empty:
        return {}
    freq = s.value_counts(normalize=True)
    return {
        "unique": int(s.nunique()),
        "top": [{"value": str(k), "pct": _f(v * 100, 2)} for k, v in freq.head(top).items()],
        "rare_categories": int((freq < 0.01).sum()),
    }