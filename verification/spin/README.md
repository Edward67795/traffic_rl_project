# SPIN verification

SPIN/Promela portion of the CSEE E6863 Formal Verification final project.
The target is the traffic-signal control logic in `src/environment.py`:
phase selection, yellow transitions, timing and directional service.
The DQN is abstracted as nondeterministic action inputs. Training and traffic
performance are outside this verification scope.

## Current status

Coordination status (2026-11-06): on hold at the user's request while the
teammate progresses. Human review is deferred, not completed. Resume on user
instruction; technical results below remain unchanged.

**S6 technical validation is complete; human review and joint-report sign-off
remain pending.** The formal dataset is unchanged:72 cases,46 PASS/26 FAIL.
A fresh temporary code copy reproduced all verdicts, depths and decision counts.

Real SUMO1.28.0 validation directly executed full source:38 model/source cases
matched7,205 projected records, plus one expected L0 negative-control mismatch.
Of21 original finite assertion prefixes,12 reproduced the target and9 did not;
all9 non-reproduced prefixes are L0 cases. These replay results are separate
from formal verdicts. Short source-backed traces establish T1/G2/L1 defects,
and the v1 delta12/min0/max11 bug was confirmed in actual patched-source SUMO.

Use L1 and actual replay for conclusions about original initialization. L0
omits autonomous behavior and is not automatically a conservative source model.
No controller/ESBMC/shared patch was changed. Source-backed technical report:
[SPIN_REPORT.md](SPIN_REPORT.md); human review: [checklist](REVIEW_CHECKLIST.md).
The teammate's actual ESBMC results CSV is absent in this checkout, so numerical
joint-tool comparisons remain pending supplied evidence.

## Documents and layout

- [Shared contract](../properties.md): authoritative IDs, parameters and CSV schema.
- [Joint workspace](../README.md): project context and ESBMC interface.
- [Source mapping](MODEL_MAPPING.md): abstractions and property observation points.
- [Findings](FINDINGS.md): actual results, witness explanations and limitations.
- [Technical report draft](SPIN_REPORT.md): SPIN section for the joint report.
- [Real SUMO validation](SUMO_VALIDATION.md): source traces and non-reproduced prefixes.
- [Human review checklist](REVIEW_CHECKLIST.md): explicit outstanding review.
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
│   ├── test_verification.py
│   ├── liveness.py
│   ├── check_liveness.py
│   ├── explain_l2_counterexample.py
│   ├── check_v1.py
│   ├── validate_sumo.py, audit_network.py
│   └── audit_results.py, reproduce.py
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

Quote `-?` in zsh. SUMO/TraCI/gymnasium are not needed for the finite extraction checks;
they are installed separately for the real-source checks below. No checkpoint, PyTorch or
GPU is required. Do not run `build_network.sh`: it overwrites the committed
network defining this verification baseline.

## Run verification

Run all commands from the repository root:

```sh
python3 verification/spin/scripts/run_spin.py --list
python3 verification/spin/scripts/run_spin.py --all
```

`--all` currently means 72 implemented v0/v1 cases. Stage selection is explicit:

```sh
python3 verification/spin/scripts/run_spin.py --stage S2
python3 verification/spin/scripts/run_spin.py --stage S3
python3 verification/spin/scripts/run_spin.py --stage S4
python3 verification/spin/scripts/run_spin.py --stage S5
```

S2/S3/S4 retain their original 20/8/12 v0 cases. S5 runs 32 additional cases:
20 v1 normal-operation checks plus six G2 parameter pairs. v1 normal operation
uses default/static scenarios and legal actions; y0 and invalid inputs are
separate rejection checks, not silently omitted PASS rows.
Run individual cases by ID:

```sh
python3 verification/spin/scripts/run_spin.py T1-v0-y0 T2-v0-any C1-v0-L1
```

Each run selects one property and an isolated temporary build directory.
The runner generates with `spin -a`, compiles pan.c and searches with pan.
T2 and L2 use `-a` acceptance-cycle detection; T2 also has timing assertions; other implemented
properties use `-DSAFETY`. Limits default to depth 100000, memory 512 MB and
120 seconds per subprocess. Override with `--depth`, `--memory`, `--timeout`.
The actual commands and limits are saved in each run's metadata.

Exit code 0 means all runs completed with PASS or witnessed FAIL, finite
witnesses matched the reference, and L2 cycle interpretations/reference closures
passed validation. ERROR/UNKNOWN/TIMEOUT or a failed witness
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

`witness.json` includes actions, sampled states and finite-reference violations
or L2 prefix/period, sampled services, fairness and reference-closure analysis. A started decision counts even when the assertion fails partway
through it. DFS witnesses are not guaranteed shortest. Controller age can be
saturated in Promela while the Python reference retains its exact larger value.

