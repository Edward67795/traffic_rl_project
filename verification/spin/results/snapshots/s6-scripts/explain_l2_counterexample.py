#!/usr/bin/env python3
"""Construct a compact request-fair starvation witness using a fixed input policy.

The controller is unchanged. This is an illustrative existential witness, not
an additional shared-case row and not a shortest-counterexample claim.
"""
import argparse
import json

from check_liveness import execute_model
from run_spin import SPIN, REPO
from liveness import analyze_cycle, reference_lasso


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    from pathlib import Path
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory to preserve earlier evidence')
    source = (SPIN / 'models/controller.pml').read_text()
    start = source.index('inline choose_action() {')
    left = source.index('{', start)
    balance = 1
    end = left + 1
    while balance:
        if source[end] == '{':
            balance += 1
        elif source[end] == '}':
            balance -= 1
        end += 1
    # Prefix warms up controller age and reaches phase0/age5/online; period
    # holds once, selects invalid 2, requests 1 too early, then returns to 0.
    actions = [0, 0, 2, 1, 0, 0, 2, 1, 0]
    branches = '\n'.join(f':: policy_pos == {i} -> action = {a}'
                         for i, a in enumerate(actions))
    policy = ('byte policy_pos=0;\ninline choose_action() {\nif\n' + branches +
              '\nfi; if :: policy_pos == 8 -> policy_pos=5 '
              ':: else -> policy_pos++ fi\n}')
    generated = source[:start] + policy + source[end:]
    verdict, replay, commands = execute_model(
        generated, ['-DCHK_L2', '-DAGENT_FAIRNESS=1', '-DANY_ACTION'], args.output)
    if verdict != 'FAIL':
        raise RuntimeError('Expected an acceptance-cycle starvation witness')
    cycle = analyze_cycle(replay, 'request')
    reference = reference_lasso(REPO, 'any', cycle)
    if not cycle['selected_premise_holds'] or not cycle['violates_service'] or not reference['closed']:
        raise RuntimeError('Illustrative witness did not validate')
    record = {'kind': 'illustrative-fixed-input-policy-counterexample',
              'verdict': verdict, 'policy_prefix': actions[:5],
              'policy_cycle': actions[5:], 'commands': commands,
              'cycle': cycle, 'reference_lasso': reference,
              'meaning': 'Request fairness does not guarantee service with invalid actions',
              'limitation': 'Input policy restricted for explanation; controller unchanged; not a shortest witness'}
    (args.output / 'analysis.json').write_text(json.dumps(record, indent=2) + '\n')
    print('Validated request-fair starvation: prefix [0,0,2,1,0], repeat [0,2,1,0].')
    print('Reference period:', reference['period_time_s'], 'seconds; greens:', reference['period_green_codes'])


if __name__ == '__main__':
    main()
