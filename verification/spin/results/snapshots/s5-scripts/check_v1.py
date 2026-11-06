#!/usr/bin/env python3
"""Compare v1 rejection/acceptance and boundary traces to the unchanged patch core."""
import argparse
import hashlib
import json
from pathlib import Path

from check_traces import reference_trace, promela_trace, MODEL, REFERENCE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new evidence file; preserve earlier results')
    specs = [
        ('default-hold', 5, 3, 10, 60, [0]*40),
        ('opposite-hold', 5, 3, 10, 60, [1]*40),
        ('delta7', 7, 3, 10, 60, [0]*40),
        ('max61', 5, 3, 10, 61, [0]*40),
        ('delta3-max16', 3, 3, 10, 16, [0]*40),
        ('min0-delta7', 7, 3, 0, 11, [0]*40),
        ('min12-delta1', 1, 3, 12, 16, [0]*40),
        ('accepted-wide-delta', 12, 3, 0, 11, [0]*8),
        ('reject-zero-delta', 0, 3, 10, 60, [0]),
        ('reject-negative-delta', -1, 3, 10, 60, [0]),
        ('reject-zero-yellow', 5, 0, 10, 60, [0]),
        ('reject-short-yellow', 5, 2, 10, 60, [0]),
        ('reject-negative-min', 5, 3, -1, 60, [0]),
        ('reject-zero-max', 5, 3, 0, 0, [0]),
        ('reject-min-above-max', 5, 3, 61, 60, [0]),
        ('reject-warmup-switch-point', 7, 3, 12, 13, [0]),
        ('reject-restart-switch-point', 7, 3, 10, 11, [0]),
        ('reject-minus1-initial', 5, 3, 10, 60, [-1]),
        ('reject-action2-initial', 5, 3, 10, 60, [2]),
        ('reject-before-force', 5, 3, 10, 60, [0]*10+[2]),
        ('reject-after-switch', 5, 3, 10, 60, [1,-1]),
    ]
    results=[]
    for name,delta,yellow,minimum,maximum,actions in specs:
        for static in (0,1):
            params=(actions,static,delta,yellow,minimum,maximum,'v1')
            expected=reference_trace(*params)
            actual=promela_trace(*params)
            if actual != expected:
                i=next((i for i,p in enumerate(zip(actual,expected)) if p[0]!=p[1]),min(len(actual),len(expected)))
                raise AssertionError(f'{name}/static{static} record{i}: {actual[i:i+1]} vs {expected[i:i+1]}')
            rejection=next((r[1] for r in actual if r[0]=='REJECT'),None)
            results.append({'name':name,'static':static,'delta':delta,'yellow':yellow,
                            'min':minimum,'max':maximum,'actions':actions,
                            'reference_match':True,'input_outcome':'REJECTED' if rejection else 'ACCEPTED',
                            'rejection_reason':rejection,'records':actual})
    evidence={'kind':'auxiliary-v1-input-contract-and-timing-traces',
              'warning':'Accepted traces are not property PASS; rejection is not normal-operation verification',
              'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [MODEL,MODEL.parent/'properties.pml',REFERENCE/'env_core_v1.py',Path(__file__).resolve()]},
              'cases':results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,indent=2)+'\n')
    print(f'MATCH: {len(results)} v1 input-contract/boundary cases; '
          f'{sum(r["input_outcome"]=="REJECTED" for r in results)} rejections matched.')
    print('Accepted wide-delta trace retained; acceptance does not imply G2 holds.')


if __name__=='__main__':
    main()
