"""
Reproduce control-logic issues of the ORIGINAL SumoTrafficEnv (main branch) in real SUMO.

Usage (from anywhere):
    pip install eclipse-sumo traci sumolib gymnasium numpy
    export SUMO_HOME=$(python -c "import sumo; print(sumo.SUMO_HOME)")
    python reproduce_v0_findings.py /path/to/traffic_rl_project

Tested with SUMO 1.28.0 (eclipse-sumo wheel), off_peak scenario, default parameters
(delta_time=5, yellow_time=3, min_green=10, max_green=60).

What it shows:
  A. max_green is never enforced (phase_duration grows past 60)  +  static-program desync:
     reset() never calls _set_phase(), so SUMO's static tlLogic (42s G / 3s y) keeps running
     until the agent's first switch; env.current_phase no longer matches the real signal.
  B. Out-of-range action (2) is not rejected: _set_phase() falls back to phase 0 but
     current_phase becomes 2 (belief != actual), and NS-green -> yellow -> NS-green appears.
  C. yellow_time=0 is accepted: NS-green -> EW-green with no yellow at all.
  D. Valid actions only (0 x 8, then 1): EW-green (static program) -> yellow -> EW-green,
     i.e. a spurious yellow, and the env restarts phase-duration accounting.
"""
import contextlib
import io
import os
import sys

REPO = sys.argv[1]
sys.path.insert(0, os.path.join(REPO, "src"))
os.chdir(REPO)

import traci  # noqa: E402
from environment import SumoTrafficEnv  # noqa: E402

TLS = "center"
TRACE = []  # (sim_time, displayed_state, program_id) after every simulation second
_orig_step = traci.simulationStep


def _logged_step(*args, **kwargs):
    result = _orig_step(*args, **kwargs)
    TRACE.append((traci.simulation.getTime(),
                  traci.trafficlight.getRedYellowGreenState(TLS),
                  traci.trafficlight.getProgram(TLS)))
    return result


traci.simulationStep = _logged_step
quiet = lambda: contextlib.redirect_stdout(io.StringIO())  # noqa: E731


def make_env(**kw):
    with quiet():
        env = SumoTrafficEnv("networks/single_intersection.net.xml",
                             "scenarios/off_peak.rou.xml", **kw)
        env.reset(seed=0)
    TRACE.clear()
    return env


def label(env, s):
    if s == env.phase_states[0]:
        return "NS-green"
    if s == env.phase_states[1]:
        return "EW-green"
    if "y" in s and "G" not in s and "g" not in s:
        return "yellow"
    return "other:" + s


def signal_sequence(env):
    seq = [(t, label(env, s), p) for t, s, p in TRACE]
    out = [seq[0]] + [seq[i] for i in range(1, len(seq)) if seq[i][1:] != seq[i - 1][1:]]
    return "  ->  ".join(f"{lab}@t={t:.0f}[{prog}]" for t, lab, prog in out)


print("=== A: agent always chooses action 0 ===")
env = make_env()
for k in range(1, 15):
    with quiet():
        env.step(0)
    t, s, prog = TRACE[-1]
    flag = "  <-- exceeds max_green" if env.phase_duration > env.max_green else ""
    print(f"step {k:2d} | t={t:4.0f} | env.current_phase={env.current_phase} "
          f"phase_duration={env.phase_duration:3d} | SUMO shows {label(env, s):9s} "
          f"program={prog}{flag}")
env.close()

print("\n=== B: out-of-range action 2 after min-green is satisfied ===")
env = make_env()
with quiet():
    env.step(0); env.step(0); env.step(2)
print(f"env.current_phase={env.current_phase}, SUMO shows {label(env, TRACE[-1][1])}")
with quiet():
    env.step(0); env.step(0); env.step(0)
print("signal:", signal_sequence(env))
env.close()

print("\n=== C: yellow_time=0 ===")
env = make_env(yellow_time=0)
with quiet():
    for a in [1, 1, 1, 0, 0, 0, 1]:
        env.step(a)
print("signal:", signal_sequence(env))
env.close()

print("\n=== D: valid actions only: 0 x 8, then 1 x 3 ===")
env = make_env()
with quiet():
    for a in [0] * 8 + [1] * 3:
        env.step(a)
print("signal:", signal_sequence(env))
print("env.current_phase at end:", env.current_phase)
env.close()
