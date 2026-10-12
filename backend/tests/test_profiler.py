import pandas as pd
from app.services.profiler import overview


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