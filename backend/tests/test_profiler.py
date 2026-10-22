import pandas as pd
from app.services.profiler import (
    overview, numeric_stats, categorical_stats, iqr_outliers, correlations, datetime_stats,
)

def test_missing_pct():
    df = pd.DataFrame({"a": [1, None, 3, None], "b": [1, 2, 3, 4]})
    ov = overview(df, {"a": "numeric", "b": "numeric"})
    assert ov["missing"] == {"a": {"count": 2, "pct": 50.0}}
    assert ov["total_missing_pct"] == 25.0

# Test for overview function
def test_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    assert overview(df, {})["duplicate_rows"] == 1


def test_constant_column():
    df = pd.DataFrame({"a": [5, 5, 5], "b": [1, 2, 3]})
    assert overview(df, {})["constant_columns"] == ["a"]


def test_empty_dataframe():
    ov = overview(pd.DataFrame(), {})
    assert ov["rows"] == 0 and ov["total_missing_pct"] == 0.0

# Numeric Tests 
def test_numeric_basic():
    r = numeric_stats(pd.Series([1, 2, 3, 4, 5]))
    assert r["mean"] == 3.0 and r["median"] == 3.0
    assert r["q1"] == 2.0 and r["q3"] == 4.0


def test_numeric_right_skew():
    assert numeric_stats(pd.Series([1, 1, 1, 1, 100]))["skewness"] > 0


def test_numeric_all_nan():
    assert numeric_stats(pd.Series([None, None], dtype=float)) == {}


def test_numeric_two_values():
    assert numeric_stats(pd.Series([1.0, 2.0]))["skewness"] is None

# Categorical Tests
def test_categorical_top():
    r = categorical_stats(pd.Series(["a", "a", "a", "b"]))
    assert r["top"][0] == {"value": "a", "pct": 75.0}


def test_categorical_rare():
    s = pd.Series(["a"] * 199 + ["b"])
    assert categorical_stats(s)["rare_categories"] == 1


def test_categorical_all_nan():
    assert categorical_stats(pd.Series([None, None])) == {}


def test_categorical_top_limit():
    s = pd.Series(list("aabbccdd"))
    assert len(categorical_stats(s, top=2)["top"]) == 2


#IQR Outlier Tests and Correlation Tests
def test_outlier_detected():
    assert iqr_outliers(pd.Series([1, 2, 3, 4, 100]))["count"] == 1


def test_no_outliers():
    assert iqr_outliers(pd.Series([1, 2, 3, 4, 5]))["count"] == 0


def test_outliers_tiny_sample():
    assert iqr_outliers(pd.Series([1, 2]))["lower"] is None


def test_correlation_perfect():
    df = pd.DataFrame({"a": range(1, 11), "b": [2 * i for i in range(1, 11)]})
    res = correlations(df, ["a", "b"])
    assert res["pairs"][0]["pearson"] > 0.99


def test_correlation_skips_constant():
    df = pd.DataFrame({"a": range(10), "b": [5] * 10})
    assert correlations(df, ["a", "b"]) == {"pairs": [], "matrix": {}, "skipped_columns": []}


# Datetime Tests
def test_datetime_stats():
    s = pd.to_datetime(pd.Series(["2024-01-01", "2024-01-31", None]))
    d = datetime_stats(s)
    assert d["span_days"] == 30 and d["min"].startswith("2024-01-01")