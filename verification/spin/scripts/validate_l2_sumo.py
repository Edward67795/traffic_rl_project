#!/usr/bin/env python3
"""Observe three periods of original L2 lassos on source; never infer infinite truth."""
import argparse
import csv
import json
import os
from pathlib import Path

from validate_sumo import BASE, live_trace, projected_promela
from check_traces import promela_trace


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a new output directory')
    args.output.mkdir(parents=True)
    import sumo
    os.environ['SUMO_HOME']=str(sumo.SUMO_HOME)
    summary=[]
    for row in csv.DictReader((BASE/'results/results.csv').open()):
        if row['property']!='L2' or row['result']!='FAIL':continue
        directory=BASE/row['notes'].split(';')[0].split('=',1)[1]
        meta=json.loads((directory/'metadata.json').read_text())
        c=meta['witness']['cycle']
        actions=c['prefix_actions']+c['cycle_actions']*3
        live=live_trace(row['version'],actions,meta['parameters'])
        modeled=projected_promela(promela_trace(actions,int(meta['scenario']=='L1'),5,
            0 if meta['scenario']=='y0' else 3,version=row['version']))
        last_start=len(c['prefix_actions'])+2*len(c['cycle_actions'])
        period=[s for s in live['samples'] if s['decision']>last_start]
        record=dict(case=meta['case'],actions=actions,period_repetitions=3,
          exact_finite_trace_match=live['records']==modeled,
          last_period_green_codes=sorted({s['signal'] for s in period if s['signal'] in (0,2)}),
          last_program=period[-1]['program'] if period else None,
          limitation='Finite source observation only; no infinite L2 verdict',live=live,promela=modeled)
        (args.output/(meta['case']+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        summary.append({k:v for k,v in record.items() if k not in ('live','promela','actions')})
        print(meta['case'],'finite match=',record['exact_finite_trace_match'],flush=True)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
