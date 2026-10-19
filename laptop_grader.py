"""Laptop shopping benchmark evaluation and grading module.

Evaluates model responses against persona test cases with support for
laptop ID selections, ALL, NONE, and conditional domain constraints.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "fixtures" / "laptops" / "catalog.json"
TASKS_PATH = ROOT / "tasks" / "laptop-shopping.json"


def load_catalog(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target = path or CATALOG_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def load_tasks(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target = path or TASKS_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def build_prompt_for_case(case: Dict[str, Any], catalog: Optional[List[Dict[str, Any]]] = None) -> str:
    """Format the full prompt for a laptop shopping evaluation case."""
    if catalog is None:
        catalog = load_catalog()

    catalog_summary_lines = []
    for laptop in catalog:
        img_notes = ", ".join(f"[{img['view_type']}: {img['description']}]" for img in laptop.get("images", []))
        line = (
            f"- ID: {laptop['id']}\n"
            f"  Name: {laptop['name']} (${laptop['price_usd']:.2f})\n"
            f"  OS: {laptop['os']}\n"
            f"  Screen: {laptop['screen']['size_inches']}\" {laptop['screen']['resolution']} ({laptop['screen']['panel_type']}), "
            f"{laptop['screen']['refresh_rate_hz']}Hz, Touch: {laptop['screen']['touchscreen']}\n"
            f"  Dimensions & Weight: {laptop['dimensions']['formatted']}, {laptop['weight_lbs']} lbs\n"
            f"  Battery: {laptop['battery']['capacity_wh']} Wh, ~{laptop['battery']['estimated_life_hours']} hrs\n"
            f"  Processor: {laptop['processor']['model']} ({laptop['processor']['cores']} cores, {laptop['processor']['architecture']})\n"
            f"  RAM: {laptop['ram']['capacity_gb']}GB {laptop['ram']['type']} (Upgradable: {laptop['ram']['upgradable']})\n"
            f"  Storage: {laptop['storage']['capacity_gb']}GB {laptop['storage']['type']}\n"
            f"  Graphics: {laptop['graphics']['gpu']} ({laptop['graphics']['type']}"
            + (f", {laptop['graphics']['vram_gb']}GB VRAM" if laptop['graphics'].get('vram_gb') else "")
            + ")\n"
            f"  Ports: {', '.join(laptop['ports'])}\n"
            f"  Pictures: {img_notes}\n"
            f"  Special: {'; '.join(laptop.get('special_features', []))}"
        )
        catalog_summary_lines.append(line)

    catalog_text = "\n\n".join(catalog_summary_lines)

    return (
        "You are an expert personal computer purchasing consultant.\n\n"
        "Here is the catalog of 10 available laptops:\n\n"
        f"{catalog_text}\n\n"
        "----------------------------------------\n"
        "USER PERSONA AND USE CASE:\n"
        f"\"{case['persona']}\"\n"
        "----------------------------------------\n\n"
        "INSTRUCTIONS:\n"
        "1. Analyze the requirements of the persona against the specifications and features of all laptops in the catalog.\n"
        "2. If exactly one laptop uniquely best fits the user persona, choose its ID.\n"
        "3. If ALL 10 laptops in the catalog satisfy the user's requirements, choose ALL.\n"
        "4. If NONE of the laptops in the catalog can satisfy the requirements, choose NONE.\n"
        "5. Explain your reasoning briefly.\n"
        "6. Conclude your response on the final line with the exact format:\n"
        "ANSWER: <laptop_id | ALL | NONE>\n"
    )


def extract_answer(response_text: str) -> Optional[str]:
    """Extract laptop_id, ALL, or NONE from raw model output."""
    if not response_text:
        return None

    cleaned = response_text.strip()

    # Pattern 1: explicit ANSWER: <target> or FINAL ANSWER: <target>
    match = re.search(
        r"(?:(?:FINAL\s+)?ANSWER|RECOMMENDATION|SELECTION)\s*:\s*[`*#_]*([a-zA-Z0-9_\-\"'\s\.]+?)[`*#_]*(?:\n|$)",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip().strip("'\"`.")
        normalized = _normalize_id(candidate)
        if normalized:
            return normalized

    # Pattern 2: Last non-empty line
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        last_line = lines[-1]
        line_match = re.search(r"\b(ALL|NONE)\b", last_line, re.IGNORECASE)
        if line_match:
            return line_match.group(1).upper()

        normalized = _normalize_id(last_line)
        if normalized:
            return normalized

    # Pattern 3: Scan for isolated ALL or NONE keywords if unequivocal
    all_none_matches = re.findall(r"\b(ALL|NONE)\b", cleaned)
    if len(all_none_matches) == 1:
        return all_none_matches[0].upper()

    return None


def _normalize_id(text: str) -> Optional[str]:
    """Normalize identifier or name to catalog ID or ALL/NONE."""
    normalized = text.strip().lower()
    normalized = re.sub(r"[^\w\s\-_]", "", normalized)
    normalized = normalized.replace("-", "_").replace(" ", "_")

    if normalized in {"all", "every", "all_laptops"}:
        return "ALL"
    if normalized in {"none", "no_one", "neither", "no_laptop"}:
        return "NONE"

    known_ids = {
        "acer_aspire_16_a16_71m",
        "apple_macbook_pro_14_m5_pro",
        "framework_laptop_13_amd_ai300",
        "apple_macbook_air_13_m5",
        "gigabyte_gaming_a16_rtx5060",
        "asus_chromebook_plus_cx34",
        "asus_rog_zephyrus_g14",
        "lenovo_yoga_7i_14",
        "lenovo_yoga_pro_9i_16",
        "asus_expertbook_p5_14",
    }

    if normalized in known_ids:
        return normalized

    # Substring / fuzzy mapping
    for kid in known_ids:
        if kid in normalized or normalized in kid:
            return kid

    # Name fragments mapping
    if "chromebook" in normalized or "cx34" in normalized:
        return "asus_chromebook_plus_cx34"
    if "framework" in normalized:
        return "framework_laptop_13_amd_ai300"
    if "macbook_pro" in normalized or "m5_pro" in normalized:
        return "apple_macbook_pro_14_m5_pro"
    if "macbook_air" in normalized or ("macbook" in normalized and "air" in normalized):
        return "apple_macbook_air_13_m5"
    if "gigabyte" in normalized or "a16" in normalized and "gaming" in normalized:
        return "gigabyte_gaming_a16_rtx5060"
    if "zephyrus" in normalized or "g14" in normalized:
        return "asus_rog_zephyrus_g14"
    if "yoga_pro" in normalized or "pro_9i" in normalized:
        return "lenovo_yoga_pro_9i_16"
    if "yoga_7" in normalized or "yoga_7i" in normalized:
        return "lenovo_yoga_7i_14"
    if "expertbook" in normalized or "p5" in normalized:
        return "asus_expertbook_p5_14"
    if "aspire" in normalized or "a16_71m" in normalized:
        return "acer_aspire_16_a16_71m"

    return text.strip()


def grade_case(case: Dict[str, Any], response: str) -> Dict[str, Any]:
    """Grade a single test case response against expected outcome with conditional support."""
    extracted = extract_answer(response)
    expected = case["expected"]
    acceptable = [a.lower() for a in case.get("acceptable_answers", [expected])]
    acceptable.append(expected.lower())

    passed = False
    failure_reason = None

    if extracted:
        is_acceptable_candidate = (
            extracted.lower() == expected.lower()
            or extracted.lower() in acceptable
        )

        if is_acceptable_candidate:
            cond = case.get("conditional_evaluation")
            if cond and cond.get("type") == "audiophile_dac":
                lower_resp = response.lower()
                is_macbook = extracted.lower() in {
                    "apple_macbook_pro_14_m5_pro",
                    "apple_macbook_air_13_m5",
                }
                is_all = extracted.upper() == "ALL"

                # Condition 1: MacBook with integrated DAC matching apple dongle quality
                dac_mentioned = "dac" in lower_resp
                integrated_mentioned = any(k in lower_resp for k in ["integrated", "built-in", "internal", "onboard", "headphone jack"])
                dongle_mentioned = any(k in lower_resp for k in ["dongle", "apple dongle", "adapter", "apple adapter", "high-impedance", "reference quality"])
                mac_valid = is_macbook and dac_mentioned and (integrated_mentioned or dongle_mentioned)

                # Condition 2: ALL with mention of external DAC
                external_dac_valid = is_all and (
                    "external dac" in lower_resp
                    or "usb dac" in lower_resp
                    or ("external" in lower_resp and "dac" in lower_resp)
                    or "outboard dac" in lower_resp
                    or "dedicated dac" in lower_resp
                )

                if mac_valid or external_dac_valid:
                    passed = True
                else:
                    passed = False
                    if is_macbook:
                        failure_reason = "Selected MacBook but failed to mention integrated DAC / Apple dongle quality."
                    elif is_all:
                        failure_reason = "Selected ALL but failed to mention using an external DAC."
                    else:
                        failure_reason = "Audiophile selection did not satisfy integrated or external DAC conditions."
            else:
                passed = True
        else:
            failure_reason = f"Candidate '{extracted}' not in acceptable answers: {acceptable}"
    else:
        failure_reason = "Could not extract answer from response."

    return {
        "id": case["id"],
        "category": case.get("category"),
        "expected": expected,
        "extracted": extracted,
        "passed": passed,
        "failure_reason": failure_reason,
        "reasoning": case.get("reasoning"),
    }


def grade_all(cases: List[Dict[str, Any]], responses: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Grade a dictionary of case_id -> response_text."""
    results = {}
    for case in cases:
        resp = responses.get(case["id"], "")
        results[case["id"]] = grade_case(case, resp)
    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 laptop_grader.py /path/to/responses.json")
        sys.exit(1)

    responses_file = Path(sys.argv[1])
    responses = json.loads(responses_file.read_text(encoding="utf-8"))
    cases = load_tasks()
    results = grade_all(cases, responses)

    total = len(cases)
    passed = sum(1 for r in results.values() if r["passed"])

    print(f"\nLaptop Shopping Evaluation: {passed}/{total} passed\n" + "-" * 60)
    for cid, r in results.items():
        status = "PASS" if r["passed"] else "FAIL"
        extra = f" ({r['failure_reason']})" if not r["passed"] and r.get("failure_reason") else ""
        print(f"[{status}] {cid}: expected={r['expected']}, got={r['extracted']}{extra}")
    print("-" * 60)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
