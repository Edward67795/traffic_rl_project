# SPIN verification

SPIN/Promela portion of the CSEE E6863 Formal Verification final project.
The target is the traffic-signal control logic in `src/environment.py`:
phase selection, yellow transitions, timing and directional service.
The DQN is abstracted as nondeterministic action inputs. Training and traffic
performance are outside this verification scope.

## Current status

**S3 is complete for the v0 model.** Seven properties now have executed checks:
S1, T1, T2, G1, C1, G2 and L1. The current matrix has **28 cases: 14 PASS and
14 FAIL**, with no UNKNOWN/TIMEOUT/ERROR. The eight new G2/L1 cases all FAIL;
the previous 20 S2 cases retain their verdicts after regression.

All 14 current finite counterexamples reproduce against the extracted Python
reference plus TraCI stub. The 96 finite conformance cases still match all
18,898 observation records. There are 14 passing test methods including timing
boundaries. These are model-level results; real SUMO validation and human model
review remain pending. L2 (S4) and v1 comparison (S5) are not implemented yet.

See [findings](FINDINGS.md), [current CSV](results/results.csv), and the
[stage-by-stage record](report.md). Do not extrapolate the results to other
parameters, v1 or the full Python/SUMO/DQN system.

## Documents and layout

- [Shared contract](../properties.md): authoritative IDs, parameters and CSV schema.
- [Joint workspace](../README.md): project context and ESBMC interface.
- [Source mapping](MODEL_MAPPING.md): abstractions and property observation points.
- [Findings](FINDINGS.md): actual results, witness explanations and limitations.
- [Experimental record](report.md): per-stage data, all attempts and final-report material.
- [AI context](node-spin.md): detailed pipeline, decisions and execution history.
- [AI instructions](AGENTS.md): scoped assistant entry point.

```text
verification/spin/
├── README.md, AGENTS.md, node-spin.md
├── MODEL_MAPPING.md, FINDINGS.md, report.md
├── models/
│   ├── controller.pml
│   └── properties.pml
├── scripts/
│   ├── check_traces.py
│   ├── run_spin.py
│   ├── replay_trail.py
│   └── test_verification.py
└── results/
    ├── results.csv
    ├── snapshots/              # Frozen stage CSVs and historical source
    └── raw/
        ├── s1-trace-comparison.json
        └── <case>-<UTC timestamp>/
```

## Prerequisites

SPIN, Python 3 and a C compiler/preprocessor must be on PATH. Tested on macOS
arm64 with SPIN 6.5.2, Apple Clang 21 and Python 3.13.7. Scripts use the Python
standard library. If SPIN is missing, install with `brew install spin`.

```sh
spin -V
cc --version
python3 --version
spin '-?'
```

Quote `-?` in zsh. SUMO/TraCI/gymnasium are not needed for the current reference
checks; they will be needed for real-source replay. No checkpoint, PyTorch or
GPU is required. Do not run `build_network.sh`: it overwrites the committed
network defining this verification baseline.

## Run verification

Run all commands from the repository root:

```sh
python3 verification/spin/scripts/run_spin.py --list
python3 verification/spin/scripts/run_spin.py --all
```

`--all` currently means 28 v0 cases: seven implemented properties across
`default`, `y0`, `any`, and `L1`. Select a stage to run its subset:

```sh
python3 verification/spin/scripts/run_spin.py --stage S2
python3 verification/spin/scripts/run_spin.py --stage S3
```

S2 runs 20 cases; S3 runs the eight G2/L1 cases. Other stages are not included.
Run individual cases by ID:

```sh
python3 verification/spin/scripts/run_spin.py T1-v0-y0 T2-v0-any C1-v0-L1
```

Each run selects one property and an isolated temporary build directory.
The runner generates with `spin -a`, compiles pan.c and searches with pan.
T2 uses `-a` acceptance-cycle detection in addition to assertions; other implemented
properties use `-DSAFETY`. Limits default to depth 100000, memory 512 MB and
120 seconds per subprocess. Override with `--depth`, `--memory`, `--timeout`.
The actual commands and limits are saved in each run's metadata.

Exit code 0 means all runs completed with PASS or witnessed FAIL and finite
witnesses matched the reference. ERROR/UNKNOWN/TIMEOUT or a failed witness
reference check produce nonzero. A property FAIL is an expected scientific
outcome, not necessarily a command error. Always read the CSV and logs.

The runner checks the fixed network before generation. It writes timestamped
raw evidence directories and updates CSV rows by tool/property/version/config,
retaining unrelated rows. Previous raw runs remain available. A rerun replaces
the current CSV entry for that case, even when limits have changed; its metadata
records the limits and exact evidence path.

## Trace conformance and monitor tests

```sh
python3 verification/spin/scripts/check_traces.py \
  --output verification/spin/results/raw/s1-trace-comparison.json
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/test_verification.py
```

The first command overwrites the trace summary after all comparisons succeed.
Expected defaults: `MATCH: 96 finite cases, 18898 observation records`. It checks
72 targeted and 24 seeded random cases against the read-only extracted Python
v0 core/stub, including elapsed time, signal, controller state and static cursor.
This finite comparison is supplementary evidence, not exhaustive verification.
Optional `--random-cases` and `--seed` change the suite and expected counts.

The tests inject invalid signal codes, direct switches, 2/3-second yellow,
wrong-direction returns, infinite yellow, 9/10-second green and phase mismatches.
They also check that violations returning process exit code 0 are classified
correctly and that actual search-depth exhaustion becomes UNKNOWN. Timing tests exercise
60/61-second greens, 66/67-second waits, both directions, yellow inclusion and
wait resets. y0 uses the configured 60-second wait limit.

## Counterexamples

