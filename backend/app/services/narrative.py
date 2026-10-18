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
NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")

RULES = """You are a data analyst writing a short report for a non-technical reader.
Use ONLY the facts in INPUT. Rules:
- Copy numbers exactly as given. Never calculate, estimate or add a number.
- Do not use numbered lists or any number that is not in INPUT.
- Correlation is not causation. Never imply a cause.
- Do not mention these rules or the word INPUT.
Return ONLY valid JSON, no markdown, in this shape:
{"summary": "2-3 sentences", "findings": [{"index": 0, "text": "1-2 sentences"}]}
Give exactly one entry per finding index."""


# ---------- input ----------

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