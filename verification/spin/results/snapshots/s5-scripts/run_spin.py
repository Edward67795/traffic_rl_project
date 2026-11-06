#!/usr/bin/env python3
"""Run the implemented v0/v1 verification matrix with one property per exhaustive search.

FAIL denotes a witnessed model violation, not runner failure. The command exits
nonzero for ERROR/UNKNOWN/TIMEOUT or a failed witness reference cross-check.
"""
import argparse
import contextlib
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from liveness import analyze_cycle, reference_lasso

SPIN = Path(__file__).resolve().parents[1]
REPO = SPIN.parents[1]
HEADER = ['tool', 'property', 'version', 'config', 'bound', 'result',
          'ce_length', 'time_s', 'memory_mb', 'notes']
PROPERTIES = ('S1', 'T1', 'T2', 'G1', 'C1', 'G2', 'L1', 'L2')
STAGES = {'S2': PROPERTIES[:5], 'S3': PROPERTIES[5:7], 'S4': ('L2',), 'S5': PROPERTIES}
SCENARIOS = ('default', 'y0', 'any', 'L1')
CASES = {f'{p}-v0-{s}': (p, s) for p in PROPERTIES if p != 'L2' for s in SCENARIOS}
CASES.update({f'L2-v0-{s}-{f}': ('L2', s) for s in SCENARIOS
              for f in ('none', 'request', 'eligible')})
CASE_STAGE = {case: ('S4' if prop == 'L2' else 'S3' if prop in ('G2','L1') else 'S2')
              for case,(prop,_) in CASES.items()}
for prop in PROPERTIES:
    for scenario in ('default','L1'):
        modes = ('none','request','eligible') if prop == 'L2' else (None,)
        for mode in modes:
            case = f'{prop}-v1-{scenario}' + (f'-{mode}' if mode else '')
            CASES[case] = (prop,scenario)
            CASE_STAGE[case] = 'S5'
PARAMETERS = {}
PROBES = {
    'dt7': (7,10,60), 'max61': (5,10,61), 'dt3max16': (3,10,16),
    'min0dt7': (7,0,11), 'min12dt1': (1,12,16), 'delta_gt_max': (12,0,11),
}
for tag,(delta,minimum,maximum) in PROBES.items():
    for version in ('v0','v1'):
        case=f'G2-{version}-default-{tag}'
        CASES[case]=('G2','default'); CASE_STAGE[case]='S5'
        PARAMETERS[case]={'delta':delta,'minimum':minimum,'maximum':maximum,'probe':tag}
STATES = ['GGGgrrrGGGgrrr', 'yyyyrrryyyyrrr', 'rrrrGGgrrrrGGg', 'rrrryyyrrrryyy']


def network_preflight():
    """Validate the codebook and protected G/G conflicts, not permissive g priority."""
    net = REPO / 'networks/single_intersection.net.xml'
    root = ET.parse(net).getroot()
    phases = root.findall("tlLogic[@id='center']/phase")
    if [p.get('state') for p in phases] != STATES:
        raise ValueError('Network states differ from the shared four-code abstraction')
    if [float(p.get('duration')) for p in phases] != [42, 3, 42, 3]:
        raise ValueError('Network durations differ from the fixed static program')
    requests = root.findall("junction[@id='center']/request")
    foes = {int(r.get('index')): r.get('foes') for r in requests}
    links = root.findall("connection[@tl='center']")
    indices = sorted(int(c.get('linkIndex')) for c in links)
    if indices != list(range(14)) or sorted(foes) != indices:
        raise ValueError('Expected 14 one-to-one signal link/request indices')
    if any(len(bits) != 14 for bits in foes.values()):
        raise ValueError('Unexpected foes bit-vector width')
    # As in the existing network checker, link i is interpreted as request i.
    # Record this network-specific mapping assumption explicitly in metadata.
    conflicts = []
    for i in range(14):
        for j in range(14):
            if foes[i][-1-j] != foes[j][-1-i]:
                raise ValueError('Asymmetric foes matrix')
            if i < j and foes[i][-1-j] == '1':
                conflicts.append((i, j))
    for state in STATES:
        if any(state[i] == state[j] == 'G' for i, j in conflicts):
            raise ValueError(f'Protected G/G conflict in {state}')
    return {'sha256': hashlib.sha256(net.read_bytes()).hexdigest(),
            'phase_states': STATES, 'durations': [42, 3, 42, 3],
            'protected_conflicts_checked': len(conflicts),
            'mapping_assumption': 'signal link i corresponds to junction request i',
            'result': 'PASS'}


