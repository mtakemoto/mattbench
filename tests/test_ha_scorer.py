"""Final state and successful tool observations jointly determine HA scores."""

import json
import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from inspect_pilot import ha_cases, synthetic_ha_state

import test_ha_trace as traces

class HaScorerTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_state_cannot_substitute_for_a_valid_trace_and_vice_versa(self):
        case = ha_cases()["mxz_coordinator_target"]
        good_trace = traces.successful_trace()
        for name, messages, temperature, value, state_correct, trace_valid in (
            ("valid", good_trace, 68, 1, True, True),
            ("missing_readback", good_trace[:-1], 68, 0, True, False),
            ("wrong_final_state", good_trace, 70, 0, False, True),
        ):
            with self.subTest(name=name):
                responses = [
                    subprocess.CompletedProcess([], 0, stdout=json.dumps({"attributes": {"temperature": temperature}})),
                    subprocess.CompletedProcess([], 0, stdout=json.dumps({"attributes": {"temperature": 74}})),
                ]
                with patch.dict(os.environ, {
                    "MATTBENCH_SYNTHETIC_HA_CONTAINER": "fictional-ha",
                    "MATTBENCH_SYNTHETIC_HA_TOKEN": "disposable-token",
                }), patch("inspect_pilot.run_bounded_async", AsyncMock(side_effect=responses)):
                    score = await synthetic_ha_state(case)(SimpleNamespace(messages=messages), None)
                self.assertEqual(score.value, value)
                self.assertEqual(score.metadata["state_correct"], state_correct)
                self.assertEqual(score.metadata["trace_valid"], trace_valid)


if __name__ == "__main__":
    unittest.main()
