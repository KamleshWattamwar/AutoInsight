"""Runs the full deterministic analysis: CSV -> structured dict."""
from .findings import detect, quality_score
from .loader import infer_types, load_csv
from .profiler import (categorical_stats, correlations, iqr_outliers,
                       numeric_stats, overview)


def analyze_df(df) -> dict:
    df, types = infer_types(df)
    ov = overview(df, types)

    columns = {}
    for col, kind in types.items():
        info = {"type": kind}
        if kind == "numeric":
            info["stats"] = numeric_stats(df[col])
            info["outliers"] = iqr_outliers(df[col])
        elif kind in ("categorical", "boolean"):
            info["stats"] = categorical_stats(df[col])
        elif kind == "text":
            info["unique"] = int(df[col].nunique())
        columns[col] = info

    numeric_cols = [c for c, k in types.items() if k == "numeric"]
    corr = correlations(df, numeric_cols)

    return {
        "overview": ov,
        "columns": columns,
        "correlations": corr,
        "findings": detect(ov, columns, corr),
        "quality_score": quality_score(ov, columns),
    }


def analyze_csv(path: str) -> dict:
    return analyze_df(load_csv(path))