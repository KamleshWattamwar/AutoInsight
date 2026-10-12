"""Deterministic statistics for the dataset."""
from scipy import stats
import numpy as np
import pandas as pd
MAX_CORR_COLS = 30


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

def iqr_outliers(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) < 4:
        return {"count": 0, "pct": 0.0, "lower": None, "upper": None}
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    count = int(((s < lower) | (s > upper)).sum())
    return {"count": count, "pct": _f(count / len(s) * 100, 2),
            "lower": _f(lower), "upper": _f(upper)}


def correlations(df: pd.DataFrame, numeric_cols: list, min_abs: float = 0.3) -> dict:
    cols = [c for c in numeric_cols if df[c].nunique() > 1][:MAX_CORR_COLS]
    if len(cols) < 2:
        return {"pairs": [], "matrix": {}}

    matrix = df[cols].corr(method="pearson")
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            both = df[[a, b]].dropna()
            if len(both) < 3:
                continue
            r, p = stats.pearsonr(both[a], both[b])
            rho, _ = stats.spearmanr(both[a], both[b])
            if abs(r) >= min_abs or abs(rho) >= min_abs:
                pairs.append({"a": a, "b": b, "pearson": _f(r), "spearman": _f(rho),
                              "p_value": _f(p, 6), "n": len(both)})
    pairs.sort(key=lambda d: -abs(d["pearson"] or 0))
    return {
        "pairs": pairs,
        "matrix": {a: {b: _f(matrix.loc[a, b], 3) for b in cols} for a in cols},
    }