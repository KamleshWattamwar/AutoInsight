import json

import pandas as pd
import numpy as np

from app.services.analyzer import analyze_df


def _sample():
    n = 50
    return pd.DataFrame({
        "id": range(1, n + 1),
        "a": range(n),
        "b": [i * 2 + 1 for i in range(n)],
        "cat": ["x", "y"] * (n // 2),
    })


def test_result_keys():
    res = analyze_df(_sample())
    assert set(res) == {"overview", "columns", "correlations", "findings", "quality_score", "warnings"}


def test_identifier_not_in_correlations():
    res = analyze_df(_sample())
    names = {p["a"] for p in res["correlations"]["pairs"]} | {p["b"] for p in res["correlations"]["pairs"]}
    assert "id" not in names


def test_json_safe():
    json.dumps(analyze_df(_sample()))


def _numeric_df(n_cols):
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        rng.normal(size=(50, n_cols)), columns=[f"c{i}" for i in range(n_cols)]
    )


def test_warns_when_correlation_columns_are_capped():
    res = analyze_df(_numeric_df(35))
    assert len(res["warnings"]) == 1
    assert len(res["correlations"]["skipped_columns"]) == 5


def test_no_warning_below_cap():
    res = analyze_df(_numeric_df(5))
    assert res["warnings"] == []
    assert res["correlations"]["skipped_columns"] == []


def test_datetime_column_gets_a_summary():
    df = pd.DataFrame({"d": pd.date_range("2024-01-01", periods=40).astype(str)})
    res = analyze_df(df)
    assert res["columns"]["d"]["stats"]["span_days"] == 39
    json.dumps(res)


def test_string_ids_do_not_trigger_high_cardinality():
    df = pd.DataFrame({"id": [f"EMP{i:04d}" for i in range(100)], "x": range(100)})
    res = analyze_df(df)
    assert res["columns"]["id"] == {"type": "identifier"}
    assert all(f["type"] != "high_cardinality" for f in res["findings"])