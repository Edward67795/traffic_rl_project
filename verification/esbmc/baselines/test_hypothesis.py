"""Property-based testing baseline (Hypothesis) for the same properties ESBMC checks.

Runs the verbatim model (model/env_core_<version>.py on model/traci_stub.py) in CPython.
Hypothesis draws action sequences and, for the parametric test, configurations.

    pytest -q verification/esbmc/baselines/test_hypothesis.py            # v0, expect failures
    MODEL=v1 pytest -q verification/esbmc/baselines/test_hypothesis.py   # v1, expect all pass
    pytest -q ... --hypothesis-show-statistics                           # examples tried, time
"""
import os
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

MODEL_DIR = Path(__file__).resolve().parents[1] / "model"
VERSION = os.environ.get("MODEL", "v0")
FILES = {"v0": "env_core_v0.py", "v1": "env_core_v1.py", "v1naive": "env_core_v1_naive.py"}
MAX_EXAMPLES = int(os.environ.get("MAX_EXAMPLES", "200"))


def load(chk: str = "", static: bool = False, mon=(10, 60, 3)):
    ns = {"nondet_int": lambda: 0, "__ESBMC_assume": lambda c: None}
    code = (MODEL_DIR / "traci_stub.py").read_text() + "\n" + (MODEL_DIR / FILES[VERSION]).read_text()
    exec(compile(code, "model", "exec"), ns)
    if chk:
        ns["CHK_" + chk] = True
    ns["STATIC_PROGRAM"] = static
    ns["MON_MIN_GREEN"], ns["MON_MAX_GREEN"], ns["MON_YELLOW"] = mon
    return ns


actions = st.lists(st.integers(0, 1), min_size=1, max_size=30)


def run(ns, acts, d=5, y=3, mn=10, mx=60, check_g2=False, check_c1=False):
    # Each test checks only its own property: the stub monitor enabled by load(chk) and,
    # if asked, the controller-level G2/C1 asserts. A failure then always names that property.
    env = ns["SumoTrafficEnvCore"](d, y, mn, mx, 3600)
    env.reset()
    for a in acts:
        env.step(a)
        if check_g2:
            assert env.phase_duration <= env.max_green, "G2: phase_duration exceeds max_green"
        if check_c1:
            assert env.current_phase in (0, 1), "C1: current_phase out of range"
    return env


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(actions)
def test_G2_max_green(acts):
    run(load("G2"), acts, check_g2=True)


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(actions)
def test_L1_no_starvation(acts):
    run(load("L1"), acts)


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(actions)
def test_T2_static_program(acts):
    run(load("T2", static=True), acts)


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(st.lists(st.integers(-1, 2), min_size=1, max_size=30))
def test_C1_any_action(acts):
    if VERSION != "v0" and any(a not in (0, 1) for a in acts):
        with pytest.raises(ValueError):       # v1 rejects invalid actions by design
            run(load(), acts, check_c1=True)
        return
    run(load(), acts, check_c1=True)


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(st.integers(1, 20), st.integers(0, 12), st.integers(5, 16), actions)
def test_G2_parametric(d, mn, mx, acts):
    try:
        ns = load()
        ns["SumoTrafficEnvCore"](d, 3, mn, mx, 3600)
    except ValueError:
        return                                # configuration rejected by the constructor
    run(ns, acts, d=d, mn=mn, mx=mx, check_g2=True)
