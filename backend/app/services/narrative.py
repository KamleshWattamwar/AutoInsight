"""LLM narrative layer: prompt building, number validation, rule-based fallback.

No web, database or provider code here. The LLM is passed in as a callable
`llm(prompt: str) -> str`, so tests can fake it and the provider can be swapped.
"""
import json
import logging
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2        # first try + one retry
MAX_FINDINGS = 15       # findings are sorted high to low, so the top ones are narrated
MAX_PROFILE_COLS = 8    # numeric and categorical columns shown to the LLM
MAX_PAIRS = 5           # strongest correlations shown to the LLM
MAX_MISSING = 5         # worst missing-data columns shown to the LLM
NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")

RULES = """You are a senior data analyst writing a brief for a non-technical manager.
Use ONLY the facts in INPUT. Rules:
- Use numbers from INPUT only. Round long decimals to at most 2 decimal places, and to whole numbers above 1000. Never calculate, estimate or add a number. Use at most 10 numbers in the summary.
- Always name the column a number belongs to. Never attach a dataset-wide figure to a single column.
- Do not use numbered lists or any number that is not in INPUT.
- Correlation is not causation. Never imply a cause.
- Do not mention these rules or the word INPUT.
- Write percentages with a % sign.
- The summary is 3 short paragraphs of 120 to 180 words in total, separated by a blank line (in the JSON string write \\n\\n):
  1. Headline: what the dataset appears to be about (infer from column names, and say "appears" if unsure), its size, and a one-sentence verdict on how trustworthy it is.
  2. What stands out: lead with the biggest data-quality problem (column name and its percentage), then mention any other missing-data column from "most_missing" with its percentage. Then add at least one insight that is not about missing data: a numeric column whose mean and median differ noticeably (quote both, do not state the difference) or that has outliers, a dominant or notably balanced category from "profile", or the strongest relationship if "strongest_correlations" is not empty.
  3. Next steps: exactly two actions. Each must name a specific column and say why it matters in one short clause. No generic advice such as "verify the source". Do not guess what a column means beyond its name.
- For each finding, say what it means for the data and one sensible next step, in plain words and without new numbers.
Return ONLY valid JSON, no markdown, in this shape:
{"summary": "...", "findings": [{"index": 0, "text": "1-2 sentences"}]}
Give exactly one entry per finding index."""

# ---------- input ----------

def _profile(result: dict) -> dict:
    """Verified facts from the engine for the LLM to compare. Built by code, never by the LLM."""
    ov = result.get("overview", {})
    columns = result.get("columns", {})

    type_counts: dict = {}
    for t in ov.get("column_types", {}).values():
        type_counts[t] = type_counts.get(t, 0) + 1

    numeric, categorical, datetimes = [], [], []
    for name, info in columns.items():
        stats = info.get("stats") or {}
        kind = info.get("type")
        if kind == "numeric" and len(numeric) < MAX_PROFILE_COLS:
            numeric.append({
                "column": name,
                **{k: stats.get(k) for k in ("mean", "median", "min", "max")},
                "outlier_pct": (info.get("outliers") or {}).get("pct"),
            })
        elif kind in ("categorical", "boolean") and len(categorical) < MAX_PROFILE_COLS:
            categorical.append({"column": name, "unique": stats.get("unique"), "top": stats.get("top")})
        elif kind == "datetime" and len(datetimes) < 3:
            datetimes.append({"column": name, **{k: stats.get(k) for k in ("min", "max", "span_days")}})

    pairs = sorted(
        result.get("correlations", {}).get("pairs", []),
        key=lambda p: max(abs(p.get("pearson") or 0), abs(p.get("spearman") or 0)),
        reverse=True,
    )[:MAX_PAIRS]
    missing = sorted(ov.get("missing", {}).items(), key=lambda kv: kv[1]["pct"], reverse=True)[:MAX_MISSING]

    return {
        "column_type_counts": type_counts,
        "numeric": numeric,
        "categorical": categorical,
        "datetime": datetimes,
        "strongest_correlations": [
            {k: p.get(k) for k in ("a", "b", "pearson", "spearman", "n")} for p in pairs
        ],
        "most_missing": [{"column": c, "pct": m["pct"]} for c, m in missing],
    }


def build_input(result: dict) -> dict:
    """Compact, LLM-safe view of the analysis result. No raw data."""
    ov = result["overview"]
    findings = result["findings"]
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("high", "medium", "low")}
    return {
        "overview": {k: ov[k] for k in ("rows", "columns", "duplicate_rows", "total_missing_pct")},
        "quality_score": result["quality_score"],
        "quality_score_max": 100,
        "finding_counts": {"total": len(findings), **counts},
        "profile": _profile(result),
        "findings": [
            {"index": i, **{k: f[k] for k in ("type", "severity", "columns", "message", "evidence")}}
            for i, f in enumerate(findings[:MAX_FINDINGS])
        ],
    }


