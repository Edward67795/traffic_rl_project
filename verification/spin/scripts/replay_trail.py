#!/usr/bin/env python3
"""Replay a saved SPIN witness with identical flags after checking model hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

SPIN = Path(__file__).resolve().parents[1]
REPO = SPIN.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path, help='Run directory containing metadata.json and trail.txt')
    args = parser.parse_args()
    metadata = json.loads((args.evidence / 'metadata.json').read_text())
    for name in ('controller.pml', 'properties.pml'):
        relative = f'verification/spin/models/{name}'
        actual = hashlib.sha256((REPO / relative).read_bytes()).hexdigest()
        if actual != metadata['model_sha256'][relative]:
            parser.error(f'{relative} changed since this run; rerun verification before replay')
    with tempfile.TemporaryDirectory(prefix='traffic-spin-replay-') as directory:
        build = Path(directory)
        for name in ('controller.pml', 'properties.pml'):
            shutil.copyfile(SPIN / 'models' / name, build / name)
        shutil.copyfile(args.evidence / 'trail.txt', build / 'controller.pml.trail')
        result = subprocess.run(['spin', '-T', *metadata['flags'], '-t', '-k',
                                 'controller.pml.trail', 'controller.pml'], cwd=build,
                                timeout=30)
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
