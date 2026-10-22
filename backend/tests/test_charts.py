import json

import pandas as pd
import pytest

from app.services import charts

from app.services.profiler import iqr_outliers

def test_histogram_counts_add_up():
    h = charts.histogram(pd.Series(range(100), name="a"), bins=10)
    assert len(h["bins"]) == 10
    assert sum(b["count"] for b in h["bins"]) == 100 == h["n"]


def test_histogram_rejects_bad_bins():
    with pytest.raises(ValueError):
        charts.histogram(pd.Series([1, 2, 3], name="a"), bins=charts.MAX_BINS + 1)


def test_boxplot_finds_outlier():
    b = charts.boxplot(pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100], name="v"))
    assert b["outlier_count"] == 1
    assert b["whisker_high"] == 9
    assert b["max"] == 100


def test_top_categories_groups_the_rest():
    s = pd.Series(["a"] * 5 + ["b"] * 3 + ["c", "d"], name="k")
    t = charts.top_categories(s, n=2)
    assert [i["value"] for i in t["items"]] == ["a", "b"]
    assert t["other_count"] == 2 and t["unique"] == 4


def test_scatter_caps_points():
    df = pd.DataFrame({"x": range(5000), "y": range(5000)})
    s = charts.scatter_sample(df, "x", "y", max_points=100)
    assert s["n_total"] == 5000 and s["n_shown"] == 100 == len(s["points"])


def test_heatmap_shape():
    m = {"a": {"a": 1.0, "b": 0.5}, "b": {"a": 0.5, "b": 1.0}}
    h = charts.heatmap(m)
    assert h["labels"] == ["a", "b"] and h["values"][0][1] == 0.5


@pytest.mark.parametrize("ctype,cols", [
    ("pie", ["age"]),            # unsupported type
    ("histogram", ["city"]),     # wrong column type
    ("histogram", ["nope"]),     # unknown column
    ("scatter", ["age"]),        # wrong column count
    ("scatter", ["age", "age"]), # same column twice
    ("heatmap", ["age"]),        # heatmap is not built here
])
def test_build_chart_rejects_bad_requests(ctype, cols):
    df = pd.DataFrame({"age": [1, 2, 3], "city": ["a", "b", "a"]})
    types = {"age": "numeric", "city": "categorical"}
    with pytest.raises(ValueError):
        charts.build_chart(df, types, ctype, cols)


def test_build_chart_output_is_json_safe():
    df = pd.DataFrame({"age": [1.0, 2.0, None, 4.0], "score": [3.0, None, 5.0, 8.0],
                       "city": ["a", "b", "a", None]})
    types = {"age": "numeric", "score": "numeric", "city": "categorical"}
    for ctype, cols in [("histogram", ["age"]), ("boxplot", ["age"]),
                        ("bar", ["city"]), ("scatter", ["age", "score"])]:
        json.dumps(charts.build_chart(df, types, ctype, cols))


def test_is_discrete():
    assert charts.is_discrete(pd.Series([25, 30, 35, 40] * 10))   # 4 values in 40 rows
    assert not charts.is_discrete(pd.Series(range(40)))           # 40 distinct values
    assert not charts.is_discrete(pd.Series([1, 2, 3, 4]))        # 4 values but only 4 rows


def test_bar_accepts_discrete_numeric_only():
    df = pd.DataFrame({"age": [25, 30, 35, 40] * 10, "score": range(40)})
    types = {"age": "numeric", "score": "numeric"}
    assert charts.build_chart(df, types, "bar", ["age"])["unique"] == 4
    with pytest.raises(ValueError):
        charts.build_chart(df, types, "bar", ["score"])


def test_bar_shows_whole_numbers():
    t = charts.top_categories(pd.Series([25.0, 30.0, 25.0, None, 25.0, 30.0], name="age"))
    assert t["items"][0]["value"] == "25" and t["n"] == 5


def test_chart_options():
    df = pd.DataFrame({"age": [25, 30, 35, 40] * 10,
                       "score": [i * 1.5 for i in range(40)],
                       "city": ["a", "b"] * 20})
    types = {"age": "numeric", "score": "numeric", "city": "categorical"}
    o = charts.chart_options(df, types)
    assert o["columns"]["age"]["suggested"] == "bar"
    assert o["columns"]["score"]["suggested"] == "histogram"
    assert o["columns"]["city"]["charts"] == ["bar"]
    assert o["scatter_columns"] == ["age", "score"] and o["heatmap"] is True

def test_boxplot_outlier_count_matches_engine():
    s = pd.Series(list(range(50)) + [500, -400], name="v")
    assert charts.boxplot(s)["outlier_count"] == iqr_outliers(s)["count"]


def test_constant_column_charts_do_not_crash():
    s = pd.Series([5] * 10, name="c")
    h = charts.histogram(s, bins=4)
    assert h["n"] == 10 and sum(b["count"] for b in h["bins"]) == 10
    b = charts.boxplot(s)
    assert b["outlier_count"] == 0 and b["median"] == 5.0


def test_all_missing_column_is_rejected():
    with pytest.raises(ValueError):
        charts.histogram(pd.Series([None, None], dtype=float, name="m"))