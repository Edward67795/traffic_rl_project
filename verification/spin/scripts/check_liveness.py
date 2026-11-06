#!/usr/bin/env python3
"""L2 positive/negative controls and full-model fairness-feasibility witnesses.

Auxiliary checks are not shared property results. A FAIL of !FAIR_INPUT witnesses
that the fairness premise is realizable; it is not a controller defect.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from run_spin import SPIN, REPO, classify
from liveness import analyze_cycle, reference_lasso


def execute_model(source, flags, directory):
    directory.mkdir(parents=True)
    for path in (SPIN / 'models').glob('*.pml'):
        shutil.copyfile(path, directory / path.name)
    (directory / 'check.pml').write_text(source)
    records = []
    output = ''
    for name, command in [
        ('generate', ['spin', *flags, '-a', 'check.pml']),
        ('compile', ['cc', '-O2', '-DMEMLIM=512', '-o', 'pan', 'pan.c']),
        ('verify', ['./pan', '-a', '-m100000', '-w18', '-b']),
    ]:
        start = time.perf_counter()
        result = subprocess.run(command, cwd=directory, capture_output=True,
                                text=True, timeout=120)
        output = result.stdout + result.stderr
        (directory / (name + '.txt')).write_text(output)
        records.append({'argv': command, 'exit_code': result.returncode,
                        'time_s': time.perf_counter() - start})
        if name != 'verify' and result.returncode:
            raise RuntimeError(output)
    verdict = classify(output, result.returncode)
    replay = ''
    if verdict == 'FAIL':
        result = subprocess.run(['spin', '-T', *flags, '-t', '-k',
                                 'check.pml.trail', 'check.pml'], cwd=directory,
                                capture_output=True, text=True, timeout=30)
        replay = result.stdout + result.stderr
        (directory / 'replay.txt').write_text(replay)
        shutil.copyfile(directory / 'check.pml.trail', directory / 'trail.txt')
    # Keep source, exact logs and text trail, but no generated binaries/pan files.
    for path in directory.iterdir():
        if path.name == 'pan' or path.name.startswith('pan.') or path.suffix == '.trail' or path.name == '_spin_nvr.tmp':
            path.unlink()
    return verdict, replay, records


def fixture_source(sequence, events=True, initial=0):
    steps = []
    for action, eligible, signal in sequence:
        request = ('record_request();' if events else
                   'requested_action = action; request_event = false;')
        steps.append(f'action={action}; phase_duration={10 if eligible else 0}; '
                     f'{request} signal={signal}; '
                     'd_step { observe_second() }; request_event=false;')
    return ('#define MIN_GREEN 10\n#define MAX_GREEN 60\n#define YELLOW_TIME 3\n'
            'byte signal=0; int action=0; int phase_duration=0; int current_phase=0;\n'
            '#include "properties.pml"\n'
            f'init {{ observed={initial}; do :: ' + '\n'.join(steps) + ' od }\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New evidence directory; must not already exist')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output directory already exists; preserve prior evidence')
    args.output.mkdir(parents=True)
    fixtures = [
        ('unfair-ns-starvation', 0, [(0, True, 0)], 'FAIL', True, 0),
        ('unfair-ew-starvation', 0, [(1, True, 2)], 'FAIL', True, 0),
        ('alternating-service', 0, [(0, True, 0), (1, True, 2)], 'PASS', True, 0),
        ('finite-ew-not-infinite', 0, [(0, True, 0)], 'FAIL', True, 2),
        ('request-fair-starvation', 1, [(0, True, 0), (1, False, 0)], 'FAIL', True, 0),
        ('request-fair-service', 1, [(0, True, 0), (1, True, 2)], 'PASS', True, 0),
        ('unfair-premise-vacuity', 1, [(0, True, 0)], 'PASS', True, 0),
        ('eligible-fair-starvation', 2, [(0, True, 0), (1, True, 0)], 'FAIL', True, 0),
        ('eligible-fair-service', 2, [(0, True, 0), (1, True, 2)], 'PASS', True, 0),
        ('ineligible-premise-vacuity', 2, [(0, False, 0), (1, False, 0)], 'PASS', True, 0),
        ('no-phantom-request-events', 1, [(0, True, 0), (1, True, 0)], 'PASS', False, 0),
    ]
    results = []
    for name, mode, sequence, expected, events, initial in fixtures:
        verdict, _, commands = execute_model(fixture_source(sequence, events, initial),
                                             ['-DCHK_L2', f'-DAGENT_FAIRNESS={mode}'],
                                             args.output / name)
        record = {'name': name, 'kind': 'synthetic-ltl-control', 'expected': expected,
                  'actual': verdict, 'matched': expected == verdict, 'commands': commands}
        results.append(record)
        print(name, verdict, 'expected', expected, flush=True)
        if verdict != expected:
            (args.output / 'summary.json').write_text(json.dumps(results, indent=2))
            raise RuntimeError(f'LTL control mismatch: {name}')
    for scenario in ('default', 'y0', 'any', 'L1'):
        for fairness, mode in [('request', 1), ('eligible', 2)]:
            name = f'premise-feasible-{scenario}-{fairness}'
            flags = ['-DCHK_L2', f'-DAGENT_FAIRNESS={mode}', '-DFAIRNESS_FEASIBILITY',
                     f'-DSTATIC_PROGRAM={int(scenario == "L1")}',
                     f'-DYELLOW_TIME={0 if scenario == "y0" else 3}']
            if scenario == 'any':
                flags.append('-DANY_ACTION')
            verdict, replay, commands = execute_model(
                (SPIN / 'models/controller.pml').read_text(), flags, args.output / name)
            if verdict != 'FAIL':
                raise RuntimeError(f'No feasible fairness witness: {name}: {verdict}')
            cycle = analyze_cycle(replay, fairness)
            reference = reference_lasso(REPO, scenario, cycle)
            if not cycle['selected_premise_holds'] or not reference['closed'] or reference['period_time_s'] <= 0:
                raise RuntimeError(f'Invalid feasibility lasso: {name}')
            record = {'name': name, 'kind': 'full-model-fairness-feasibility',
                      'actual_verifier_result': verdict,
                      'meaning': 'Acceptance cycle of !FAIR_INPUT demonstrates a realizable premise',
                      'cycle': cycle, 'reference_lasso': reference, 'commands': commands}
            results.append(record)
            (args.output / name / 'analysis.json').write_text(json.dumps(record, indent=2) + '\n')
            print(name, 'FEASIBLE (acceptance cycle of negated premise)', flush=True)
    summary = {'date_utc': datetime.now(timezone.utc).isoformat(),
               'kind': 'auxiliary-controls-not-shared-property-results',
               'spin': subprocess.check_output(['spin', '-V'], text=True).strip(),
               'sha256': {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [*list((SPIN / 'models').glob('*.pml')), Path(__file__).resolve()]},
               'records': results}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('All 11 LTL controls and 8 full-model fairness-feasibility checks matched.', flush=True)


if __name__ == '__main__':
    main()
