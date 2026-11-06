#!/usr/bin/env python3
"""Validate current CSV verdicts against raw pan output, sources and witness data."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from run_spin import SPIN, REPO, HEADER, classify


def audit(path):
    with path.open(newline='') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=HEADER:raise ValueError('Unexpected CSV schema')
        rows=list(reader)
    keys=set();counts={};finite=0;cyclic=0
    for row in rows:
        key=tuple(row[k] for k in ('tool','property','version','config'))
        if key in keys:raise ValueError('Duplicate result key')
        keys.add(key)
        directory=SPIN/row['notes'].split(';')[0].split('=',1)[1]
        metadata=json.loads((directory/'metadata.json').read_text())
        if metadata['result']!=row:raise ValueError(f'Metadata/CSV mismatch: {key}')
        pan=next(c for c in metadata['commands'] if c['argv'][0]=='./pan' and
                 any(a.startswith('-m') for a in c['argv']))
        actual=classify((directory/'verify.txt').read_text(),pan['exit_code'])
        if actual!=row['result']:raise ValueError(f'Raw verdict differs: {key}')
        for relative,digest in metadata['model_sha256'].items():
            original=REPO/relative
            candidates=[original,directory/'models'/original.name]
            candidates+=list((SPIN/'results/snapshots').glob(f'*-scripts/{original.name}'))
            candidates+=list((SPIN/'results/snapshots').glob(f'*-model/{original.name}'))
            if not any(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest for p in candidates):
                raise ValueError(f'No matching retained source: {relative}')
        if actual=='PASS':
            if row['ce_length']:raise ValueError('PASS has counterexample length')
        elif actual=='FAIL':
            witness=json.loads((directory/'witness.json').read_text())
            if int(row['ce_length'])!=len(witness['actions']):raise ValueError('Bad decision count')
            if witness['acceptance_cycle']:
                cyclic+=1;c=witness['cycle'];ref=witness['reference_lasso']
                if not(c['selected_premise_holds'] and c['violates_service'] and ref['closed'] and ref['period_time_s']>0):
                    raise ValueError('Invalid liveness interpretation')
            else:
                finite+=1
                if not witness['reference']['reproduced']:raise ValueError('Reference witness did not reproduce')
        counts[actual]=counts.get(actual,0)+1
    return dict(rows=len(rows),verdicts=counts,finite_witnesses=finite,cyclic_witnesses=cyclic,
                note='Audits saved evidence, not an independent rerun or real SUMO proof')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=audit(SPIN/'results/results.csv')
    print(json.dumps(result,indent=2))
    if args.output:
        if args.output.exists():parser.error('Refusing to overwrite audit evidence')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