The common SUMO replay imports current src/; selected T1/G2/C1 source traces
were reproduced through that unchanged shared entry point in S6.
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
boundary behavior was confirmed for this build in S6 (see SUMO_VALIDATION.md). See MODEL_MAPPING.md for counter saturation.

T1 samples actual simulated seconds, so transient zero-time yellow cannot hide
`y0`. T2 checks duration/opposite successor and eventual completion for observed
yellow. T2/y0 is vacuous because no yellow is observed; T1/y0 detects the missing
interval. C1 checks after each complete decision, provisionally following the
ESBMC harness while the referenced D4 decision remains unavailable.

## L2 fairness and infinite-execution interpretation

L2 is `(GF observed_NS) AND (GF observed_EW)`. Observed greens are sampled only
on simulated seconds. Positive decision time and the ongoing controller loop
are explicit assumptions; real episode termination is omitted.

| Mode in case ID/config | Premise of the LTL implication | default / y0 / any / static L1 |
|---|---|---|
| none | true (unconditional service) | FAIL / FAIL / FAIL / FAIL |
| request | GF request0 AND GF request1 at decision input events | PASS / PASS / FAIL / PASS |
| eligible | GF eligible_request0 AND GF eligible_request1 | PASS / PASS / PASS / PASS |

Eligibility means phase_duration >=min_green when the input is received. These
are input assumptions, not implemented controller guarantees. No pan -f is used.
Request fairness is insufficient under invalid actions: requests for EW can
always occur before min_green after invalid actions reset the age. The eligible
premise is stronger; do not rename its result unconditional liveness.
GF requests permit arbitrarily long finite gaps, so these premises do not
establish L1's bounded waiting-time guarantee.

A cycle of the negated fairness premise was found for every conditional mode
and scenario, demonstrating that the input premise is realizable. Synthetic
controls also test intentional premise vacuity, starvation and phantom events.
They are auxiliary checks, not additional PASS/FAIL rows in the shared CSV.

Reproduce auxiliary checks with fresh output directories:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/check_liveness.py \
  --output verification/spin/results/raw/s4-controls-rerun
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/explain_l2_counterexample.py \
  --output verification/spin/results/raw/s4-short-witness-rerun
```

Choose unused output paths: existing evidence is deliberately not overwritten.
Original [control data](results/raw/s4-liveness-controls/summary.json) and the
[compact witness](results/raw/s4-short-request-fair-witness/analysis.json) are retained.
The compact policy prepares with [0,0,2,1,0], then repeats [0,2,1,0]: its 26-second
cycle has both legal requests, but only NS/yellow. This illustrative constrained
input policy leaves the controller unchanged; it is not claimed shortest.

A saved acceptance trail contains a prefix and one loop. ce_length counts
started ACTION events in that prefix plus one loop; the marker may split a
decision. witness.json separates both counts and records time samples per loop.
Repeating the rotated action word closes the documented Python-reference state
projection with positive time; this is supplementary evidence, not a finite
simulation proof of infinite liveness in real SUMO.

## v1 fixes, input rejection and parameter scope

VERSION=1 mirrors the existing patch; the default VERSION=0 preserves v0.

| Fix | Model behavior |
|---|---|
| FIX-1 | If controller age +delta exceeds max, force the opposite action before existing min-green logic |
| FIX-2 | Reject illegal actions before the forced-switch check; do not advance time |
| FIX-3 | Preserve parameter and both reachable-switch-point checks exactly |
| FIX-4 | Set NS online before warmup and include warmup in controller age |

Rejection emits REJECT and ends the abstract execution. ABORT captures unchanged
control/time state on action rejection. We do not run these terminal error paths
as normal L2 executions or label them successful traffic control. The v1/y0
comparison is constructor rejection, not T1 PASS. v1/any rejects invalid requests;
legal inputs are covered by the normal-operation matrix.

```sh
python3 verification/spin/scripts/check_traces.py --version v1 \
  --output verification/spin/results/raw/s5-v1-trace-comparison.json
python3 verification/spin/scripts/check_v1.py \
  --output verification/spin/results/raw/s5-v1-contract-rerun.json
