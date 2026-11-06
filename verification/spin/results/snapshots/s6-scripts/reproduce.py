#!/usr/bin/env python3
"""Run all formal cases in a fresh temporary code copy without changing current CSV.

Uses the installed compiler/SPIN. This tests isolated output/path reproducibility,
not installation on another computer or conformance with real SUMO.
"""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

BASE=Path(__file__).resolve().parents[1]
REPO=BASE.parents[1]


def key(row):return tuple(row[x] for x in ('tool','property','version','config'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a new output directory')
    args.output.mkdir(parents=True)
    baseline={key(r):r for r in csv.DictReader((BASE/'results/results.csv').open())}
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='spin-isolated-repro-') as directory:
        root=Path(directory)
        for relative in ['src','networks','scenarios','verification/esbmc/model',
                         'verification/spin/models','verification/spin/scripts']:
            shutil.copytree(REPO/relative,root/relative,
                            ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        command=[sys.executable,'verification/spin/scripts/run_spin.py','--all']
        process=subprocess.Popen(command,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 text=True,bufsize=1)
        lines=[]
        for line in process.stdout:
            lines.append(line);print(line,end='',flush=True)
        code=process.wait()
        (args.output/'run.txt').write_text(''.join(lines))
        shutil.copytree(root/'verification/spin/results',args.output/'results')
    reproduced={key(r):r for r in csv.DictReader((args.output/'results/results.csv').open())}
    differences=[]
    for k in baseline.keys()|reproduced.keys():
        a=baseline.get(k);b=reproduced.get(k)
        if a is None or b is None or any(a[x]!=b[x] for x in ('result','bound','ce_length')):
            differences.append(dict(key=k,baseline=a,reproduced=b))
    summary={'kind':'fresh-temporary-code-copy-formal-reproduction','exit_code':code,
             'rows':len(reproduced),'matched_verdict_depth_ce':not differences,
             'differences':differences,'wall_time_s':time.perf_counter()-started,
             'argv':command,'limits':['same installed toolchain, not a fresh Mac',
                                     'metrics measured again; timings are not expected identical']}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='differences'},indent=2))
    if code or differences:raise SystemExit(1)


if __name__=='__main__':main()
