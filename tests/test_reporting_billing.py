"""Offline billing and summary publication regressions."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_script(filename):
    spec = importlib.util.spec_from_file_location(filename.replace('-', '_'), ROOT / 'scripts' / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load_script('inspect-report.py')
billing = load_script('openrouter-billing.py')


def fake_log(eval_id, sample_id, response_ids, score=None):
    sample = SimpleNamespace(
        id=sample_id,
        events=[SimpleNamespace(event='model', output=SimpleNamespace(response_id=value)) for value in response_ids],
        scores={'pi_scope': score} if score is not None else {}, metadata={},
        model_usage={'example': SimpleNamespace(model_dump=lambda **_: {'input_tokens': 1, 'total_cost': 9.0})},
        output=SimpleNamespace(model='example'), total_time=0.1, started_at='now',
    )
    info = SimpleNamespace(eval_id=eval_id, model='openai-api/openrouter/example',
                           task='example', run_id='run', task_version=1,
                           model_generate_config=SimpleNamespace(model_dump=lambda **_: {}),
                           model_args={}, packages={})
    return SimpleNamespace(eval=info, samples=[sample], status='success')


class BillingTests(unittest.TestCase):
    def collect(self, groups, results):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / 'artifacts/inspect/selected/20261011010203'
            directory.mkdir(parents=True)
            logs = {}
            for index, attempts in enumerate(groups):
                path = directory / f'{index}.eval'
                path.write_text('fixture')
                logs[path] = fake_log(f'eval-{index}', f'sample-{index}', attempts)

            def lookup(gen_id, _key):
                result = results[gen_id]
                if isinstance(result, Exception):
                    raise result
                return result

            argv = ['openrouter-billing.py', '--run-id', '20261011010203']
            with patch.object(billing, 'ROOT', root), patch.object(billing, 'read_eval_log', side_effect=lambda path: logs[path]), patch.object(billing, 'generation', side_effect=lookup), patch.object(sys, 'argv', argv), patch.dict(billing.os.environ, {'OPENROUTER_API_KEY': 'offline'}, clear=True):
                result = billing.main()
            payload = json.loads((root / 'artifacts/inspect/openrouter-billing/20261011010203.json').read_text())
            return result, payload

    def test_every_suite_directory_is_billed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logs = {}
            for index, suite in enumerate(('selected', 'laptops')):
                path = root / 'artifacts/inspect' / suite / '20261011010203' / f'{index}.eval'
                path.parent.mkdir(parents=True)
                path.write_text('fixture')
                logs[path] = fake_log(f'eval-{index}', f'sample-{index}', [f'gen-{index}'])
            argv = ['openrouter-billing.py', '--run-id', '20261011010203']
            lookup = lambda gen_id, _key: {'cost_usd': 0.1, 'provider': 'p', 'model': 'm'}
            with patch.object(billing, 'ROOT', root), patch.object(billing, 'read_eval_log', side_effect=lambda path: logs[path]), patch.object(billing, 'generation', side_effect=lookup), patch.object(sys, 'argv', argv), patch.dict(billing.os.environ, {'OPENROUTER_API_KEY': 'offline'}, clear=True):
                billing.main()
            payload = json.loads((root / 'artifacts/inspect/openrouter-billing/20261011010203.json').read_text())
        self.assertEqual(sorted(row['sample_id'] for row in payload['rows']), ['sample-0', 'sample-1'])

    def test_missing_id_does_not_claim_exact_charge(self):
        status, data = self.collect([['gen-one', None]], {'gen-one': {'cost_usd': 0.2, 'provider': 'p', 'model': 'm'}})
        self.assertEqual(status, 1)
        self.assertEqual((data['generation_attempts'], data['available_ids'], data['queried_ids']), (2, 1, 1))
        self.assertEqual(data['unknown_attempts'], 1)
        self.assertIsNone(data['cost_usd'])
        self.assertEqual(data['partial_cost_usd'], 0.2)
        self.assertIsNone(data['rows'][0]['cost_usd'])

    def test_lookup_failure_is_unknown_and_not_zero(self):
        status, data = self.collect([['gen-one']], {'gen-one': ValueError('unavailable')})
        self.assertEqual(status, 1)
        self.assertEqual((data['lookup_failures'], data['unknown_attempts'], data['billed_calls']), (1, 1, 0))
        self.assertIsNone(data['cost_usd'])
        self.assertEqual(data['partial_cost_usd'], 0)

    def test_repeated_id_across_samples_charged_once(self):
        status, data = self.collect([['gen-one', 'gen-one'], ['gen-one']], {'gen-one': {'cost_usd': 0.4, 'provider': 'p', 'model': 'm'}})
        self.assertEqual(status, 0)
        self.assertEqual(data['generation_attempts'], 3)
        self.assertEqual(data['billed_calls'], 1)
        self.assertEqual(data['cost_usd'], 0.4)
        self.assertEqual([row['cost_usd'] for row in data['rows']], [0.4, 0])
        self.assertEqual(data['rows'][1]['shared_generation_ids'], 1)

    def test_fully_accounted_run_reports_exact_cost(self):
        status, data = self.collect([['gen-one', 'gen-two']], {
            'gen-one': {'cost_usd': 0.1, 'provider': 'p', 'model': 'm'},
            'gen-two': {'cost_usd': 0.2, 'provider': 'p', 'model': 'm'},
        })
        self.assertEqual(status, 0)
        self.assertTrue(data['complete'])
        self.assertEqual(data['cost_usd'], 0.3)
        self.assertIsNone(data['partial_cost_usd'])
        self.assertEqual(data['rows'][0]['cost_usd'], 0.3)

    def test_billing_publish_failure_retains_old_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / 'artifacts/inspect/openrouter-billing/20261011010203.json'
            destination.parent.mkdir(parents=True)
            destination.write_text('{"previous":true}\n')
            argv = ['openrouter-billing.py', '--run-id', '20261011010203']
            with patch.object(billing, 'ROOT', root), patch.object(sys, 'argv', argv), patch.dict(billing.os.environ, {'OPENROUTER_API_KEY': 'offline'}, clear=True), patch.object(Path, 'replace', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    billing.main()
            self.assertEqual(json.loads(destination.read_text()), {'previous': True})
            self.assertEqual(list(destination.parent.glob('*.tmp')), [])


class ReportTests(unittest.TestCase):
    def test_every_suite_directory_carries_its_launcher_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suite in ('selected', 'ha', 'laptops', 'some_future_suite'):
                with self.subTest(suite=suite):
                    path = root / suite / '20261019204001210372' / 'x.eval'
                    with patch.object(report, 'LOG_DIR', root), patch.object(report, 'read_eval_log', return_value=fake_log('e', 's', [])):
                        row = report.export_eval(path, {}, {})[0]
                    self.assertEqual(row['launcher_run_id'], '20261019204001210372')

    def test_legacy_pi_keyword_scores_are_not_semantic_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "legacy.eval"
            for value in (0, 1):
                with self.subTest(legacy_score=value):
                    log = fake_log("old", "scope", [], SimpleNamespace(value=value, metadata={}))
                    log.eval.task = "pi_scope"
                    with patch.object(report, "LOG_DIR", root), patch.object(report, "read_eval_log", return_value=log):
                        row = report.export_eval(path, {}, {})[0]
                    self.assertIsNone(row["passed"])
                    self.assertEqual(row["scores"]["pi_scope"], value)
                    self.assertTrue(row["score_metadata"]["instruction_scope_state"]["semantic_review_required"])

    def test_legacy_billing_is_not_treated_as_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'old.json'
            path.write_text(json.dumps({'rows': [{
                'eval_id': 'old', 'sample_id': 's', 'cost_usd': 0.7,
                'billed_calls': 1, 'expected_calls': 1,
                'providers': [], 'routed_models': [],
            }]}))
            row = report.read_billing_rows(path)[0]
            self.assertFalse(row['complete'])
            self.assertIsNone(row['cost_usd'])
            self.assertEqual(row['partial_cost_usd'], 0.7)
            self.assertTrue(row['accounting_legacy'])

    def test_valid_artifacts_survive_corrupt_json_and_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bdir, tdir = root / 'openrouter-billing', root / 'ha-timing'
            bdir.mkdir()
            tdir.mkdir()
            good_bill = {'rows': [{'eval_id': 'good', 'sample_id': 's', 'complete': False,
                                    'cost_usd': None, 'partial_cost_usd': 0.2,
                                    'generation_attempts': 2, 'available_ids': 1,
                                    'queried_ids': 1, 'billed_calls': 1,
                                    'unknown_attempts': 1, 'lookup_failures': 0,
                                    'providers': ['p'], 'routed_models': ['m']}]}
            (bdir / 'good.json').write_text(json.dumps(good_bill))
            (bdir / 'bad.json').write_text('{')
            (bdir / 'schema.json').write_text('{"rows":{}}')
            (tdir / 'good.json').write_text('{"eval_ids":["good"],"setup_seconds":1}')
            (tdir / 'bad.json').write_text('{')
            (tdir / 'schema.json').write_text('{"eval_ids":"good"}')
            eval_dir = root / 'selected' / '20261011010203'
            eval_dir.mkdir(parents=True)
            (eval_dir / 'good.eval').write_text('valid')
            (eval_dir / 'bad.eval').write_text('invalid')
            score = SimpleNamespace(value=0, metadata={
                'objective_checks_passed': True, 'semantic_review_required': True,
                'semantic_review_status': 'pending', 'semantic_review_reason': 'Manual review required.'
            })

            def read_log(path):
                if path.name == 'bad.eval':
                    raise ValueError('private error details')
                return fake_log('good', 's', ['gen-one'], score)

            with patch.object(report, 'LOG_DIR', root), patch.object(report, 'read_eval_log', side_effect=read_log):
                report.main()
            summary = json.loads((root / 'summary.json').read_text())
            self.assertEqual(len(summary['rows']), 1)
            self.assertTrue(summary['incomplete_report'])
            self.assertEqual(len(summary['warnings']), 6)
            self.assertNotIn('private', json.dumps(summary['warnings']))
            row = summary['rows'][0]
            self.assertIsNone(row['passed'])
            self.assertTrue(row['score_metadata']['pi_scope']['objective_checks_passed'])
            self.assertEqual(row['usage']['example']['total_cost'], 9.0)
            self.assertEqual(row['billing']['partial_cost_usd'], 0.2)
            self.assertEqual(row['run_timing']['setup_seconds'], 1)

    def test_complete_billing_overrides_estimated_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bill = root / 'openrouter-billing'
            bill.mkdir()
            (bill / 'ok.json').write_text(json.dumps({'rows': [{
                'eval_id': 'good', 'sample_id': 's', 'complete': True,
                'cost_usd': 0.1, 'partial_cost_usd': None,
                'generation_attempts': 1, 'available_ids': 1, 'queried_ids': 1,
                'billed_calls': 1, 'unknown_attempts': 0, 'lookup_failures': 0,
                'providers': [], 'routed_models': [],
            }]}))
            eval_dir = root / 'selected' / '20261011010203'
            eval_dir.mkdir(parents=True)
            (eval_dir / 'ok.eval').write_text('valid')
            with patch.object(report, 'LOG_DIR', root), patch.object(report, 'read_eval_log', return_value=fake_log('good', 's', ['gen-one'])):
                report.main()
            row = json.loads((root / 'summary.json').read_text())['rows'][0]
            self.assertEqual(row['usage']['example']['total_cost'], 0.1)
            self.assertTrue(row['billing']['complete'])


if __name__ == '__main__':
    unittest.main()
