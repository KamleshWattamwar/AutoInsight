import pandas as pd
import pytest
from app.services.loader import infer_types, load_csv


def test_type_detection():
    df = pd.DataFrame({
        "n": ["1", "2", "3", "4"],
        "d": ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"],
        "b": ["yes", "no", "yes", "no"],
        "c": ["a", "b", "a", "b"],
        "e": [None, None, None, None],
    })
    _, types = infer_types(df)
    assert types == {"n": "numeric", "d": "datetime", "b": "boolean",
                     "c": "categorical", "e": "empty"}


def test_empty_file(tmp_path):
    f = tmp_path / "empty.csv"
    f.write_text("")
    with pytest.raises(ValueError):
        load_csv(str(f))