#!/usr/bin/env python3
"""Check TLS/request-index correspondence using the installed SUMO library.

Uses getJunctionIndex rather than assuming equal counts imply equal indices.
Checks protected G/G conflicts; permissive g is intentionally not protected G.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Refusing to overwrite network evidence')
    import sumolib
    repo=Path(__file__).resolve().parents[3]
    path=repo/'networks/single_intersection.net.xml'
    net=sumolib.net.readNet(str(path))
    node=net.getNode('center')
    mapping=[]
    for edge in node.getIncoming():
        for lane in edge.getLanes():
            for connection in lane.getOutgoing():
                if connection.getTLSID()=='center':
                    mapping.append(dict(tls=connection.getTLLinkIndex(),
                        junction=connection.getJunctionIndex(),incoming=lane.getID(),
                        outgoing=connection.getToLane().getID()))
    mapping.sort(key=lambda r:r['tls'])
    if [r['tls'] for r in mapping]!=list(range(14)):
        raise ValueError('Unexpected TLS index coverage')
    root=ET.parse(path).getroot()
    foes={int(r.get('index')):r.get('foes') for r in root.findall("junction[@id='center']/request")}
    phases=[]
    for phase in root.findall("tlLogic[@id='center']/phase"):
        state=phase.get('state');bad=[]
        for a in mapping:
            for b in mapping:
                if a['tls']<b['tls'] and state[a['tls']]==state[b['tls']]=='G' and foes[a['junction']][-1-b['junction']]=='1':
                    bad.append([a['tls'],b['tls']])
        phases.append(dict(state=state,protected_conflicts=bad))
    record=dict(kind='SUMO-library-index-and-protected-conflict-audit',
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),mapping=mapping,
        identity_mapping=all(r['tls']==r['junction'] for r in mapping),phases=phases,
        sources=['https://sumo.dlr.de/docs/Networks/SUMO_Road_Networks.html',
                 'https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print('Identity mapping:',record['identity_mapping'],'protected conflicts:',sum(len(p['protected_conflicts']) for p in phases))
    if not record['identity_mapping'] or any(p['protected_conflicts'] for p in phases):raise SystemExit(1)


if __name__=='__main__':main()
