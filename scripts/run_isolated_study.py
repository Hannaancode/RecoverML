"""Run a fresh extended study away from synchronized open-file streams.

Only closed output files are copied to the requested destination. Failed runs
remain in their disclosed temporary directory for inspection.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', choices=['eyeai', 'gigabyte'])
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=Path('work/stare'))
    args = parser.parse_args()
    if args.destination.exists():
        parser.error('Destination must be new so earlier evidence is preserved')
    base = Path(tempfile.mkdtemp(prefix='recoverml_' + args.study + '_'))
    output = base / 'results'
    print('Study files and logs: ' + str(base), flush=True)
    python = sys.executable
    if args.study == 'eyeai':
        commands = [
            [python, '-m', 'recoverml.eyeai_experiment', '--config',
             'configs/eyeai_rebuild_oct15.json', '--dataset', str(args.dataset),
             '--output', str(output)],
            [python, 'scripts/analyze_eyeai.py', str(output)],
        ]
    else:
        commands = [
            [python, 'scripts/gigabyte_history.py', '--protocol',
             'configs/gigabyte_letter_oct15.json', '--output', str(output),
             '--work', str(base / 'payloads')],
            [python, 'scripts/analyze_gigabyte_history.py', str(output),
             '--verify-payloads', str(base / 'payloads')],
        ]
    for index, command in enumerate(commands):
        with (base / ('phase_' + str(index) + '.txt')).open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise SystemExit('Study stopped and its evidence remains at ' + str(base))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(output, args.destination)
    print('Verified closed results copied to ' + str(args.destination), flush=True)


if __name__ == '__main__':
    main()
