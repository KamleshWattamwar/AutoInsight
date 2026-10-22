"""Rule-based findings and the data quality score."""

T = {
    "missing_high": 30, "missing_medium": 5, "missing_low": 1,
    "corr_moderate": 0.5, "corr_strong": 0.7,
    "skew": 2.0, "outlier_pct": 5.0, "dup_pct": 1.0,
    "dominant_cat_pct": 80.0, "high_cardinality": 50,
}
ORDER = {"high": 0, "medium": 1, "low": 2}


def _finding(type_, severity, columns, message, evidence):
    return {"type": type_, "severity": severity, "columns": columns,
            "message": message, "evidence": evidence}


def detect(overview: dict, columns: dict, correlations: dict) -> list:
    out = []

    for col, m in overview["missing"].items():
        if m["pct"] >= T["missing_high"]:
            sev = "high"
        elif m["pct"] >= T["missing_medium"]:
            sev = "medium"
        elif m["pct"] >= T["missing_low"]:
            sev = "low"
        else:
            continue
        out.append(_finding("missing_data", sev, [col],
                            f"{col} has {m['pct']}% missing values", m))

    rows = overview["rows"]
    dup_pct = overview["duplicate_rows"] / rows * 100 if rows else 0
    if dup_pct >= T["dup_pct"]:
        out.append(_finding("duplicates", "medium", [],
                            f"{overview['duplicate_rows']} duplicate rows ({dup_pct:.1f}%)",
                            {"count": overview["duplicate_rows"], "pct": round(dup_pct, 2)}))

    for col in overview["constant_columns"]:
        out.append(_finding("constant_column", "low", [col],
                            f"{col} has a single value", {}))

    for col, info in columns.items():
        kind = info["type"]
        if kind == "numeric":
            skew = info["stats"].get("skewness")
            if skew is not None and abs(skew) >= T["skew"]:
                out.append(_finding("skewed_distribution", "medium", [col],
                                    f"{col} is heavily skewed (skewness {skew})",
                                    {"skewness": skew}))
            o = info["outliers"]
            if o["pct"] >= T["outlier_pct"]:
                out.append(_finding("outliers", "medium", [col],
                                    f"{col} has {o['count']} potential outliers ({o['pct']}%)", o))
        elif kind == "categorical":
            top = info["stats"].get("top")
            if top and top[0]["pct"] >= T["dominant_cat_pct"]:
                out.append(_finding("dominant_category", "low", [col],
                                    f"{col} is dominated by '{top[0]['value']}' ({top[0]['pct']}%)",
                                    top[0]))
        elif kind == "text" and info["unique"] > T["high_cardinality"]:
            out.append(_finding("high_cardinality", "low", [col],
                                f"{col} has {info['unique']} unique values",
                                {"unique": info["unique"]}))

    for p in correlations["pairs"]:
        # Pearson is distorted by outliers, so use the stronger of the two
        main = max((p["pearson"] or 0, p["spearman"] or 0), key=abs)
        if abs(main) >= T["corr_moderate"]:
            strong = abs(main) >= T["corr_strong"]
            direction = "positive" if main > 0 else "negative"
            out.append(_finding(
                "correlation", "medium" if strong else "low", [p["a"], p["b"]],
                f"{p['a']} and {p['b']} show a {'strong' if strong else 'moderate'} "
                f"{direction} correlation (Pearson {p['pearson']}, Spearman {p['spearman']})",
                {**p, "note": "correlation, not causation"}))

    return sorted(out, key=lambda f: ORDER[f["severity"]])


def quality_score(overview: dict, columns: dict) -> int:
    """0-100. Capped penalties: missing % x2 (max 40), duplicate % x3 (max 15),
    5 per constant column (max 15), mean numeric outlier % x1.5 (max 15)."""
    rows = overview["rows"] or 1
    dup_pct = overview["duplicate_rows"] / rows * 100
    out_pcts = [c["outliers"]["pct"] for c in columns.values() if c["type"] == "numeric"]
    avg_out = sum(out_pcts) / len(out_pcts) if out_pcts else 0
    penalty = (min(40, overview["total_missing_pct"] * 2)
               + min(15, dup_pct * 3)
               + min(15, 5 * len(overview["constant_columns"]))
               + min(15, avg_out * 1.5))
    return round(max(0, 100 - penalty))