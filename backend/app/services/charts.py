"""Chart data builders. Pure: pandas in, small JSON-safe dicts out. Never raw rows."""
import numpy as np
import pandas as pd

from app.services.profiler import _f

MAX_BINS = 100
MAX_TOP = 50
MAX_POINTS = 2000

# chart type -> for each required column, the allowed column types
SPEC = {
    "histogram": (("numeric",),),
    "boxplot": (("numeric",),),
    "bar": (("categorical", "boolean"),),
    "scatter": (("numeric",), ("numeric",)),
}


def _numeric(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").dropna()
    x = x[np.isfinite(x)]
    if x.empty:
        raise ValueError(f"No numeric values in '{s.name}'")
    return x


def histogram(s: pd.Series, bins: int = 20) -> dict:
    if not 1 <= bins <= MAX_BINS:
        raise ValueError(f"bins must be between 1 and {MAX_BINS}")
    x = _numeric(s)
    counts, edges = np.histogram(x, bins=bins)
    return {
        "type": "histogram",
        "column": str(s.name),
        "n": int(len(x)),
        "bins": [
            {"start": _f(edges[i]), "end": _f(edges[i + 1]), "count": int(counts[i])}
            for i in range(len(counts))
        ],
    }


def boxplot(s: pd.Series) -> dict:
    x = _numeric(s)
    q1, med, q3 = x.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    low_fence, high_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = x[(x >= low_fence) & (x <= high_fence)]
    return {
        "type": "boxplot",
        "column": str(s.name),
        "n": int(len(x)),
        "q1": _f(q1),
        "median": _f(med),
        "q3": _f(q3),
        "whisker_low": _f(inside.min()),
        "whisker_high": _f(inside.max()),
        "min": _f(x.min()),
        "max": _f(x.max()),
        "outlier_count": int(len(x) - len(inside)),
    }


def top_categories(s: pd.Series, n: int = 10) -> dict:
    if not 1 <= n <= MAX_TOP:
        raise ValueError(f"top must be between 1 and {MAX_TOP}")
    counts = s.dropna().astype(str).value_counts()
    if counts.empty:
        raise ValueError(f"No values in '{s.name}'")
    total = int(counts.sum())
    top = counts.head(n)
    return {
        "type": "bar",
        "column": str(s.name),
        "n": total,
        "unique": int(len(counts)),
        "items": [
            {"value": str(v), "count": int(c), "pct": _f(c / total * 100)}
            for v, c in top.items()
        ],
        "other_count": int(total - top.sum()),
    }


def scatter_sample(df: pd.DataFrame, x: str, y: str, max_points: int = MAX_POINTS) -> dict:
    data = df[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
    data = data[np.isfinite(data).all(axis=1)]
    if data.empty:
        raise ValueError("No rows with both values present")
    total = len(data)
    if total > max_points:
        data = data.sample(max_points, random_state=0)  # fixed seed: same chart every time
    return {
        "type": "scatter",
        "x": x,
        "y": y,
        "n_total": int(total),
        "n_shown": int(len(data)),
        "points": [{"x": _f(a), "y": _f(b)} for a, b in zip(data[x], data[y])],
    }


def heatmap(matrix: dict) -> dict:
    """Reshape correlations.matrix from the stored result. No CSV needed."""
    labels = list(matrix)
    return {
        "type": "heatmap",
        "labels": labels,
        "values": [[matrix[a].get(b) for b in labels] for a in labels],
    }


def build_chart(df: pd.DataFrame, types: dict, chart_type: str, columns: list[str],
                bins: int = 20, top: int = 10) -> dict:
    """Validate type/columns/column-types, then build. Raises ValueError (API maps it to 400)."""
    if chart_type not in SPEC:
        raise ValueError(f"Unsupported chart type. Use one of: {', '.join(SPEC)}")
    need = SPEC[chart_type]
    if len(columns) != len(need):
        raise ValueError(f"'{chart_type}' needs {len(need)} column(s)")
    for col, ok in zip(columns, need):
        if col not in df.columns:
            raise ValueError(f"Unknown column '{col}'")
        if types.get(col) not in ok:
            raise ValueError(f"'{col}' is {types.get(col)}, '{chart_type}' needs {'/'.join(ok)}")

    if chart_type == "histogram":
        return histogram(df[columns[0]], bins)
    if chart_type == "boxplot":
        return boxplot(df[columns[0]])
    if chart_type == "bar":
        return top_categories(df[columns[0]], top)
    return scatter_sample(df, columns[0], columns[1])