Each FAIL directory contains `trail.txt`, `replay.txt` and `witness.json` in
addition to `metadata.json`, generation/compile logs and verifier output.
`trail.txt` stores the original trail bytes under a trackable text filename.
Use the evidence directory linked in the CSV/FINDINGS:

```sh
python3 verification/spin/scripts/replay_trail.py \
  verification/spin/results/raw/<case>-<UTC-timestamp>
```

Replace the placeholder with a real run directory. The script checks model
hashes, chooses matching run-local or stage-snapshot source, restores the trail
in a temporary directory and replays with identical
preprocessor flags. Replay prints ACTION/OBS events and the failing assertion;
a replay process exit code of 0 does not mean the property passed.

`witness.json` includes actions, recent sampled states and the reference
violation. A started decision counts even when the assertion fails partway
through it. DFS witnesses are not guaranteed shortest. Controller age can be
saturated in Promela while the Python reference retains its exact larger value.

The common SUMO replay imports current src/ and has not yet been run here.
Do not apply v1 patches to the user's checkout for replay. Finite replay cannot
establish an infinite L2 guarantee.

## Semantics and interpretation

Defaults: delta 5 s, yellow 3 s, min green 10 s, max green 60 s, warmup 10 s.
Signal codes 0/1/2/3 mean NS green/NS yellow/EW green/EW yellow.
`default`, `y0` and `any` use simplified fidelity L0; scenario `L1` includes
the autonomous static program. Scenario L1 is distinct from property L1.

v0 warmup does not increase controller phase_duration. The model distinguishes
controller age from observed green duration, preserves invalid-action fallback
and missing max-green enforcement, and follows source update ordering. Static
sampling uses the reference stub's 43 initial samples, then 3/42/3/42; real SUMO
boundary validation is pending. See MODEL_MAPPING.md for counter saturation.

T1 samples actual simulated seconds, so transient zero-time yellow cannot hide
`y0`. T2 checks duration/opposite successor and eventual completion for observed
yellow. T2/y0 is vacuous because no yellow is observed; T1/y0 detects the missing
interval. C1 checks after each complete decision, provisionally following the
ESBMC harness while the referenced D4 decision remains unavailable.

## Stage guide and live progress

Last updated: 2026-11-06 (Asia/Shanghai). **Current checkpoint: S3 complete.**
Current v0 matrix: 28 cases, 14 PASS / 14 FAIL. Next stage: S4 (L2/fairness).
No S4 result is claimed yet.
Stage names are work labels, not shared property IDs (stage S1 != property S1).

| Stage | Meaning | Deliverables / completion gate | Current status |
|---|---|---|---|
| S0: environment | Establish a working, reproducible toolchain | Repository/contract inspection; SPIN/compiler versions; successful and failing safety/LTL smoke checks | Complete |
| S1: v0 abstraction | Translate source control behavior into a finite-state model | Phase/action/timing/static-takeover mapping; documented abstractions; matching reference traces | Initial model complete: 96 finite cases match; real SUMO fidelity pending |
| S2: safety/transitions | Check legal signals, yellow transitions, minimum green and phase consistency | S1/T1/T2/G1/C1 matrix; exhaustive runs; reviewed and reference-reproduced finite failures | Complete for v0: 20 cases, 14 PASS / 6 FAIL |
| S3: timing/waiting | Check maximum green and directional waiting limits | G2 displayed/controller age checks; L1 wait counters; 60/61 and 66/67-second boundaries; evidence and snapshot | Complete for v0: 8 FAIL cases reference-reproduced; boundaries and S2 regression passed |
| S4: infinite liveness | Determine whether both directions receive green infinitely often | L2 acceptance-cycle runs with/without explicit agent fairness; prefix/cycle explanations | Not started |
| S5: repaired model | Mirror exactly FIX-1..4 and compare v0/v1 | v1 mapping; aligned matrix; rejected-input semantics; non-divisible timing checks | Not started |
| S6: final delivery | Assemble reproducible evidence and report | Final suite/CSV; SUMO cross-checks; human-review status; joint-tool comparison and report | In progress for documentation only; final validation pending |

Update this table when a stage begins, reaches a validation milestone or ends.
Completed means the named stage gate was met under documented assumptions, not
that the full Python/SUMO/DQN system was proved. Human model review and real
SUMO checks remain pending. Current blockers/limitations are in FINDINGS.md;
all attempts and original measurements are retained in report.md.

R1/P1 stay in ESBMC scope. Process weak fairness must not be confused with fair
agent action selection. Real episode termination is omitted in the ongoing
control abstraction and must be stated in future liveness results.

G2 combines per-second displayed green age and controller phase_duration at
completed decisions, matching the shared ESBMC harness. Its static-program FAIL
currently comes from the controller counter, while displayed green age is 29 s;
it must not be described as a 61-second displayed-green witness. L1 includes
warmup/yellow and resets only on the direction's green. Its limit is 66 s by
default and 60 s in y0. See report.md for full component and sampling details.

## Evidence and collaboration rules

CSV columns are exactly:

```text
tool,property,version,config,bound,result,ce_length,time_s,memory_mb,notes
```

PASS requires a completed exhaustive search under stated assumptions; depth or
memory exhaustion is UNKNOWN. Allowed results also include FAIL, TIMEOUT, ERROR.
`bound` records actual depth reached. ce_length counts started decision events
and is blank for PASS. time_s is verifier wall time only; compilation/generation
have separate metadata timings. memory_mb is pan's reported total actual memory.

Keep changes in this directory. Do not modify source, ESBMC, common scripts,
shared contracts or network files without authorization. Do not automatically
commit, push, create PRs or merge. Use English for code/docs and Chinese with
the user. Final reporting must compare tool guarantees and limitations and
separately record pending human review and real SUMO evidence.