def build_prompt(inp: dict) -> str:
    return f"{RULES}\n\nINPUT:\n{json.dumps(inp)}"


# ---------- number validation ----------

def _parse_nums(text: str) -> list[str]:
    """Numbers as strings, thousands commas removed: '3,900' -> '3900'."""
    return [m.replace(",", "") for m in NUM_RE.findall(text)]


def _collect(obj, out: set) -> None:
    if obj is None or isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(abs(Decimal(str(obj))))
    elif isinstance(obj, str):
        out.update(Decimal(n) for n in _parse_nums(obj))  # digits inside names/messages
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _collect(k, out)
            _collect(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, out)


def allowed_numbers(inp: dict) -> set:
    """Every number the LLM may use. The finding 'index' is excluded on purpose,
    otherwise an invented '7' would pass just because a finding has index 7."""
    out: set = set()
    _collect({k: v for k, v in inp.items() if k != "findings"}, out)
    for f in inp["findings"]:
        _collect({k: v for k, v in f.items() if k != "index"}, out)
    return out


def _is_supported(num: str, allowed: set) -> bool:
    """True if some allowed value rounds (half up) to `num` at num's own precision."""
    n = Decimal(num)
    dp = len(num.split(".")[1]) if "." in num else 0
    q = Decimal(1).scaleb(-dp)
    return any(a.quantize(q, rounding=ROUND_HALF_UP) == n for a in allowed)


def invalid_numbers(text: str, allowed: set) -> list[str]:
    return [n for n in _parse_nums(text) if not _is_supported(n, allowed)]


# ---------- fallback ----------

def fallback_summary(inp: dict) -> str:
    ov, c = inp["overview"], inp["finding_counts"]
    return (
        f"The dataset has {ov['rows']} rows and {ov['columns']} columns. "
        f"Data quality score: {inp['quality_score']}/{inp['quality_score_max']}. "
        f"{c['total']} findings: {c['high']} high, {c['medium']} medium, {c['low']} low severity."
    )


def _all_rules(inp: dict) -> dict:
    return {
        "source": "rules",
        "summary": fallback_summary(inp),
        "findings": [
            {"index": f["index"], "text": f["message"], "source": "rules"} for f in inp["findings"]
        ],
    }


# ---------- parse and assemble ----------

def _parse(raw) -> dict | None:
    if not isinstance(raw, str):
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("summary"), str)
        or not isinstance(data.get("findings"), list)
    ):
        return None
    return data


def _assemble(data: dict, inp: dict, allowed: set) -> tuple[dict, int]:
    """Keep each LLM piece that passes validation, use the rule-based text otherwise.
    Returns (narrative, number of pieces that fell back)."""
    bad = 0

    summary = data["summary"].strip()
    if summary and not invalid_numbers(summary, allowed):
        summary_src = "llm"
    else:
        summary, summary_src = fallback_summary(inp), "rules"
        bad += 1

    texts = {
        item["index"]: item["text"].strip()
        for item in data["findings"]
        if isinstance(item, dict) and isinstance(item.get("index"), int) and isinstance(item.get("text"), str)
    }
    findings = []
    for f in inp["findings"]:
        text = texts.get(f["index"])
        if text and not invalid_numbers(text, allowed):
            findings.append({"index": f["index"], "text": text, "source": "llm"})
        else:
            findings.append({"index": f["index"], "text": f["message"], "source": "rules"})
            bad += 1

    total = 1 + len(findings)
    source = "llm" if bad == 0 else "rules" if bad == total else "mixed"
    return {"source": source, "summary": summary, "findings": findings}, bad


# ---------- entry point ----------

def generate_narrative(result: dict, llm: Callable[[str], str]) -> dict:
    """Narrate the findings. Never raises: any LLM failure ends in the rule-based text."""
    inp = build_input(result)
    allowed = allowed_numbers(inp)
    prompt = build_prompt(inp)

    best: tuple[dict, int] | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            raw = llm(prompt)
        except Exception:
            logger.exception("LLM call failed")
            continue
        data = _parse(raw)
        if data is None:
            continue
        narrative, bad = _assemble(data, inp, allowed)
        if best is None or bad < best[1]:
            best = (narrative, bad)
        if bad == 0:
            break
    return best[0] if best else _all_rules(inp)