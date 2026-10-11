"""Run the pinned local/private suite, recording durable progress for the web console."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('freetoken', 'compatible'), required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--base-url', default='')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--progress-file', required=True)
    args = parser.parse_args()
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
                       '--source', args.source, '--model', args.model, '--base-url', args.base_url,
                       '--run-id', args.run_id, '--progress-file', args.progress_file]
        try:
            result = subprocess.run(command, cwd=ROOT, check=False)
            return_code = result.returncode
        except OSError:
            return_code = 127
        state = 'complete' if return_code == 0 else 'failed'
        if state == 'failed':
            failures += 1
        completed.append({'caseId': case_id, 'status': state,
                          'message': None if state == 'complete' else f'{name} could not complete (exit status {return_code}).'})
        update('running', None if len(completed) == len(entries) else entries[len(completed)][0],
               f'{len(completed)} of {len(entries)} cases finished')
    update('exporting', None, 'Exporting Inspect results')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
