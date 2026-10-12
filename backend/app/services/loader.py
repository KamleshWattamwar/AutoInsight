"""CSV loading and column type detection."""
import warnings
import pandas as pd

MAX_ROWS = 500_000
NUMERIC_THRESHOLD = 0.95   # share of values that must parse as numbers
DATE_THRESHOLD = 0.90
DATE_SAMPLE = 200          # only parse this many values when testing for dates
BOOL_WORDS = {"true", "false", "yes", "no"}

ID_UNIQUE_RATIO = 0.95
ID_MIN_ROWS = 20


def _numeric_or_identifier(nums: pd.Series) -> str:
    nums = nums.dropna()
    is_whole = (nums % 1 == 0).all()
    unique_ratio = nums.nunique() / len(nums)
    if is_whole and unique_ratio > ID_UNIQUE_RATIO and len(nums) >= ID_MIN_ROWS:
        return "identifier"
    return "numeric"


def load_csv(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, nrows=MAX_ROWS, low_memory=False)
    except pd.errors.EmptyDataError:
        raise ValueError("CSV file is empty")
    if df.shape[1] == 0:
        raise ValueError("CSV has no columns")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def detect_column_type(s: pd.Series) -> str:
    s = s.dropna()
    if s.empty:
        return "empty"
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_numeric_dtype(s):
        return _numeric_or_identifier(s)

    as_str = s.astype(str).str.strip()
    if set(as_str.str.lower().unique()) <= BOOL_WORDS:
        return "boolean"

    nums = pd.to_numeric(as_str, errors="coerce")
    if nums.notna().mean() > NUMERIC_THRESHOLD:
        return _numeric_or_identifier(nums)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sample = pd.to_datetime(as_str.head(DATE_SAMPLE), errors="coerce", format="mixed")
    if sample.notna().mean() > DATE_THRESHOLD:
        return "datetime"

    if s.nunique() / len(s) > 0.9 and s.nunique() > 50:
        return "text"
    return "categorical"


def infer_types(df: pd.DataFrame):
    """Return (cleaned copy of df, {column: type})."""
    df = df.copy()
    types = {}
    for col in df.columns:
        t = detect_column_type(df[col])
        types[col] = t
        if t == "numeric":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif t == "datetime":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
    return df, types