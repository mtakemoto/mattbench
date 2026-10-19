"""Unit tests for laptop shopping benchmark schema, catalog, tasks, and grader."""

import json
import unittest
from pathlib import Path
import jsonschema

from suites.laptop_shopping.grader import (
    TASKS_PATH,
    CATALOG_PATH,
    build_prompt_for_case,
    extract_answer,
    grade_all,
    grade_case,
    load_catalog,
    load_tasks,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "fixtures" / "laptops" / "schema.json"


class LaptopShoppingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(CATALOG_PATH)
        self.tasks = load_tasks(TASKS_PATH)
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_schema_validity_and_catalog_conformance(self):
        """Confirm that the JSON schema is valid and all laptops in the catalog conform."""
        validator = jsonschema.Draft202012Validator(self.schema)
        errors = list(validator.iter_errors(self.catalog))
        self.assertEqual(errors, [], f"Schema validation errors found: {errors}")
        self.assertEqual(len(self.catalog), 10, "Catalog must contain exactly 10 laptops")

    def test_initial_five_laptops_present_with_required_specs(self):
        """Verify the 5 laptops specified in the prompt are present and accurately configured."""
        laptop_ids = {item["id"] for item in self.catalog}
        expected_five = {
            "acer_aspire_16_a16_71m",
            "apple_macbook_pro_14_m5_pro",
            "framework_laptop_13_amd_ai300",
            "apple_macbook_air_13_m5",
            "gigabyte_gaming_a16_rtx5060",
        }
        for fid in expected_five:
            self.assertIn(fid, laptop_ids, f"Expected laptop '{fid}' missing from catalog")

        # Check required spec fields across all laptops
        for laptop in self.catalog:
            self.assertTrue(laptop["id"])
            self.assertTrue(laptop["name"])
            self.assertTrue(laptop["brand"])
            self.assertGreater(laptop["price_usd"], 0)
            self.assertTrue(laptop["os"])
            # Screen
            self.assertGreater(laptop["screen"]["size_inches"], 10)
            self.assertIn("x", laptop["screen"]["resolution"])
            self.assertGreater(laptop["screen"]["resolution_horizontal"], 800)
            self.assertGreater(laptop["screen"]["resolution_vertical"], 600)
            self.assertGreaterEqual(laptop["screen"]["refresh_rate_hz"], 60)
            # Physical
            self.assertGreater(laptop["dimensions"]["width_in"], 0)
            self.assertGreater(laptop["dimensions"]["depth_in"], 0)
            self.assertGreater(laptop["dimensions"]["thickness_in"], 0)
            self.assertTrue(laptop["dimensions"]["formatted"])
            self.assertGreater(laptop["weight_lbs"], 0)
            # Battery
            self.assertGreater(laptop["battery"]["capacity_wh"], 0)
            self.assertGreater(laptop["battery"]["estimated_life_hours"], 0)
            # Hardware
            self.assertTrue(laptop["processor"]["model"])
            self.assertGreater(laptop["processor"]["cores"], 0)
            self.assertIn(laptop["processor"]["architecture"], {"x86_64", "ARM64"})
            self.assertGreater(laptop["ram"]["capacity_gb"], 0)
            self.assertGreater(laptop["storage"]["capacity_gb"], 0)
            self.assertIn(laptop["graphics"]["type"], {"integrated", "discrete"})
            self.assertGreater(len(laptop["ports"]), 0)
            # Pictures
            self.assertGreaterEqual(len(laptop["images"]), 2)
            for img in laptop["images"]:
                self.assertTrue(img["url"].startswith("http"))
                self.assertTrue(img["description"])
                self.assertIn(img["view_type"], {"front", "angled", "keyboard", "ports", "open", "profile"})

    def test_tasks_coverage_and_trick_questions(self):
        """Verify tasks cover the 10 personas plus ALL and NONE trick questions."""
        numbered_personas = {t.get("persona_number") for t in self.tasks if t.get("persona_number") is not None}
        self.assertEqual(numbered_personas, set(range(1, 11)), "Personas 1 through 10 must be present")

        # Check trick questions
        all_cases = [t for t in self.tasks if t["expected"] == "ALL"]
        none_cases = [t for t in self.tasks if t["expected"] == "NONE"]

        self.assertGreaterEqual(len(all_cases), 1, "Must contain questions where expected is ALL")
        self.assertGreaterEqual(len(none_cases), 1, "Must contain questions where expected is NONE")

        # Check specific tricky persona 8 (AI engineer 128B) has expected NONE
        persona_8 = next(t for t in self.tasks if t.get("persona_number") == 8)
        self.assertEqual(persona_8["expected"], "NONE")
        self.assertIn("128B", persona_8["persona"])

        # Check persona 9 (Elderly person with back issues)
        persona_9 = next(t for t in self.tasks if t.get("persona_number") == 9)
        self.assertIn("back issues", persona_9["persona"].lower())
        self.assertEqual(persona_9["expected"], "apple_macbook_air_13_m5")

        # Check persona 10 (Audiophile)
        persona_10 = next(t for t in self.tasks if t.get("persona_number") == 10)
        self.assertIn("audiophile", persona_10["persona"].lower())
        self.assertIn("ALL", persona_10["acceptable_answers"])
        self.assertIn("apple_macbook_pro_14_m5_pro", persona_10["acceptable_answers"])

    def test_audiophile_conditional_grading(self):
        """Verify conditional rules for the audiophile persona."""
        case = next(t for t in self.tasks if t["id"] == "persona_10_audiophile_best_audio")

        # Case A: MacBook Pro with mention of integrated DAC / Apple dongle quality -> PASS
        resp_mac_good = (
            "The MacBook Pro features an exceptional integrated hardware DAC that matches the "
            "reference quality of the Apple dongle and supports high-impedance headphones.\n"
            "ANSWER: apple_macbook_pro_14_m5_pro"
        )
        self.assertTrue(grade_case(case, resp_mac_good)["passed"])

        # Case B: MacBook Air with mention of built-in DAC -> PASS
        resp_air_good = (
            "The MacBook Air includes a built-in hardware DAC matching the Apple adapter sound quality.\n"
            "ANSWER: apple_macbook_air_13_m5"
        )
        self.assertTrue(grade_case(case, resp_air_good)["passed"])

        # Case C: MacBook without mentioning DAC / dongle -> FAIL
        resp_mac_bad = (
            "The MacBook Pro has great speakers and a nice screen.\n"
            "ANSWER: apple_macbook_pro_14_m5_pro"
        )
        self.assertFalse(grade_case(case, resp_mac_bad)["passed"])

        # Case D: ALL with mention of external USB DAC -> PASS
        resp_all_good = (
            "An audiophile using a dedicated external USB DAC can use any laptop to stream bit-perfect audio.\n"
            "ANSWER: ALL"
        )
        self.assertTrue(grade_case(case, resp_all_good)["passed"])

        # Case E: ALL without mention of external DAC -> FAIL
        resp_all_bad = (
            "All laptops have headphone jacks.\n"
            "ANSWER: ALL"
        )
        self.assertFalse(grade_case(case, resp_all_bad)["passed"])

        # Case F: Non-Macbook selection (e.g. Acer) -> FAIL
        resp_wrong = (
            "The Acer has a headphone jack.\n"
            "ANSWER: acer_aspire_16_a16_71m"
        )
        self.assertFalse(grade_case(case, resp_wrong)["passed"])

    def test_prompt_builder(self):
        """Check prompt formatting includes catalog details and persona instructions."""
        case = self.tasks[0]
        prompt = build_prompt_for_case(case, self.catalog)
        self.assertIn("catalog of 10 available laptops", prompt)
        self.assertIn(case["persona"], prompt)
        self.assertIn("ANSWER: <laptop_id | ALL | NONE>", prompt)
        self.assertIn("Pictures:", prompt)

    def test_answer_extractor_patterns(self):
        """Test extraction of targets from varied formatting styles."""
        self.assertEqual(extract_answer("ANSWER: asus_chromebook_plus_cx34"), "asus_chromebook_plus_cx34")
        self.assertEqual(extract_answer("FINAL ANSWER: ALL"), "ALL")
        self.assertEqual(extract_answer("The best choice is None.\nANSWER: NONE"), "NONE")
        self.assertEqual(extract_answer("After weighing all factors:\n**ANSWER: ALL**"), "ALL")
        self.assertEqual(extract_answer("Based on this, my recommendation is:\nFramework Laptop 13"), "framework_laptop_13_amd_ai300")
        self.assertEqual(extract_answer("None of these laptops have 70GB+ VRAM.\nNONE"), "NONE")
        self.assertEqual(extract_answer("Every single one can run web docs.\nALL"), "ALL")

    def test_grader_evaluation(self):
        """Test full test case grading logic with simulated valid answers."""
        simulated_perfect_run = {}
        for t in self.tasks:
            if t["id"] == "persona_10_audiophile_best_audio":
                simulated_perfect_run[t["id"]] = (
                    "The MacBook Pro features an integrated hardware DAC matching Apple dongle quality.\n"
                    "ANSWER: apple_macbook_pro_14_m5_pro"
                )
            else:
                simulated_perfect_run[t["id"]] = f"Based on the analysis:\nANSWER: {t['expected']}"

        results = grade_all(self.tasks, simulated_perfect_run)
        for tid, res in results.items():
            self.assertTrue(res["passed"], f"Expected task {tid} to pass, but failed: {res}")


if __name__ == "__main__":
    unittest.main()
