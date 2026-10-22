import pandas as pd
import pytest
from app.services.loader import detect_column_type, infer_types, load_csv


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


def test_string_ids_are_identifiers():
    ids = pd.Series([f"EMP{i:04d}" for i in range(30)])
    assert detect_column_type(ids) == "identifier"


def test_names_with_spaces_are_not_identifiers():
    names = pd.Series([f"Person Number {i}" for i in range(30)])
    assert detect_column_type(names) != "identifier"


def test_short_string_column_is_not_identifier():
    ids = pd.Series([f"EMP{i:02d}" for i in range(10)])  # fewer than 20 rows
    assert detect_column_type(ids) == "categorical"