def classify(output, returncode):
    """Only a concrete selected-property witness can override incomplete search."""
    if re.search(r'max search depth too small|depth limit reached|out of memory|memory limit|MEMLIM bound|cannot allocate',
                 output, re.I):
        return 'UNKNOWN'
    if re.search(r'assertion violated|acceptance cycle', output, re.I):
        return 'FAIL'
    errors = re.search(r'errors:\s*(\d+)', output)
    if returncode != 0 or not errors or int(errors[1]) != 0:
        return 'ERROR'
    if re.search(r'Search not completed|error:|warning:', output, re.I):
        return 'UNKNOWN'
    if 'Full statespace search' not in output or 'bit states' in output.lower():
        return 'UNKNOWN'
    return 'PASS'


def reference_witness(prop, scenario, actions, version="v0", delta=5, minimum=10, maximum=60):
    """Cross-check finite assertion witnesses using the read-only Python reference."""
    ns = {}
    model = REPO / 'verification/esbmc/model'
    for name in ('traci_stub.py', f'env_core_{version}.py'):
        path = model / name
        exec(compile(path.read_text(), str(path), 'exec'), ns)
    ns['STATIC_PROGRAM'] = scenario == 'L1'
    ns['CHK_' + prop] = prop != 'C1'
    ns['MON_YELLOW'] = 0 if scenario == 'y0' else 3
    ns['MON_MIN_GREEN'] = minimum
    ns['MON_MAX_GREEN'] = maximum
    stub = ns['traci']
    env = ns['SumoTrafficEnvCore'](delta, 0 if scenario == 'y0' else 3, minimum, maximum, 3600)
    consumed = 0
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            env.reset()
            for consumed, action in enumerate(actions, 1):
                env.step(action)
                if prop == 'G2':
                    assert env.phase_duration <= env.max_green, 'G2: controller phase_duration exceeds max_green'
                if prop == 'C1':
                    assert env.current_phase in (0, 1), 'C1: phase out of range'
                    assert stub.trafficlight.code == (0 if env.current_phase == 0 else 2), \
                        'C1: displayed state mismatch'
    except AssertionError as error:
        return {'reproduced': True, 'message': str(error), 'time_s': stub.time,
                'decision': consumed, 'phase': env.current_phase,
                'signal': stub.trafficlight.code, 'controller_age': env.phase_duration,
                'observed_green_age': stub.green_len, 'ns_wait': stub.ns_wait,
                'ew_wait': stub.ew_wait,
                'component': ('controller_age' if 'phase_duration exceeds' in str(error)
                              else 'observed_green' if prop == 'G2'
                              else 'directional_wait' if prop == 'L1' else prop)}
    return {'reproduced': False, 'message': 'No finite reference assertion violation'}


