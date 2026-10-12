import json

import pandas as pd

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
    assert set(res) == {"overview", "columns", "correlations", "findings", "quality_score"}


def test_identifier_not_in_correlations():
    res = analyze_df(_sample())
    names = {p["a"] for p in res["correlations"]["pairs"]} | {p["b"] for p in res["correlations"]["pairs"]}
    assert "id" not in names


def test_json_safe():
    json.dumps(analyze_df(_sample()))