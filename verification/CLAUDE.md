# CSEE 6863 verification workspace

Goal: formally verify the traffic-signal control logic in `src/environment.py`
(SUMO + DQN). ESBMC-Python lives in `verification/esbmc/` (Edward);
SPIN/Promela lives in `verification/spin/` (teammate).

## Ground rules
- Branch `verification`; feature branches `esbmc/*` or `spin/*`; PR into `verification`. Never push to `main`.
- Never edit `src/` (D1: v1 = `verification/esbmc/model/v1_fix.patch` applied at run time to a
  temporary copy; see `verification/common/sumo_env.py`).
- `verification/esbmc/model/traci_stub.py` and `env_core_v*.py` are also executed as reference
  models by the teammate's SPIN scripts (`run_spin.py`, `check_traces.py`, `liveness.py`).
  Stop and ask Edward before changing them. The PR must mention `@LOOK4869` as plain text,
  without backticks: GitHub does not notify a mention inside backticks. (It is in backticks
  here only because a bare @name in CLAUDE.md is read as a file import.)
- Property IDs (S1 T1 T2 G1 G2 L1 L2 C1 R1 P1), default parameters and the results CSV
  schema are fixed in `verification/properties.md`. Do not invent new IDs.
- Results go to `verification/<tool>/results/results.csv` using the shared schema;
  raw tool output goes to `verification/<tool>/results/raw/*.txt` (`*.log` is git-ignored).
- Commit messages: `<area>: <imperative summary>`, area in {esbmc, spin, common, docs, src}.
- Code comments and commit messages in English.

## Environment (Edward, macOS arm64)
- Python venv: `source .venv/bin/activate` (Python 3.12, eclipse-sumo 1.28, traci, hypothesis);
  the activate script also exports `SUMO_HOME`.
- ESBMC: `esbmc` on PATH (Homebrew, `/opt/homebrew/bin/esbmc`). If it was installed another way,
  write its path here.

## How to run (repo root, venv active)
- ESBMC suite: `python verification/esbmc/scripts/run_esbmc.py --list`, then `--all` or a list of ids.
- Ad-hoc run: `python verification/esbmc/scripts/run_esbmc.py --harness h_G2 --version v1 --set K=20`
- Counterexample to actions: `python verification/esbmc/scripts/ce_to_actions.py verification/esbmc/results/raw/<id>.txt`
- Replay in SUMO: `python verification/common/replay_in_sumo.py --ce <raw file>` or `--actions 0,1,0`
- Model vs SUMO conformance: `python verification/esbmc/scripts/conformance_test.py --model v0 --level L1`

## ESBMC-Python rules learned the hard way
- Always pass `--tuple-node-flattener` (run_esbmc.py does); without it the solver is ~1000x slower.
- Keep unwinding assertions on; let run_esbmc.py compute `--unwindset` from `--show-loops`.
- Never name a method `set`; never name a helper `nondet_*`; annotate the type of every local.
- Pass a call's result through a typed local before handing it to a method (`k: int = f(x); self.m(k)`).
- Do not edit the 7 model lines listed in `INT_REWRITES` (run_esbmc.py) without re-running `S0-strings-str`.
- `--k-induction` disables its inductive step on this model; use `harnesses/h_G2_ind.py` instead.
- Do not use an object after the `try` that built it when its constructor cannot raise (v0): Homebrew ESBMC 8.6.0 leaves its fields unconstrained (see `results/raw/P1-v0-try-quirk.txt`). Probe with `accepts()` and build the object outside `try`, as `h_P1`/`h_R1` do. `h_G2_param` keeps the `try` form: it only runs on v1/v1naive, and the probe form is ~6x slower there.

## Known v0 findings
F1 max_green never enforced; F2 SUMO static program runs until the first switch;
F3 out-of-range action accepted; F4 yellow_time=0 accepted (no yellow);
F5 the naive max-green fix fails when max_green is not a multiple of delta_time.