def run_case(case_id, prop, scenario, args, network, versions):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    evidence = SPIN / 'results/raw' / f'{case_id}-{stamp}'
    evidence.mkdir(parents=True)
    source_snapshot = evidence / 'models'
    source_snapshot.mkdir()
    for name in ('controller.pml', 'properties.pml'):
        shutil.copyfile(SPIN / 'models' / name, source_snapshot / name)
    version = 'v1' if '-v1-' in case_id else 'v0'
    params=PARAMETERS.get(case_id,{})
    delta=params.get('delta',5); minimum=params.get('minimum',10); maximum=params.get('maximum',60)
    yellow=0 if scenario=='y0' else 3
    flags = [f'-DCHK_{prop}', f'-DVERSION={int(version == "v1")}',
             f'-DDELTA_TIME={delta}', f'-DMIN_GREEN={minimum}', f'-DMAX_GREEN={maximum}',
             f'-DSTATIC_PROGRAM={int(scenario == "L1")}', f'-DYELLOW_TIME={yellow}']
    if scenario == 'any':
        flags.append('-DANY_ACTION')
    config = f'{scenario};fidelity={"L1" if scenario == "L1" else "L0"};dt={delta};y={yellow};min={minimum};max={maximum}'
    if 'probe' in params:
        config += f';probe={params["probe"]}'
    fairness = case_id.rsplit('-', 1)[-1] if prop == 'L2' else None
    if fairness is not None:
        flags.append(f'-DAGENT_FAIRNESS={dict(none=0, request=1, eligible=2)[fairness]}')
        config += f';fairness={fairness}'
    row = dict(zip(HEADER, ['spin', prop, version, config, '', 'ERROR', '', '', '', '']))
    metadata = {'case': case_id, 'property': prop, 'scenario': scenario,
                'version':version, 'parameters':{'delta':delta,'yellow':yellow,'min':minimum,'max':maximum},
                'versions': versions, 'network': network, 'flags': flags,
                'agent_fairness': fairness, 'process_weak_fairness': False,
                'limits': {'depth': args.depth, 'memory_mb': args.memory,
                           'timeout_s_per_command': args.timeout},
                'commands': [], 'model_sha256': {}, 'started_utc': stamp,
                'source_snapshot': 'models/',
                'observation_columns': ['signal', 'current_phase', 'controller_age', 'green_age_before_sample', 'yellow_age_before_sample'],
                'timing_columns': ['observed_green_age', 'ns_wait', 'ew_wait'],
                'timing': 'time_s is verifier wall time only; generation/compile recorded separately',
                'ce_length_convention': 'count ACTION events through failing state, including an unfinished decision; not guaranteed shortest',
                'limitations': ['reference static timing, not real SUMO validation',
                                'C1 decision-boundary interpretation pending D4']}
    for path in [SPIN / 'models/controller.pml', SPIN / 'models/properties.pml',
                 Path(__file__).resolve(), SPIN / 'scripts/liveness.py']:
        metadata['model_sha256'][str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata['reference_sha256'] = {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in (REPO / 'verification/esbmc/model').glob('*.py')}

    def execute(command, cwd, filename):
        start = time.perf_counter()
        try:
            completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                                       timeout=args.timeout)
            output = completed.stdout + completed.stderr
            code = completed.returncode
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b'') + (error.stderr or b'')
            if isinstance(output, bytes):
                output = output.decode(errors='replace')
            (evidence / filename).write_text(output)
            metadata['commands'].append({'argv': command, 'shell': shlex.join(command),
                                          'time_s': time.perf_counter() - start, 'timeout': True})
            raise
        elapsed = time.perf_counter() - start
        (evidence / filename).write_text(output)
        metadata['commands'].append({'argv': command, 'shell': shlex.join(command),
                                      'exit_code': code, 'time_s': elapsed})
        return code, output, elapsed

    try:
        with tempfile.TemporaryDirectory(prefix='traffic-spin-check-') as directory:
            build = Path(directory)
            for name in ('controller.pml', 'properties.pml'):
                shutil.copyfile(SPIN / 'models' / name, build / name)
            code, output, _ = execute(['spin', *flags, '-a', 'controller.pml'], build, 'generate.txt')
            if code or 'Error:' in output:
                raise RuntimeError('SPIN generation failed')
            compile_cmd = ['cc', '-O2', f'-DMEMLIM={args.memory}']
            if prop not in ('T2', 'L2'):
                compile_cmd.append('-DSAFETY')
            code, _, _ = execute([*compile_cmd, '-o', 'pan', 'pan.c'], build, 'compile.txt')
            if code:
                raise RuntimeError('C compilation failed')
            execute(['./pan', '-?'], build, 'pan-help.txt')
            pan = ['./pan', f'-m{args.depth}', '-w18', '-b']
            if prop in ('T2', 'L2'):
                pan.append('-a')
            code, output, elapsed = execute(pan, build, 'verify.txt')
            row['result'] = classify(output, code)
            row['time_s'] = f'{elapsed:.6f}'
            depth = re.search(r'depth reached\s+(\d+)', output)
            memory = re.search(r'([\d.]+)\s+total actual memory usage', output)
            if depth:
                row['bound'] = f'depth={depth[1]}'
            if memory:
                row['memory_mb'] = memory[1]
            trail = build / 'controller.pml.trail'
            if row['result'] == 'FAIL':
                if not trail.exists():
                    raise RuntimeError('FAIL reported without a trail')
                shutil.copyfile(trail, evidence / 'trail.txt')
                _, replay, _ = execute(['spin', '-T', *flags, '-t', '-k',
                                         'controller.pml.trail', 'controller.pml'],
                                        build, 'replay.txt')
                actions = [int(x) for x in re.findall(r'^\s*ACTION (-?\d+)\s*$', replay, re.M)]
                row['ce_length'] = str(len(actions))
                observations = [[int(x) for x in match.split()] for match in
                                re.findall(r'^\s*OBS ((?:-?\d+ ){4}-?\d+)\s*$', replay, re.M)]
                witness = {'actions': actions, 'observed_seconds': len(observations),
                           'last_observations': observations[-12:],
                           'acceptance_cycle': 'START OF CYCLE' in replay,
                           'timing_samples': [[int(x) for x in match.split()] for match in
                                             re.findall(r'^\s*TIMING ((?:-?\d+ ){2}-?\d+)\s*$', replay, re.M)]}
                if not witness['acceptance_cycle']:
                    witness['reference'] = reference_witness(prop, scenario, actions, version, delta, minimum, maximum)
                else:
                    if prop == 'L2':
                        cycle = analyze_cycle(replay, fairness)
                        closure = reference_lasso(REPO, scenario, cycle, version=version)
                        if not cycle['selected_premise_holds'] or not cycle['violates_service']:
                            raise ValueError('L2 witness does not exhibit the selected fair-service violation')
                        if not closure['closed'] or closure['period_time_s'] <= 0:
                            raise ValueError('L2 reference projection did not close with positive time')
                        if closure['period_green_codes'] != cycle['cycle_service_codes']:
                            raise ValueError('Reference lasso service differs from the SPIN cycle')
                        if fairness == 'request' and not closure['request_fair']:
                            raise ValueError('Reference period does not satisfy request fairness')
                        if fairness == 'eligible' and not closure['eligible_request_fair']:
                            raise ValueError('Reference period does not satisfy eligible fairness')
                        witness['cycle'] = cycle
                        witness['reference_lasso'] = closure
                        witness['reference'] = {'reproduced': None,
                                                'message': 'Projected reference lasso closes; full-system liveness not tested'}
                    else:
                        witness['reference'] = {'reproduced': None, 'message': 'Infinite cycle needs liveness analysis'}
                (evidence / 'witness.json').write_text(json.dumps(witness, indent=2) + '\n')
                metadata['witness'] = witness
    except subprocess.TimeoutExpired:
        row['result'] = 'TIMEOUT'
    except (RuntimeError, OSError, ValueError) as error:
        metadata['error'] = str(error)
        row['result'] = 'ERROR'
    relative = str(evidence.relative_to(SPIN))
    row['notes'] = f'evidence={relative};model-level only;ce counts started decisions;DFS witness not necessarily shortest'
    if 'probe' in params:
        row['notes'] += ';parameter probe beyond default;dt12 probe outside teammate dt1..7 sweep'
    if version=='v1':
        row['notes'] += ';accepted parameters and legal inputs;rejections tested separately'
    if prop == 'L2':
        row['notes'] += f';agent_fairness={fairness};ongoing positive-time controller;ce=prefix plus one cycle decisions'
    if prop == 'G2':
        row['notes'] += ';observed green per second AND controller age after decisions'
    if prop == 'L1':
        row['notes'] += f';wait_limit={maximum + 2 * yellow}s;warmup and yellow included'
    if prop == 'C1':
        row['notes'] += ';C1 sampled after decision;D4 unavailable'
    if scenario == 'y0' and prop == 'T2':
        row['notes'] += ';observed-yellow obligation;T1 separately checks missing yellow'
    metadata['result'] = row
    (evidence / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return row, metadata


def save_rows(rows):
    path = SPIN / 'results/results.csv'
    existing = []
    if path.exists():
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != HEADER:
                raise ValueError('Existing results.csv has an unexpected schema')
            existing = list(reader)
    keys = {(r['tool'], r['property'], r['version'], r['config']) for r in rows}
    retained = [r for r in existing
                if (r['tool'], r['property'], r['version'], r['config']) not in keys]
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADER, lineterminator='\n')
        writer.writeheader()
        writer.writerows(retained + rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases', nargs='*', choices=None)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--all', action='store_true', help='All currently implemented v0/v1 cases including parameter probes')
    parser.add_argument('--stage', choices=STAGES, help='Run only this stage instead of --all/case IDs')
    parser.add_argument('--depth', type=int, default=100000)
    parser.add_argument('--memory', type=int, default=512)
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if args.list:
        print('\n'.join(CASES))
        return
    if args.depth < 1 or args.memory < 1 or args.timeout <= 0:
        parser.error('Limits must be positive')
    if sum([bool(args.all), bool(args.stage), bool(args.cases)]) != 1:
        parser.error('Choose one of --all, --stage, or case IDs')
    unknown = set(args.cases) - set(CASES)
    if unknown:
        parser.error(f'Unknown case IDs: {sorted(unknown)}')
    network = network_preflight()
    versions = {'spin': subprocess.check_output(['spin', '-V'], text=True).strip(),
                'cc': subprocess.check_output(['cc', '--version'], text=True).strip()}
    rows = []
    bad = False
    selected = CASES if args.all else [case for case, (prop, _) in CASES.items()
                                      if CASE_STAGE[case] == args.stage] if args.stage else args.cases
    for case in selected:
        row, metadata = run_case(case, *CASES[case], args, network, versions)
        rows.append(row)
        save_rows(rows)
        reference = metadata.get('witness', {}).get('reference', {})
        bad |= row['result'] in ('UNKNOWN', 'TIMEOUT', 'ERROR') or reference.get('reproduced') is False
        print(f'{case}: {row["result"]} {row["bound"]} ce_decisions={row["ce_length"] or "-"}', flush=True)
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
