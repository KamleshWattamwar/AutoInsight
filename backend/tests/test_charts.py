import json

import pandas as pd
import pytest

from app.services import charts


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
])
def test_build_chart_rejects_bad_requests(ctype, cols):
    df = pd.DataFrame({"age": [1, 2, 3], "city": ["a", "b", "a"]})
    types = {"age": "numeric", "city": "categorical"}
    with pytest.raises(ValueError):
        charts.build_chart(df, types, ctype, cols)


def test_build_chart_output_is_json_safe():
    df = pd.DataFrame({"age": [1.0, 2.0, None, 4.0], "city": ["a", "b", "a", None]})
    types = {"age": "numeric", "city": "categorical"}
    for ctype, cols in [("histogram", ["age"]), ("boxplot", ["age"]),
                        ("bar", ["city"]), ("scatter", ["age", "age"])]:
        json.dumps(charts.build_chart(df, types, ctype, cols))