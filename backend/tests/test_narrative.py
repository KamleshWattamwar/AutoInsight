import json
from decimal import Decimal

from app.services import narrative as nar
from app.services.narrative import allowed_numbers, build_input, invalid_numbers
RESULT = {
    "overview": {"rows": 1000, "columns": 5, "duplicate_rows": 0, "total_missing_pct": 2.5},
    "quality_score": 91,
    "findings": [
        {"type": "missing_data", "severity": "medium", "columns": ["age"],
         "message": "age has 12.5% missing values", "evidence": {"count": 125, "pct": 12.5}},
        {"type": "outliers", "severity": "low", "columns": ["income"],
         "message": "income has 3.2% outliers", "evidence": {"count": 32, "pct": 3.2}},
    ],
}

GOOD = json.dumps({
    "summary": "The dataset has 1000 rows and 5 columns with a quality score of 91 out of 100.",
    "findings": [
        {"index": 0, "text": "The age column is missing 12.5% of its values, which is 125 rows."},
        {"index": 1, "text": "About 3.2% of income values are outliers."},
    ],
})
BAD = GOOD.replace("12.5% of its values, which is 125 rows", "40% of its values")


def fake(*outputs):
    """Fake LLM: returns outputs in order (the last one repeats). An Exception is raised."""
    calls = []

    def llm(prompt):
        calls.append(prompt)
        out = outputs[min(len(calls) - 1, len(outputs) - 1)]
        if isinstance(out, Exception):
            raise out
        return out

    llm.calls = calls
    return llm


def test_parse_nums_removes_commas():
    assert nar._parse_nums("3,900 rows and 12.5%") == ["3900", "12.5"]


def test_rounding_is_accepted_but_invented_number_is_not():
    allowed = {Decimal("12.5")}
    assert nar.invalid_numbers("12.5% or about 13%", allowed) == []
    assert nar.invalid_numbers("about 14%", allowed) == ["14"]


def test_build_input_caps_findings_and_keeps_true_total():
    many = {**RESULT, "findings": [
        {"type": "x", "severity": "low", "columns": [], "message": "m", "evidence": {}}
    ] * 20}
    inp = nar.build_input(many)
    assert len(inp["findings"]) == nar.MAX_FINDINGS
    assert inp["finding_counts"]["total"] == 20


def test_valid_output_is_used():
    out = nar.generate_narrative(RESULT, fake(GOOD))
    assert out["source"] == "llm"
    assert all(f["source"] == "llm" for f in out["findings"])


def test_code_fences_are_stripped():
    out = nar.generate_narrative(RESULT, fake("```json\n" + GOOD + "\n```"))
    assert out["source"] == "llm"


def test_invented_number_falls_back_for_that_finding_only():
    llm = fake(BAD)
    out = nar.generate_narrative(RESULT, llm)
    assert out["source"] == "mixed"
    assert out["findings"][0]["source"] == "rules"
    assert out["findings"][0]["text"] == "age has 12.5% missing values"
    assert out["findings"][1]["source"] == "llm"
    assert len(llm.calls) == nar.MAX_ATTEMPTS  # retried once


def test_retry_recovers():
    llm = fake(BAD, GOOD)
    out = nar.generate_narrative(RESULT, llm)
    assert out["source"] == "llm"
    assert len(llm.calls) == 2


def test_invalid_json_falls_back_to_rules():
    llm = fake("not json at all")
    out = nar.generate_narrative(RESULT, llm)
    assert out["source"] == "rules"
    assert [f["text"] for f in out["findings"]] == [f["message"] for f in RESULT["findings"]]
    assert len(llm.calls) == nar.MAX_ATTEMPTS


def test_llm_exception_falls_back_to_rules():
    out = nar.generate_narrative(RESULT, fake(RuntimeError("provider down")))
    assert out["source"] == "rules"
    assert "1000 rows" in out["summary"]

def test_profile_is_in_input_and_its_numbers_are_allowed():
    result = {
        "overview": {"rows": 10, "columns": 2, "duplicate_rows": 0, "total_missing_pct": 0.0,
                     "missing": {}, "column_types": {"age": "numeric"}},
        "columns": {"age": {"type": "numeric",
                            "stats": {"mean": 31.5, "median": 30.0, "min": 20.0, "max": 50.0},
                            "outliers": {"pct": 0.0}}},
        "correlations": {"pairs": []},
        "findings": [],
        "quality_score": 100,
    }
    inp = build_input(result)
    assert inp["profile"]["numeric"][0]["column"] == "age"

    allowed = allowed_numbers(inp)
    assert invalid_numbers("The average age is 31.5.", allowed) == []
    assert invalid_numbers("The average age is 99.", allowed) == ["99"]