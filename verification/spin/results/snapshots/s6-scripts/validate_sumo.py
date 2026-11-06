#!/usr/bin/env python3
"""Compare live original SUMO source traces to Promela and replay saved witnesses.

v1 is a temporary full-source copy patched with the unchanged shared patch.
Independent monitors below do not import the ESBMC core or TraCI stub.
Finite observations are supplementary evidence, never an infinite L2 proof.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
import csv

from check_traces import promela_trace

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
STATES = ['GGGgrrrGGGgrrr','yyyyrrryyyyrrr','rrrrGGgrrrrGGg','rrrryyyrrrryyy']


class SignalMonitor:
    """Independent sample counters on real displayed states, recording first faults."""
    def __init__(self, minimum, maximum, yellow):
        self.minimum=minimum; self.maximum=maximum; self.limit=maximum+2*yellow
        self.previous=None; self.last_green=None
        self.green_age=0; self.yellow_age=0; self.ns_wait=0; self.ew_wait=0
        self.events={}

    def fault(self, prop, component, second, decision, message, **extra):
        self.events.setdefault((prop,component),dict(property=prop,component=component,
            time_s=second,decision=decision,message=message,**extra))

    def sample(self, code, second, decision):
        if code not in range(4):
            self.fault('S1','signal_code',second,decision,'Unknown displayed signal')
        green=code in (0,2); prev_green=self.previous in (0,2)
        yellow=code in (1,3); prev_yellow=self.previous in (1,3)
        if prev_green and green and code != self.previous:
            self.fault('T1','missing_yellow',second,decision,'Direct green direction change')
        if prev_yellow and green:
            if self.yellow_age<3:
                self.fault('T2','yellow_duration',second,decision,'Yellow shorter than3',yellow_age=self.yellow_age)
            if code==self.last_green:
                self.fault('T2','yellow_target',second,decision,'Yellow returned to the same green')
        if prev_green and code != self.previous and self.green_age<self.minimum:
            self.fault('G1','observed_green',second,decision,'Green terminated too early',green_age=self.green_age)
        if green:
            self.green_age=self.green_age+1 if code==self.previous else 1
            self.last_green=code; self.yellow_age=0
        else:
            self.green_age=0
            self.yellow_age=(self.yellow_age+1 if prev_yellow else 1) if yellow else 0
        self.ns_wait=0 if code==0 else self.ns_wait+1
        self.ew_wait=0 if code==2 else self.ew_wait+1
        if self.green_age>self.maximum:
            self.fault('G2','observed_green',second,decision,'Displayed green exceeds max',green_age=self.green_age)
        for direction,value in [('NS',self.ns_wait),('EW',self.ew_wait)]:
            if value>self.limit:
                self.fault('L1',direction+'_wait',second,decision,'Directional wait exceeds configured bound',wait=value,limit=self.limit)
        self.previous=code

    def boundary(self, env, code, second, decision):
        if env.phase_duration>self.maximum:
            self.fault('G2','controller_age',second,decision,'Controller age exceeds max',controller_age=env.phase_duration)
        if env.current_phase not in (0,1):
            self.fault('C1','phase_range',second,decision,'Controller phase outside0/1',phase=env.current_phase)
        elif code != (0 if env.current_phase==0 else 2):
            self.fault('C1','signal_agreement',second,decision,'Controller and displayed signal disagree',phase=env.current_phase,signal=code)


def load_source(version, temporary):
    path=REPO/'src/environment.py'
    patch_log=''
    if version=='v1':
        path=Path(temporary)/'src/environment.py';path.parent.mkdir()
        shutil.copyfile(REPO/'src/environment.py',path)
        command=['patch','--batch','-p1','-i',str(REPO/'verification/esbmc/model/v1_fix.patch')]
        result=subprocess.run(command,cwd=temporary,capture_output=True,text=True)
        patch_log=result.stdout+result.stderr
        if result.returncode:raise RuntimeError(patch_log)
    spec=importlib.util.spec_from_file_location('sumo_original_'+version,str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.SumoTrafficEnv,hashlib.sha256(path.read_bytes()).hexdigest(),patch_log


def live_trace(version,actions,params,route='off_peak'):
    import traci
    minimum=params.get('min',10);maximum=params.get('max',60)
    delta=params.get('delta',5);yellow=params.get('yellow',3)
    cap=maximum+minimum+delta+1
    records=[];samples=[];decision=0;env=None;rejection=None
    monitor=SignalMonitor(minimum,maximum,yellow)
    original_step=traci.simulationStep
    output=io.StringIO()
    def code():
        state=traci.trafficlight.getRedYellowGreenState('center')
        return STATES.index(state) if state in STATES else -1
    def values():
        return [code(),env.current_phase,min(env.phase_duration,cap),
                int(traci.trafficlight.getProgram('center')=='online')]
    def observed(*args,**kwargs):
        before=traci.simulation.getTime()
        state=values()
        records.append(['TICK',env.current_step,*state])
        samples.append(dict(time_s=before,signal=state[0],phase=env.current_phase,
            controller_age=env.phase_duration,program=traci.trafficlight.getProgram('center'),
            program_phase=traci.trafficlight.getPhase('center'),
            next_switch=traci.trafficlight.getNextSwitch('center'),decision=decision))
        monitor.sample(state[0],before,decision)
        return original_step(*args,**kwargs)
    traci.simulationStep=observed
    with tempfile.TemporaryDirectory(prefix='spin-source-') as directory:
        Env,source_hash,patch_log=load_source(version,directory)
        try:
            with contextlib.redirect_stdout(output):
                try:
                    env=Env(str(REPO/'networks/single_intersection.net.xml'),
                            str(REPO/f'scenarios/{route}.rou.xml'),delta_time=delta,
                            yellow_time=yellow,min_green=minimum,max_green=maximum)
                except ValueError as error:
                    message=str(error)
                    reason=2 if 'first green has no' in message else 3 if 'no multiple of' in message else 1
                    records.append(['REJECT',reason]);rejection={'stage':'constructor','message':message}
                if env is not None:
                    env.reset(seed=0)
                    records.append(['DONE',0,env.current_step,*values()])
                    for decision,action in enumerate(actions,1):
                        try:env.step(action)
                        except ValueError as error:
                            records.append(['REJECT',4])
                            records.append(['ABORT',decision,env.current_step,*values()])
                            rejection={'stage':'action','message':str(error),'decision':decision}
                            break
                        records.append(['DONE',decision,env.current_step,*values()])
                        monitor.boundary(env,code(),traci.simulation.getTime(),decision)
        finally:
            traci.simulationStep=original_step
            with contextlib.redirect_stdout(output):
                if traci.isLoaded():traci.close()
    return {'records':records,'samples':samples,'events':list(monitor.events.values()),
            'rejection':rejection,'source_sha256':source_hash,'patch_log':patch_log,
            'stdout':output.getvalue()}


def projected_promela(records):
    # Ignore abstract static cursor, which is not a controller source field.
    return [record[:6] if record[0]=='TICK' else record[:7] if record[0] in ('DONE','ABORT')
            else record for record in records]


def compare_case(name,version,actions,params,route,output,static=1,expected_match=True):
    started=time.perf_counter()
    live=live_trace(version,actions,params,route)
    modeled=projected_promela(promela_trace(actions,static,params.get('delta',5),
        params.get('yellow',3),params.get('min',10),params.get('max',60),version))
    matches=live['records']==modeled
    mismatch=next((i for i,pair in enumerate(zip(live['records'],modeled)) if pair[0]!=pair[1]),
                  min(len(live['records']),len(modeled))) if not matches else None
    summary={'name':name,'version':version,'actions':actions,'parameters':params,'route':route,
             'modeled_static':static,'matches':matches,'expected_match':expected_match,
             'expectation_met':matches==expected_match,'time_s':time.perf_counter()-started,
             'records':len(live['records']),'first_mismatch':mismatch,
             'actual_at_mismatch':live['records'][mismatch:mismatch+1] if mismatch is not None else None,
             'model_at_mismatch':modeled[mismatch:mismatch+1] if mismatch is not None else None}
    (output/(name+'.json')).write_text(json.dumps({**summary,'live':live,'promela':modeled},indent=2)+'\n')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--random-cases',type=int,default=6,help='Seeded cases per version')
    parser.add_argument('--smoke',action='store_true',help='Only static boundary and one v1 case')
    args=parser.parse_args()
    if args.output.exists():parser.error('Output must be a new directory')
    args.output.mkdir(parents=True)
    import sumo
    os.environ['SUMO_HOME']=str(sumo.SUMO_HOME)
    os.environ['PATH']=str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')
    versions={p:importlib.metadata.version(p) for p in ['eclipse-sumo','traci','sumolib','gymnasium','numpy']}
    versions['python']=sys.version
    versions['sumo']=subprocess.check_output([str(Path(sumo.SUMO_HOME)/'bin/sumo'),'--version'],text=True)
    results=[]
    specs=[
        ('static-hold',[0]*40,{}),('switch-ew',[1]*30,{}),('alternate',[0,1]*20,{}),
        ('takeover-yellow',[0]*7+[1]*8,{}),('takeover-ew',[0]*8+[1]*8,{}),
        ('late-takeover',[0]*17+[1]*8,{}),('illegal',[0,0,-1,2,1,0]*3,{}),
        ('zero-yellow',[0,0,1,0,1],{'yellow':0}),('delta7',[0]*25,{'delta':7}),
        ('min0dt7',[0]*20,{'delta':7,'min':0,'max':11}),
        ('wide-delta',[0]*4,{'delta':12,'min':0,'max':11}),
        ('min12dt1',[0]*25,{'delta':1,'min':12,'max':16}),
        ('max61',[0]*30,{'max':61}),
    ]
    if args.smoke:specs=specs[:1]
    rng=random.Random(6863)
    if not args.smoke:
        for i in range(args.random_cases):
            phase=0;actions=[]
            for _ in range(40):
                if rng.random()<0.2:phase=1-phase
                actions.append(phase)
            specs.append((f'random-{i}',actions,{}))
    for version in ('v0','v1'):
        for i,(name,actions,params) in enumerate(specs):
            print('START',version+'-'+name,flush=True)
            result=compare_case(version+'-'+name,version,actions,params,
                'morning_rush' if i%2 else 'off_peak',args.output)
            results.append(result)
            print(result['name'],'MATCH' if result['matches'] else 'MISMATCH',flush=True)
            if not result['matches']:
                print(result['actual_at_mismatch'],result['model_at_mismatch'],flush=True)
                (args.output/'partial-summary.json').write_text(json.dumps(results,indent=2)+'\n')
                raise SystemExit(1)
    # Deliberately test the documented simplified-fidelity gap.
    result=compare_case('v0-L0-negative-control','v0',[0]*40,{},'off_peak',args.output,
                        static=0,expected_match=False)
    results.append(result);print(result['name'],'expected mismatch:',not result['matches'],flush=True)
    replays=[]
    if not args.smoke:
        for row in csv.DictReader((BASE/'results/results.csv').open()):
            if row['result']!='FAIL' or row['property']=='L2':continue
            evidence=BASE/row['notes'].split(';')[0].split('=',1)[1]
            metadata=json.loads((evidence/'metadata.json').read_text())
            witness=json.loads((evidence/'witness.json').read_text())
            live=live_trace(row['version'],witness['actions'],metadata['parameters'])
            target=[e for e in live['events'] if e['property']==row['property']]
            record={'case':metadata['case'],'version':row['version'],'target':row['property'],
                    'formal_evidence':str(evidence.relative_to(BASE)),'target_reproduced':bool(target),
                    'target_events':target,'live':live}
            (args.output/('replay-'+metadata['case']+'.json')).write_text(json.dumps(record,indent=2)+'\n')
            replays.append({k:v for k,v in record.items() if k!='live'})
            print('replay',metadata['case'],'REPRODUCED' if target else 'NOT REPRODUCED',flush=True)
        # Source-backed short examples compensate for abstraction-only DFS prefixes.
        for name,actions,params in [
            ('concrete-y0',[0,0,1],{'yellow':0}),
            ('concrete-overlong',[0,0,1]+[1]*12,{}),
            ('concrete-starvation',[0,0,1]+[1]*13,{}),
            ('compact-L2-finite-prefix',[0,0,2,1,0]+[0,2,1,0]*3,{}),
        ]:
            live=live_trace('v0',actions,params)
            (args.output/(name+'.json')).write_text(json.dumps(dict(actions=actions,parameters=params,live=live,
                limitation='Finite illustrative source trace, not an infinite liveness proof'),indent=2)+'\n')
    summary={'kind':'real-SUMO-full-source-validation','started_utc':datetime.now(timezone.utc).isoformat(),
             'versions':versions,'conformance':results,'witness_replays':replays,
             'sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [REPO/'src/environment.py',REPO/'networks/single_intersection.net.xml',
                        REPO/'verification/esbmc/model/v1_fix.patch',Path(__file__).resolve()]},
             'limits':['finite conformance is not proof of all source paths',
                       'finite L2 periods are not infinite real-SUMO proofs','human review still required']}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not all(x['expectation_met'] for x in results):raise SystemExit(1)
    print(f'SUMO checks: {len(results)} conformance/negative cases; '
          f'{sum(x["target_reproduced"] for x in replays)}/{len(replays)} original finite witnesses reproduced.',flush=True)


if __name__=='__main__':main()
