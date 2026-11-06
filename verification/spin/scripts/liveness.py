"""Acceptance-cycle analysis and projected Python-reference lasso checks.

Reference closure concerns the extracted control abstraction with saturated age,
not full Python/SUMO liveness. Absolute time/episode termination are omitted.
"""
import contextlib
import io
from pathlib import Path
import re

MARKER = '<<<<<START OF CYCLE>>>>>'


def actions_in(text):
    return [int(x) for x in re.findall(r'^\s*ACTION (-?\d+)\s*$', text, re.M)]


def observations_in(text):
    return [[int(x) for x in m.split()] for m in
            re.findall(r'^\s*OBS ((?:-?\d+ ){4}-?\d+)\s*$', text, re.M)]


def analyze_cycle(replay, fairness):
    if MARKER not in replay:
        raise ValueError('Acceptance-cycle replay has no cycle marker')
    prefix, period = replay.split(MARKER, 1)
    actions = actions_in(period)
    samples = observations_in(period)
    requests = [[int(x) for x in m.split()] for m in
                re.findall(r'^\s*REQUEST (-?\d+ [01])\s*$', period, re.M)]
    if not actions or not samples:
        raise ValueError('Cycle lacks decision/time progress; cannot interpret service liveness')
    services = sorted({x[0] for x in samples if x[0] in (0, 2)})
    request_fair = {0, 1} <= {x[0] for x in requests}
    eligible_fair = {0, 1} <= {a for a, eligible in requests if eligible}
    premise = fairness == 'none' or (request_fair if fairness == 'request' else eligible_fair)
    return {'prefix_actions': actions_in(prefix), 'cycle_actions': actions,
            'prefix_decisions': len(actions_in(prefix)), 'cycle_decisions': len(actions),
            'prefix_samples': len(observations_in(prefix)), 'cycle_samples': len(samples),
            'cycle_requests': requests, 'cycle_service_codes': services,
            'missing_green_directions': [name for code, name in [(0, 'NS'), (2, 'EW')]
                                         if code not in services],
            'request_fair': request_fair, 'eligible_request_fair': eligible_fair,
            'selected_premise_holds': premise,
            'violates_service': services != [0, 2]}


def reference_lasso(repo, scenario, cycle, version="v0"):
    """Rotate to decision boundaries and check one repeated projected period."""
    namespace = {}
    for name in ['traci_stub.py', f'env_core_{version}.py']:
        path = Path(repo) / 'verification/esbmc/model' / name
        exec(compile(path.read_text(), str(path), 'exec'), namespace)
    namespace['STATIC_PROGRAM'] = scenario == 'L1'
    stub = namespace['traci']
    env = namespace['SumoTrafficEnvCore'](5, 0 if scenario == 'y0' else 3, 10, 60, 3600)
    samples = []
    original = stub.simulationStep

    def sample_step():
        samples.append(stub.trafficlight.code)
        original()

    stub.simulationStep = sample_step

    def state():
        return {'phase': env.current_phase, 'signal': stub.trafficlight.code,
                'controller_age_projected': min(env.phase_duration, 76),
                'online': stub.trafficlight.online, 'static_index': stub.sp_index,
                'static_left': stub.sp_left}

    with contextlib.redirect_stdout(io.StringIO()):
        env.reset()
        # The marker can split a decision. Start the closure check after its
        # containing period finishes, then repeat the same rotated action word.
        for a in cycle['prefix_actions'] + cycle['cycle_actions']:
            env.step(a)
        before = state()
        time_before = stub.time
        samples.clear()
        eligible = set()
        for a in cycle['cycle_actions']:
            if a in (0, 1) and env.phase_duration >= 10:
                eligible.add(a)
            env.step(a)
        after = state()
    greens = sorted({x for x in samples if x in (0, 2)})
    return {'kind': 'projected-extracted-reference-lasso-closure',
            'state_before': before, 'state_after': after,
            'closed': before == after, 'period_time_s': stub.time - time_before,
            'period_green_codes': greens,
            'period_actions': cycle['cycle_actions'],
            'request_fair': {0, 1} <= set(cycle['cycle_actions']),
            'eligible_request_fair': eligible == {0, 1},
            'limitation': 'Finite closure on the documented quotient, not full Python/SUMO proof'}
