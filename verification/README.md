# Verification workspace (CSEE 6863 final project)

Formal verification of the traffic-signal control logic in `src/environment.py`
(SUMO + DQN): ESBMC on the Python source (`esbmc/`), SPIN on a Promela model (`spin/`).
The property IDs, parameters and result format shared by both are in `properties.md`.

## Layout

```
verification/
├── README.md, CLAUDE.md, properties.md
├── common/
│   ├── replay_in_sumo.py          # replay an action sequence in real SUMO, check every property
│   └── reproduce_v0_findings.py   # stand-alone SUMO demo of F1-F4 on the original code
├── esbmc/
│   ├── model/        # env_core_v0.py (extracted), env_core_v1*.py, traci_stub.py,
│   │                 # EXTRACTION.md (line map), v1_fix.patch (FIX-1..4 for src/)
│   ├── harnesses/    # one ESBMC harness per property (h_<ID>.py)
│   ├── scripts/      # run_esbmc.py (suite runner), ce_to_actions.py, conformance_test.py,
│   │                 # py_sim.py, smoke_test.py, scaling_sweep.py, results_table.py,
│   │                 # check_phase_strings.py, param_sweep_maxgreen_fix.py
│   ├── baselines/    # Hypothesis tests and statistics; llm_repair/ for the LLM loop
│   └── results/      # results.csv, scaling.csv, hypothesis_stats.csv, raw/*.txt, figures
└── spin/             # Promela models, scripts and results (SPIN owner)
```

## Setup (macOS arm64)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install eclipse-sumo==1.28.0 traci==1.28.0 sumolib==1.28.0 gymnasium numpy hypothesis mypy pylint matplotlib
export SUMO_HOME="$(python -c 'import sumo; print(sumo.SUMO_HOME)')"
brew install esbmc
```

## Reproduce the ESBMC results (repo root, venv active)

```bash
python verification/esbmc/scripts/smoke_test.py                 # expect: 13 of 13 cases ok
python verification/esbmc/scripts/check_phase_strings.py        # S1 part 2: no G/G conflict in the net file
python verification/esbmc/scripts/run_esbmc.py --all            # 31 entries -> esbmc/results/results.csv
python verification/esbmc/scripts/results_table.py              # Markdown summary of results.csv
python verification/esbmc/scripts/conformance_test.py --model v0 --level L1 --runs 30
python verification/common/replay_in_sumo.py --ce verification/esbmc/results/raw/G2-v0-L1.txt
python verification/esbmc/scripts/scaling_sweep.py --exp K && python verification/esbmc/scripts/scaling_sweep.py --plot
pytest -q verification/esbmc/baselines/test_hypothesis.py
```

ESBMC runs use the models in `esbmc/model/` and do not depend on `src/`. The replay and
conformance scripts run the real environment in `src/environment.py` of the current checkout:
the original code (v0) on `main`, or v1 after `git apply verification/esbmc/model/v1_fix.patch`.

## Main results

| Version | Holds (K = 16) | Violated, with a counterexample replayed in SUMO |
|---|---|---|
| v0 | S1, T1, T2, G1, C1 with the default parameters and the L0 stub | G2, L1, R1, P1; T1 with `yellow_time=0`; T2 and C1 with out-of-range actions; T2, G1, C1, G2 with the L1 stub (SUMO's static program) |
| v1 | all nine properties with the L1 stub; G2 for all `delta_time` in 1..7, `min_green` in 0..12, `max_green` in 11..16; G2 and C1 for unbounded executions (one-step induction) | none |

Defects: F1 max_green never enforced; F2 SUMO's static program runs until the first switch;
F3 out-of-range actions accepted; F4 `yellow_time=0` accepted; F5 the naive max-green fix fails
when `max_green` is not a multiple of `delta_time`.
