# SPIN verification

SPIN/Promela portion of the CSEE E6863 Formal Verification final project.
The target is the traffic-signal control logic in `src/environment.py`:
phase selection, yellow transitions, timing and directional service.
The DQN is abstracted as nondeterministic action inputs. Training and traffic
performance are outside this verification scope.

## Current status

**S2 is implemented for v0: S1, T1, T2, G1 and C1.** The executed 20-case matrix
contains 14 PASS and 6 FAIL; see [findings](FINDINGS.md) and [CSV](results/results.csv).
These are model-level results under the documented abstractions. All six finite
counterexamples reproduce against the extracted Python reference plus TraCI
stub. Real SUMO validation and human model review are pending.

The 96 finite conformance cases still match all 18,898 observation records.
G2/L1 (S3), L2 (S4), and v1 comparison (S5) remain pending. Do not extrapolate
these v0 results to v1, other parameter configurations or the full SUMO system.

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

`--all` currently means the 20 implemented v0 S2 cases: five properties across
`default`, `y0`, `any`, and `L1`. Other stages are not silently included.
Run individual cases by ID:

```sh
python3 verification/spin/scripts/run_spin.py T1-v0-y0 T2-v0-any C1-v0-L1
```

Each run selects one property and an isolated temporary build directory.
The runner generates with `spin -a`, compiles pan.c and searches with pan.
T2 uses `-a` acceptance-cycle detection in addition to assertions; other S2
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
correctly and that actual search-depth exhaustion becomes UNKNOWN.

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
hashes, restores the trail in a temporary directory and replays with identical
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

## Pipeline and remaining work

Stage names are work labels, not shared property IDs.

| Stage | Status / completion gate |
|---|---|
| S0 | Toolchain smoke checks complete |
| S1 | v0 model and finite reference comparison implemented; real SUMO fidelity unconfirmed |
| S2 | S1/T1/T2/G1/C1 matrix executed; all six finite failures reference-reproduced |
| S3 | Pending: G2/L1 with timing/wait boundary evidence |
| S4 | Pending: L2 with/without explicit agent fairness |
| S5 | Pending: exact v1 FIX-1..4 model and comparison |
| S6 | Pending: final suite, SUMO checks, human-review status and joint-report material |

R1/P1 stay in ESBMC scope. SPIN process weak fairness alone must not be confused
with fair agent action selection. Real episode termination is omitted in the
ongoing control abstraction and must be stated in future liveness results.

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
