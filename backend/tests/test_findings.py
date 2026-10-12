from app.services.findings import detect, quality_score


def _ov(**kw):
    base = {"rows": 100, "duplicate_rows": 0, "total_missing_pct": 0.0,
            "missing": {}, "constant_columns": []}
    return {**base, **kw}


NO_CORR = {"pairs": [], "matrix": {}}


def test_high_missing():
    ov = _ov(missing={"income": {"count": 40, "pct": 40.0}})
    f = detect(ov, {}, NO_CORR)
    assert f[0]["type"] == "missing_data" and f[0]["severity"] == "high"


def test_skewed_column():
    cols = {"x": {"type": "numeric", "stats": {"skewness": 3.1},
                  "outliers": {"count": 0, "pct": 0.0}}}
    assert any(f["type"] == "skewed_distribution" for f in detect(_ov(), cols, NO_CORR))


def test_clean_data():
    cols = {"x": {"type": "numeric", "stats": {"skewness": 0.1},
                  "outliers": {"count": 0, "pct": 0.0}}}
    assert detect(_ov(), cols, NO_CORR) == []
    assert quality_score(_ov(), cols) == 100


def test_sorted_by_severity():
    ov = _ov(missing={"a": {"count": 6, "pct": 6.0}, "b": {"count": 40, "pct": 40.0}})
    sev = [f["severity"] for f in detect(ov, {}, NO_CORR)]
    assert sev == ["high", "medium"]