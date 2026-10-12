import pandas as pd
from app.services.profiler import overview
from app.services.profiler import overview, numeric_stats

def test_missing_pct():
    df = pd.DataFrame({"a": [1, None, 3, None], "b": [1, 2, 3, 4]})
    ov = overview(df, {"a": "numeric", "b": "numeric"})
    assert ov["missing"] == {"a": {"count": 2, "pct": 50.0}}
    assert ov["total_missing_pct"] == 25.0


def test_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    assert overview(df, {})["duplicate_rows"] == 1


def test_constant_column():
    df = pd.DataFrame({"a": [5, 5, 5], "b": [1, 2, 3]})
    assert overview(df, {})["constant_columns"] == ["a"]


def test_empty_dataframe():
    ov = overview(pd.DataFrame(), {})
    assert ov["rows"] == 0 and ov["total_missing_pct"] == 0.0


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