python3 verification/spin/scripts/run_spin.py G2-v1-default-delta_gt_max
```

Choose a fresh check_v1 output file: prior contract evidence is not overwritten.
The parameter probe intentionally yields FAIL and returns a valid witness.
The patch admits delta12/min0/max11 because both computed first switch points
(10 and 0) are <=11, but a new green still lasts a whole 12-second decision.
The saved witness reaches green12 at pre-step t24, controller age11. A potential
remedy is an additional admissibility restriction or redesigned intra-decision
control, requiring shared-owner review; neither has been applied here.

Five other probes (delta7, max61, delta3/max16, min0/delta7/max11,
min12/delta1/max16) pass G2 in v1. These selected examples do not constitute a
universal parameter proof. All raw metrics and aligned v0 rows are retained.

## S6 source validation and isolated reproduction

The current tested live runtime is Python3.13.7 with SUMO1.28.0. A slow/restarting
Python3.12 Homebrew download was cancelled; no3.12 run is claimed. The virtual
environment is Git-ignored. Exact package pins are in requirements-sumo.txt.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r verification/spin/requirements-sumo.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python verification/spin/scripts/validate_sumo.py \
  --output verification/spin/results/raw/s6-sumo-rerun
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python verification/spin/scripts/audit_network.py \
  --output verification/spin/results/raw/s6-network-rerun.json
python3 verification/spin/scripts/audit_results.py
python3 verification/spin/scripts/reproduce.py \
  --output verification/spin/results/raw/s6-isolated-rerun
```

Choose unused output paths. Live validation sets SUMO_HOME internally and needs
local TraCI sockets. v1 is patched only in a temporary copy. Independent live
monitors do not import the shared stub. Reproduction uses a fresh temporary
code tree and the installed toolchain, writes separate results, and leaves
current CSV unchanged. The completed72-case reproduction matched verdict,
depth and CE counts; wall time was64.059 s including compilation.

[SUMO validation](SUMO_VALIDATION.md) explains the12/21 target replays, nine L0
non-reproductions, actual static boundaries and additional concrete source
witnesses. [Replay CSV](results/sumo-replay.csv) is supplementary data, not the
shared formal-results schema. The official-library network audit confirmed all14
TLS/request indices correspond and zero protected G/G conflicts in all phases.

Human review is not completed by these commands. Please use REVIEW_CHECKLIST.md
alongside the mapping/models and source evidence. Do not replace pending reviewer
fields with a successful automated test result. The joint report also needs the
teammate's actual ESBMC metrics/results, not copied expected values.

## Stage guide and live progress

Last updated: 2026-11-06 (Asia/Shanghai). **Current checkpoint: S6 technical validation complete; human review pending.**
Current formal dataset:72 cases,46 PASS/26 FAIL. Live source results and
non-reproduced L0 prefixes are separately archived. Joint evidence/sign-off is pending.
The accepted wide-delta v1 failure remains an open finding, not silently repaired.
Stage names are work labels, not shared property IDs (stage S1 != property S1).

| Stage | Meaning | Deliverables / completion gate | Current status |
|---|---|---|---|
| S0: environment | Establish a working, reproducible toolchain | Repository/contract inspection; SPIN/compiler versions; successful and failing safety/LTL smoke checks | Complete |
| S1: v0 abstraction | Translate source control behavior into a finite-state model | Phase/action/timing/static-takeover mapping; documented abstractions; matching reference traces | Initial model complete;96 finite reference cases match;38 S6 source cases match including both versions |
| S2: safety/transitions | Check legal signals, yellow transitions, minimum green and phase consistency | S1/T1/T2/G1/C1 matrix; exhaustive runs; reviewed and reference-reproduced finite failures | Complete for v0: 20 cases, 14 PASS / 6 FAIL |
| S3: timing/waiting | Check maximum green and directional waiting limits | G2 displayed/controller age checks; L1 wait counters; 60/61 and 66/67-second boundaries; evidence and snapshot | Complete for v0: 8 FAIL cases reference-reproduced; boundaries and S2 regression passed |
| S4: infinite liveness | Determine whether both directions receive green infinitely often | L2 acceptance-cycle runs with/without explicit agent fairness; prefix/cycle explanations | Complete for v0: 12 cases, 7 conditional PASS / 5 FAIL; cycle and feasibility evidence retained |
| S5: repaired model | Mirror exactly FIX-1..4 and compare v0/v1 | v1 mapping; aligned matrix; rejected-input semantics; non-divisible timing checks | Complete: 20 v1 default PASS; six parameter pairs (v1 5 PASS/1 FAIL); 42 contract traces match |
| S6: final delivery | Assemble reproducible evidence and report | Final suite/CSV; SUMO cross-checks; human-review status; joint-tool comparison and report | Technical checks/report draft complete; human model review and joint evidence/sign-off pending |

Update this table when a stage begins, reaches a validation milestone or ends.
Completed means the named stage gate was met under documented assumptions, not
that the full Python/SUMO/DQN system was proved. Human model review remains pending; selected real
SUMO checks are completed and their limits are documented. Current blockers/limitations are in FINDINGS.md;
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
separately record pending human review, completed finite SUMO evidence and
its limits.
