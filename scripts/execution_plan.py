"""Validate fixture snapshots and enforce exact model-generation budgets at launch."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("base", "careful")


@dataclass(frozen=True)
class SmokeCase:
    id: str
    prompt: str
    expected: str
    category: str


@dataclass(frozen=True)
class HaCase:
    id: str
    name: str
    max_model_calls: int
    manifest_json: str

    def to_dict(self) -> dict:
        return json.loads(self.manifest_json)


@dataclass(frozen=True)
class LaptopCase:
    id: str
    prompt: str
    expected: str
    category: str


@dataclass(frozen=True)
class ExecutionPlan:
    variants: tuple[str, ...]
    smoke_cases: tuple[SmokeCase, ...]
    ha_cases: tuple[HaCase, ...]
    laptop_cases: tuple[LaptopCase, ...] = ()

    @property
    def smoke_calls(self) -> int:
        return len(self.smoke_cases) * len(self.variants)

    @property
    def laptop_calls(self) -> int:
        return len(self.laptop_cases)

    @property
    def max_calls(self) -> int:
        return self.smoke_calls + sum(case.max_model_calls for case in self.ha_cases) + self.laptop_calls

    @property
    def sample_ids(self) -> tuple[str, ...]:
        return tuple(
            [f"{variant}:{case.id}" for variant in self.variants for case in self.smoke_cases]
            + [case.id for case in self.laptop_cases]
        )

    def ha_case(self, case_id: str) -> dict:
        for case in self.ha_cases:
            if case.id == case_id:
                return case.to_dict()
        raise ValueError(f"HA case {case_id!r} is absent from the frozen plan.")

    def to_dict(self) -> dict:
        data = {
            "version": 1,
            "variants": list(self.variants),
            "smokeCases": [vars(case) for case in self.smoke_cases],
            "haCases": [case.to_dict() for case in self.ha_cases],
            "sampleIds": list(self.sample_ids),
            "smokeCalls": self.smoke_calls,
            "maxCalls": self.max_calls,
        }
        if self.laptop_cases:
            data["laptopCases"] = [vars(case) for case in self.laptop_cases]
            data["laptopCalls"] = self.laptop_calls
        return data


def _rows(value: Any, label: str, *, empty: bool = False) -> list[dict]:
    if not isinstance(value, list) or (not empty and not value) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{label} must be a {'JSON array' if empty else 'nonempty JSON array'} of objects.")
    return value


def _string(row: dict, field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a nonempty string.")
    return value


def _make_plan(variants: Any, smoke: Any, ha: Any, laptop: Any = None) -> ExecutionPlan:
    if not isinstance(variants, list) or not variants or len(set(map(str, variants))) != len(variants) or any(
        variant not in VARIANTS for variant in variants
    ):
        raise ValueError("variants must contain distinct base/careful values.")
    cases = []
    seen = set()
    for row in _rows(smoke, "Smoke fixture", empty=bool(ha or laptop)):
        if set(row) != {"id", "prompt", "expected", "category"}:
            raise ValueError("Smoke fixture rows require exactly id, prompt, expected, category.")
        case = SmokeCase(*(_string(row, key, "Smoke fixture") for key in ("id", "prompt", "expected", "category")))
        if case.id in seen:
            raise ValueError(f"Duplicate smoke sample ID: {case.id}")
        seen.add(case.id)
        cases.append(case)
    ha_cases = []
    seen.clear()
    if not isinstance(ha, list) or any(not isinstance(row, dict) for row in ha):
        raise ValueError("HA fixture must be a JSON array of objects.")
    for row in ha:
        case_id = _string(row, "id", "HA fixture")
        name = _string(row, "name", "HA fixture")
        for key in ("prompt", "target", "category", "fixture"):
            _string(row, key, "HA fixture")
        calls = row.get("max_model_calls")
        if type(calls) is not int or not 1 <= calls <= 100:
            raise ValueError(f"HA fixture {case_id}: max_model_calls must be an integer from 1 to 100.")
        for key in ("initial", "expected", "action"):
            if not isinstance(row.get(key), dict):
                raise ValueError(f"HA fixture {case_id}: {key} must be an object.")
        for key in ("initial", "expected"):
            if not row[key] or any(not isinstance(entity, str) or "." not in entity or not isinstance(state, dict)
                                   for entity, state in row[key].items()):
                raise ValueError(f"HA fixture {case_id}: {key} requires entity-to-state assertions.")
        action = row["action"]
        if (not all(isinstance(action.get(key), str) and action[key] for key in ("domain", "service"))
                or not isinstance(action.get("data"), dict)
                or not isinstance(action["data"].get("entity_id"), str)
                or action["data"]["entity_id"] not in row["expected"]):
            raise ValueError(f"HA fixture {case_id}: action requires a service and expected entity target.")
        if "require_search" in row and type(row["require_search"]) is not bool:
            raise ValueError(f"HA fixture {case_id}: require_search must be boolean.")
        reads = row.get("require_initial_read", [])
        if not isinstance(reads, list) or any(not isinstance(entity, str) or entity not in row["initial"] for entity in reads):
            raise ValueError(f"HA fixture {case_id}: initial reads must reference pinned initial entities.")
        if case_id in seen or case_id in {item.id for item in cases}:
            raise ValueError(f"Duplicate sample ID: {case_id}")
        seen.add(case_id)
        ha_cases.append(HaCase(case_id, name, calls, json.dumps(row, sort_keys=True, separators=(",", ":"))))

    laptop_cases = []
    if laptop:
        for row in _rows(laptop, "Laptop fixture", empty=True):
            cid = _string(row, "id", "Laptop fixture")
            prompt = row.get("prompt") or row.get("persona")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("Laptop fixture.prompt must be a nonempty string.")
            expected = _string(row, "expected", "Laptop fixture")
            cat = row.get("category", "laptop_shopping")
            if not isinstance(cat, str) or not cat.strip():
                cat = "laptop_shopping"
            laptop_cases.append(LaptopCase(cid, prompt, expected, cat))

    if not cases and not ha_cases and not laptop_cases:
        raise ValueError("Execution plan must contain at least one case.")
    return ExecutionPlan(tuple(variants), tuple(cases), tuple(ha_cases), tuple(laptop_cases))


def build_plan(variant: str = "base", *, suite: bool = False, case_id: str | None = None,
               smoke_file: Path | None = None, ha_file: Path | None = None,
               laptop_file: Path | None = None, include_laptops: bool = False) -> ExecutionPlan:
    """Build a validated plan: ``smoke``, ``all``, ``smart_home``, ``laptop``, or one case ID."""
    if variant not in (*VARIANTS, "both"):
        raise ValueError("variant must be base, careful, or both.")
    selected = case_id if case_id is not None else ("all" if suite else "smoke")
    smoke_path = smoke_file or ROOT / "tasks/smoke.json"
    ha_path = ha_file or ROOT / "tasks/inspect-ha-cases.json"
    laptop_path = laptop_file or ROOT / "tasks/laptop-shopping.json"

    selected_parts = set(selected.split(","))

    try:
        smoke = json.loads(smoke_path.read_text()) if (selected in ("smoke", "all") or "smoke" in selected_parts) else []
        ha_rows = json.loads(ha_path.read_text()) if (selected in ("all", "smart_home", "ha") or "smart_home" in selected_parts or "ha" in selected_parts) else []
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read execution fixture: {error}") from error

    if selected in ("smoke", "all") or "smoke" in selected_parts:
        _rows(smoke, "Smoke fixture")

    if selected not in ("smoke", "all", "smart_home", "ha", "laptop", "laptop_shopping") and not any(p in ("smoke", "smart_home", "ha", "laptop", "laptop_shopping") for p in selected_parts):
        try:
            ha_all = json.loads(ha_path.read_text())
            ha_rows = [row for row in ha_all if row.get("id") == selected]
        except (OSError, json.JSONDecodeError):
            ha_rows = []
        if not ha_rows:
            raise ValueError(f"Unknown HA case ID: {selected}")

    laptop_rows = []
    if (include_laptops or selected in ("all_with_laptops", "laptop", "laptop_shopping") or "laptop" in selected_parts or "laptop_shopping" in selected_parts) and laptop_path.exists():
        laptop_rows = json.loads(laptop_path.read_text())

    return _make_plan(list(VARIANTS) if variant == "both" else [variant], smoke, ha_rows, laptop=laptop_rows)

def load_plan(path: Path) -> ExecutionPlan:
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid execution plan JSON at {path}: {error}") from error
    allowed_standard = {"version", "variants", "smokeCases", "haCases", "sampleIds", "smokeCalls", "maxCalls"}
    allowed_with_laptops = {"version", "variants", "smokeCases", "haCases", "laptopCases", "sampleIds", "smokeCalls", "laptopCalls", "maxCalls"}
    if not isinstance(data, dict) or (set(data) != allowed_standard and set(data) != allowed_with_laptops) or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Invalid execution plan: expected version 1 with complete plan fields.")
    laptop = data.get("laptopCases", [])
    plan = _make_plan(data["variants"], data["smokeCases"], data["haCases"], laptop=laptop)
    if data != plan.to_dict():
        raise ValueError("Invalid execution plan: sample IDs or model-call limits do not match frozen fixtures.")
    return plan


def save_plan(path: Path, plan: ExecutionPlan) -> None:
    """Serialize validated rows so child tasks never reload a changing fixture."""
    Path(path).write_text(json.dumps(plan.to_dict(), indent=2) + "\n")


def require_calls(plan: ExecutionPlan, confirmed: int, *, scope: str = "plan") -> None:
    if type(confirmed) is not int or confirmed != plan.max_calls:
        raise ValueError(f"{scope} requires exactly {plan.max_calls} confirmed model calls; received {confirmed}.")


def run_id(value: str | None = None) -> str:
    result = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") if value is None or value == "" else value
    if not isinstance(result, str) or not result.isascii() or not result.isdigit() or not 14 <= len(result) <= 20:
        raise ValueError("Run ID must be a 14–20 digit UTC timestamp.")
    return result


def validate_request(payload: dict) -> dict:
    """Validate the web/worker JSON boundary; return only non-secret fields."""
    from scripts.run_inspect_settings import compatible_base, is_free_model, local_config, validate_cap, validate_model

    if not isinstance(payload, dict):
        raise ValueError("Settings request must be a JSON object.")
    allowed = {"source", "model", "variant", "caseId", "baseUrl", "capUsd", "capConfirmed", "maxCalls", "runId"}
    if set(payload) - allowed:
        raise ValueError(f"Unknown settings fields: {', '.join(sorted(set(payload) - allowed))}")
    source = payload.get("source")
    if source not in ("freetoken", "openrouter", "compatible"):
        raise ValueError("source must be freetoken, openrouter, or compatible.")
    model = validate_model(payload.get("model"))
    variant = payload.get("variant", "base")
    case_id = payload.get("caseId", "all")
    if not isinstance(case_id, str):
        raise ValueError("caseId must be a string.")
    if case_id not in ("smoke",) and variant != "base":
        raise ValueError("All-suite and multi-case selections require the base prompt.")
    include_laptops = (case_id == "all" and (payload.get("maxCalls") == 39 or payload.get("maxCalls") is None)) or case_id in ("all_with_laptops", "laptop", "laptop_shopping") or "laptop" in case_id
    plan = build_plan(variant, case_id=case_id, include_laptops=include_laptops)
    if payload.get("maxCalls") is not None:
        require_calls(plan, payload["maxCalls"])
    identifier = run_id(payload.get("runId"))
    if source == "openrouter":
        if not is_free_model(model) and payload.get("capConfirmed") is not True:
            raise ValueError("Confirm the active OpenRouter workspace cap before a paid run.")
        cap = None if is_free_model(model) and payload.get("capUsd") is None else validate_cap(payload.get("capUsd"))
        base = ""
    else:
        cap = None
        supplied_base = payload.get("baseUrl", "")
        if source == "freetoken" and not supplied_base:
            supplied_base, _ = local_config()
        if not isinstance(supplied_base, str):
            raise ValueError("baseUrl must be a string.")
        base = compatible_base(supplied_base, loopback_only=source == "freetoken")
    settings = {"source": source, "model": model, "baseUrl": base, "capUsd": cap,
                "runId": identifier, "variant": variant, "caseId": case_id, "maxCalls": plan.max_calls}
    return {"settings": settings, "plan": plan.to_dict()}


def describe() -> dict:
    """Non-secret configuration and case catalog for the console."""
    from scripts.run_inspect_settings import local_config, read_env_file

    plan = build_plan(case_id="all")
    try:
        local_base, local_model = local_config()
    except ValueError:
        local_base, local_model = "", ""
    cases = [{"id": case.id, "name": case.id.replace("_", " ").capitalize(),
              "category": case.category, "suite": "smoke", "fixture": "tasks/smoke.json",
              "maxModelCalls": 1} for case in plan.smoke_cases]
    cases.extend({"id": case.id, "name": case.name, "category": case.to_dict().get("category", "smart_home"),
                  "suite": "ha", "fixture": case.to_dict().get("fixture", "tasks/inspect-ha-cases.json"), "maxModelCalls": case.max_model_calls}
                 for case in plan.ha_cases if case.id != "laptop_shopping")
    laptop_file = ROOT / "tasks/laptop-shopping.json"
    if laptop_file.exists():
        laptop_cases = json.loads(laptop_file.read_text(encoding="utf-8"))
        cases.extend({"id": item["id"], "name": item.get("title", item["id"]), "category": "laptop_shopping",
                      "suite": "laptop", "fixture": "tasks/laptop-shopping.json", "maxModelCalls": 1}
                     for item in laptop_cases)
    return {"settings": {"localBase": local_base, "localModel": local_model,
                         "openrouterReady": bool(os.environ.get("OPENROUTER_API_KEY") or read_env_file().get("OPENROUTER_API_KEY"))},
            "cases": cases, "maxCalls": sum(c["maxModelCalls"] for c in cases)}


def main() -> None:
    """Print safe, validated JSON for server callers; never include credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--request-json", action="store_true", help="Read a settings object from stdin")
    parser.add_argument("--source", choices=("freetoken", "openrouter", "compatible"))
    parser.add_argument("--model")
    parser.add_argument("--variant", choices=(*VARIANTS, "both"), default="base")
    parser.add_argument("--suite", action="store_true")
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    try:
        if args.describe:
            output = describe()
        elif args.request_json:
            try:
                payload = json.load(sys.stdin)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid settings JSON: {error}") from error
            output = validate_request(payload)
        else:
            output = validate_request({"source": args.source, "model": args.model, "variant": args.variant,
                                       "caseId": args.case_id or ("all" if args.suite else "smoke"),
                                       "baseUrl": args.base_url, "capUsd": args.cap_usd,
                                       "capConfirmed": args.cap_usd is not None,
                                       "maxCalls": args.max_calls, "runId": args.run_id})
    except (ValueError, OSError) as error:
        if args.request_json or args.describe:
            print(json.dumps({"error": str(error)}))
            raise SystemExit(1) from error
        parser.error(str(error))
    print(json.dumps(output))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
