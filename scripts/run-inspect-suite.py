"""Run the pinned suite, recording durable progress for the web console."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.log import read_eval_log

ROOT = Path(__file__).resolve().parents[1]


def case_score(kind: str, case_id: str, run_id: str) -> tuple[bool | None, int | None]:
    directory = ROOT / 'artifacts/inspect' / ('selected' if kind == 'smoke' else 'ha') / run_id
    samples = []
    for path in directory.glob('*.eval'):
        samples.extend(sample for sample in (read_eval_log(path).samples or []) if kind == 'smoke' or sample.id == case_id)
    if len(samples) != (2 if kind == 'smoke' else 1):
        return None, None
    values = [score.value for sample in samples for score in (sample.scores or {}).values()]
    if any(not sample.scores for sample in samples):
        return None, None
    passed = all(value in ('C', True, 1) for value in values)
    calls = sum(event.event == 'model' for sample in samples for event in sample.events)
    return passed, calls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('freetoken', 'openrouter', 'compatible'), required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--base-url', default='')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--progress-file', required=True)
    parser.add_argument('--cap-usd', type=float)
    args = parser.parse_args()
    if args.source == 'openrouter':
        if not os.environ.get('OPENROUTER_API_KEY'):
            parser.error('OPENROUTER_API_KEY is missing.')
        if args.cap_usd is None or not 0 < args.cap_usd <= 20:
            parser.error('Confirm an active OpenRouter workspace cap between $0 and $20.')
    cases = json.loads((ROOT / 'tasks/inspect-ha-cases.json').read_text())
    entries = [('smoke', 'Pinned smoke set', 'smoke')]
    entries.extend((row['id'], row['name'], 'ha') for row in cases)
    completed = []

    def update(phase: str, current: str | None, message: str) -> None:
        data = {'phase': phase, 'currentCaseId': current, 'completedCases': completed,
                'completedCount': len(completed), 'totalCases': len(entries), 'message': message,
                'updatedAt': datetime.now(timezone.utc).isoformat()}
        destination = Path(args.progress_file)
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(data) + '\n')
        temporary.replace(destination)

    failures = 0
    update('preparing', None, 'Preparing pinned suite')
    for case_id, name, kind in entries:
        update('running', case_id, f'Running {name}')
        if kind == 'smoke':
            command = [sys.executable, str(ROOT / 'scripts/run-inspect-selected.py'), '--source', args.source,
                       '--model', args.model, '--variant', 'base', '--max-calls', '2', '--run-id', args.run_id]
            if args.base_url:
                command.extend(['--base-url', args.base_url])
        else:
            command = [sys.executable, str(ROOT / 'scripts/run-inspect-ha-pilot.py'), '--case', case_id,
                       '--source', args.source, '--model', args.model,
                       '--run-id', args.run_id, '--progress-file', args.progress_file]
            if args.base_url:
                command.extend(['--base-url', args.base_url])
        if args.source == 'openrouter':
            command.extend(['--cap-usd', str(args.cap_usd)])
        try:
            result = subprocess.run(command, cwd=ROOT, check=False)
            return_code = result.returncode
        except OSError:
            return_code = 127
        state = 'complete' if return_code == 0 else 'failed'
        if state == 'failed':
            failures += 1
        item = {'caseId': case_id, 'status': state,
                'message': None if state == 'complete' else f'{name} could not complete (exit status {return_code}).'}
        if state == 'complete':
            passed, calls = case_score(kind, case_id, args.run_id)
            if passed is not None:
                item.update({'passed': passed, 'modelCalls': calls})
        completed.append(item)
        update('running', None if len(completed) == len(entries) else entries[len(completed)][0],
               f'{len(completed)} of {len(entries)} cases finished')
    update('exporting', None, 'Exporting Inspect results')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
