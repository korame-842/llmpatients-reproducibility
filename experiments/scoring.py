"""Offline questionnaire scoring copied from the original Agent scorer.

Only loading a YAML definition requires PyYAML. This module never imports the
Agent, model providers, Pydantic, LangGraph or an embedding model. The scoring
method preserves the original handling of totals, domains, flags and notes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class QuestionnaireScorer:
    def __init__(self, definition: dict):
        self.q_def = definition

    def _compute_scores(self, answers: Dict[str, Any]) -> dict:
        """Apply the scoring config defined in the questionnaire YAML."""
        scoring = self.q_def.get("scoring", {})
        result: dict = {}

        # -- Subscales --
        subscale_scores: Dict[str, float] = {}
        for name, cfg in scoring.get("subscales", {}).items():
            item_ids = cfg.get("items", [])
            method = cfg.get("method", "sum")
            values = [
                answers[str(i)]
                for i in item_ids
                if str(i) in answers and isinstance(answers[str(i)], (int, float))
            ]
            if not values:
                continue
            subscale_scores[name] = sum(values) if method == "sum" else round(sum(values) / len(values), 3)

        if subscale_scores:
            result["subscales"] = subscale_scores

        # -- Domain scores (average of subscales) --
        domain_scores: Dict[str, float] = {}
        for name, cfg in scoring.get("domains", {}).items():
            sub_names = cfg.get("subscales", [])
            method = cfg.get("method", "mean")
            values = [subscale_scores[s] for s in sub_names if s in subscale_scores]
            if not values:
                continue
            domain_scores[name] = (
                sum(values) if method == "sum" else round(sum(values) / len(values), 3)
            )

        if domain_scores:
            result["domains"] = domain_scores

        # -- Total --
        total_cfg = scoring.get("total", {})
        if total_cfg:
            if "subscales" in total_cfg:
                sub_vals = [subscale_scores[s] for s in total_cfg["subscales"] if s in subscale_scores]
                method = total_cfg.get("method", "sum")
                if sub_vals:
                    result["total"] = (
                        sum(sub_vals) if method == "sum" else round(sum(sub_vals) / len(sub_vals), 3)
                    )
            elif "items" in total_cfg:
                item_ids = total_cfg["items"]
                vals = [
                    answers[str(i)]
                    for i in item_ids
                    if str(i) in answers and isinstance(answers[str(i)], (int, float))
                ]
                method = total_cfg.get("method", "sum")
                if vals:
                    result["total"] = sum(vals) if method == "sum" else round(sum(vals) / len(vals), 3)

        # -- Severity label --
        if "total" in result:
            for threshold in scoring.get("severity_thresholds", []):
                if result["total"] <= threshold["max"]:
                    result["severity"] = threshold["label"]
                    break

        # -- Domain flags (DSM-5-TR style: highest item score per domain) --
        domain_flags: dict = {}
        for domain_name, dcfg in scoring.get("domain_flags", {}).items():
            item_ids = dcfg.get("items", [])
            flag_threshold = dcfg.get("flag_threshold", 2)
            vals = [
                answers[str(i)]
                for i in item_ids
                if str(i) in answers and isinstance(answers[str(i)], (int, float))
            ]
            highest = max(vals) if vals else 0
            domain_flags[domain_name] = {"highest": highest, "flag": highest >= flag_threshold}

        if domain_flags:
            result["domain_flags"] = domain_flags

        # -- Functional item (PHQ-9 item 10, stored separately) --
        functional_item = scoring.get("functional_item")
        if functional_item is not None and str(functional_item) in answers:
            val = answers[str(functional_item)]
            item_def = next(
                (it for it in self.q_def.get("items", []) if it["id"] == functional_item), None
            )
            func_labels = {}
            if item_def:
                raw_labels = (item_def.get("scale_override") or {}).get("labels") or {}
                func_labels = {int(k): v for k, v in raw_labels.items()}
            result["functional_impairment"] = {
                "score": val,
                "label": func_labels.get(val, str(val)),
            }

        # -- Notes (e.g. SNAP-2 scoring key notice) --
        if scoring.get("notes"):
            result["notes"] = scoring["notes"]

        return result


def compute_scores(definition: dict, answers: dict) -> dict:
    """Return the archived scorer's calculation without loading any runtime."""
    return QuestionnaireScorer(definition)._compute_scores(answers)


def verify_scores(results_dir, definitions_dir, *, expected_count: int = 30) -> dict:
    """Compare saved scores with answers and YAML rules; do not modify files.

    Returns ``status``, ``checked``, ``matched``, ``mismatches`` and ``errors``.
    The default expected count is the five profiles × six original instruments.
    """
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("YAML scoring definitions require PyYAML==6.0.2.") from exc

    results_dir = Path(results_dir)
    definitions_dir = Path(definitions_dir)
    files = sorted(results_dir.rglob("*.json"))
    mismatches = []
    errors = []
    matched = 0
    for path in files:
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            questionnaire_id = saved["questionnaire_id"]
            if not isinstance(questionnaire_id, str) or Path(questionnaire_id).name != questionnaire_id:
                raise ValueError("Invalid questionnaire identifier")
            definition = yaml.safe_load((definitions_dir / f"{questionnaire_id}.yaml").read_text(encoding="utf-8"))
            calculated = compute_scores(definition, saved["answers"])
            if calculated == saved["scores"]:
                matched += 1
            else:
                mismatches.append({"file": str(path.relative_to(results_dir)), "different_fields": sorted(
                    key for key in set(calculated) | set(saved["scores"])
                    if calculated.get(key) != saved["scores"].get(key)
                )})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"file": str(path.relative_to(results_dir)), "error": type(exc).__name__})
    if len(files) != expected_count:
        errors.append({"error": "UnexpectedResultCount", "expected": expected_count, "found": len(files)})
    return {"status": "PASS" if not errors and not mismatches else "FAIL",
            "checked": len(files), "matched": matched, "mismatches": mismatches, "errors": errors}
