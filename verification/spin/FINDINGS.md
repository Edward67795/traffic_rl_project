# SPIN findings: v0 through S3

Current checkpoint: v0 through S3; see the appended S3 results below.
The S2 baseline below is retained as historical evidence.

Run date: 2026-11-06. Tool: SPIN 6.5.2; Apple Clang 21; Python 3.13.7.
Scope: v0 only, S1/T1/T2/G1/C1, default timing except y0. G2/L1 were not implemented at the S2 checkpoint; they are now covered in S3.
v1 and L2 remain pending. No real SUMO run or human model review is
claimed here. Results apply to the documented finite-state abstractions.

## Executed matrix

| Property | default (L0) | y0 (L0) | any (L0) | static program (L1) |
|---|---|---|---|---|
| S1 | PASS | PASS | PASS | PASS |
| T1 | PASS | FAIL | PASS | PASS |
| T2 | PASS | PASS* | FAIL | FAIL |
| G1 | PASS | PASS | PASS | FAIL |
| C1 | PASS | PASS | FAIL | FAIL |

Actual totals: **14 PASS, 6 FAIL, 0 UNKNOWN/TIMEOUT/ERROR**.
All PASS searches completed exhaustively without depth/memory truncation.
T2 checks timing/direction assertions and the yellow_completion LTL claim with
acceptance-cycle search. Other rows use safety search. No fairness option is
needed/used for these checks. The ongoing single-controller abstraction has
no modeled external blocking or scheduler starvation.

* T2/y0 is vacuous: there is no sampled yellow, so the conditional observed-yellow
obligation is never triggered. T1/y0 fails on the direct change. These two
results must be presented together; T2/y0 does not establish zero-yellow safety.

The S1 preflight checks all four network strings against protected G/G conflicts
in the foes matrix, assuming signal link index i corresponds to request index i
for this fixed network. Permissive g is not protected G. C1 is sampled at completed
decisions, following the existing harness; D4 is unavailable and the interpretation
remains provisional. Static boundary timing follows the reference stub pending
real SUMO validation.

## Counterexamples

The verifier reports the first DFS witness, not necessarily a shortest witness.
ce_length counts ACTION events, including a partially executed failing decision.
Reported times below are from replay against the Python reference, measured
before the failing second or at the completed C1 decision boundary.

| Property/scenario | Decisions | Reference time (s) | Cause | Evidence |
|---|---|---|---|---|
| T1/y0 | 17 | 90 | Direct NS green to EW green with no observed yellow | [witness](results/raw/T1-v0-y0-20261106T084450210734Z/witness.json), [verifier](results/raw/T1-v0-y0-20261106T084450210734Z/verify.txt), [replay](results/raw/T1-v0-y0-20261106T084450210734Z/replay.txt) |
| T2/any | 35 | 189 | An invalid action changes controller phase; a later yellow returns to NS instead of the opposite green | [witness](results/raw/T2-v0-any-20261106T084452869814Z/witness.json), [verifier](results/raw/T2-v0-any-20261106T084452869814Z/verify.txt), [replay](results/raw/T2-v0-any-20261106T084452869814Z/replay.txt) |
| T2/L1 | 17 | 93 | Static program already shows EW; controller takeover yellows EW and returns to EW | [witness](results/raw/T2-v0-L1-20261106T084453446889Z/witness.json), [verifier](results/raw/T2-v0-L1-20261106T084453446889Z/verify.txt), [replay](results/raw/T2-v0-L1-20261106T084453446889Z/replay.txt) |
| G1/L1 | 28 | 145 | Controller age permits takeover while displayed EW green has lasted only 9 seconds | [witness](results/raw/G1-v0-L1-20261106T084455513246Z/witness.json), [verifier](results/raw/G1-v0-L1-20261106T084455513246Z/verify.txt), [replay](results/raw/G1-v0-L1-20261106T084455513246Z/replay.txt) |
| C1/any | 33 | 181 | Invalid action -1 is stored as current_phase while the signal falls back to NS | [witness](results/raw/C1-v0-any-20261106T084457547770Z/witness.json), [verifier](results/raw/C1-v0-any-20261106T084457547770Z/verify.txt), [replay](results/raw/C1-v0-any-20261106T084457547770Z/replay.txt) |
| C1/L1 | 7 | 45 | After seven hold decisions the autonomous signal is yellow but controller phase remains NS | [witness](results/raw/C1-v0-L1-20261106T084458111435Z/witness.json), [verifier](results/raw/C1-v0-L1-20261106T084458111435Z/verify.txt), [replay](results/raw/C1-v0-L1-20261106T084458111435Z/replay.txt) |

All six action sequences reproduce the selected assertion in the read-only
extracted Python v0 + TraCI stub. This is an independent execution of the
reference extraction, not verification of the full Python/SUMO implementation.
The original, unminimized actions are in each witness JSON. The raw trail is
preserved as trail.txt; replay_trail.py verifies model hashes before replaying it.

The G1 witness also illustrates the age abstraction: Promela controller age may
be saturated at 76 while the reference age is 135. Both exceed min_green and
enable exactly the same controller branch. The independent displayed green
counter is 9 and correctly triggers the property violation.

## Reproduction and evidence

From repository root:

```sh
python3 verification/spin/scripts/run_spin.py --all
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/test_verification.py
python3 verification/spin/scripts/check_traces.py \
  --output verification/spin/results/raw/s1-trace-comparison.json
```

Expected: the matrix above; 10 test methods pass; 96 reference trace cases and
18,898 sampled/boundary records match. Tests include 15 synthetic monitor
executions (including acceptance-cycle and actual depth-exhaustion cases).
Property FAIL outcomes do not cause the suite to exit nonzero when their
finite witnesses also reproduce in the reference. UNKNOWN/TIMEOUT/ERROR and
reference mismatches require investigation.

For each current CSV row, notes links to its timestamped evidence directory.
metadata.json records exact generation, compilation, help, verification and
replay commands; versions; limits; network digest; model/runner digests; exit
statuses; timings and witness interpretation. verify.txt is original pan output.
CSV time_s measures the verifier subprocess wall time, excluding generation,
compilation and reference/replay; memory_mb is pan's total actual memory.
Prior raw runs are retained; results.csv points to the current run per case.

## Remaining limits and next stage

- Full source/SUMO conformance and finite witness replay remain pending.
- Human review of the generated model remains pending, as required by the proposal.
- These results do not replace ESBMC evidence and do not claim equivalent coverage.
- The next work stage is S3: G2 and L1, with explicit observed-green and wait
  counters and boundary checks. L2 fairness and v1 FIX-1..4 follow in S4/S5.

## S3 results: maximum green and bounded waiting (2026-11-06)

Current combined v0 matrix is 28 cases: 14 PASS, 14 FAIL. The eight S3 cases
are all FAIL, with finite witnesses replayed and reference-reproduced. Re-running
the 20 S2 cases preserved all prior verdicts. No project UNKNOWN/TIMEOUT/ERROR
occurred. L2/v1, real SUMO and human model review remain pending.

| Case | Result | Depth | CE decisions | Reference pre-step/boundary time_s | Component | Observed green age | Controller age | NS/EW wait | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| G2-v0-default | FAIL | 380 | 11 | 60 | observed_green | 61 | 50 | 0/61 | [witness](results/raw/G2-v0-default-20261106T090427766230Z/witness.json) |
| G2-v0-y0 | FAIL | 380 | 11 | 60 | observed_green | 61 | 50 | 0/61 | [witness](results/raw/G2-v0-y0-20261106T090428544566Z/witness.json) |
| G2-v0-any | FAIL | 380 | 11 | 60 | observed_green | 61 | 50 | 0/61 | [witness](results/raw/G2-v0-any-20261106T090429354453Z/witness.json) |
| G2-v0-L1 | FAIL | 474 | 13 | 75 | controller_age | 29 | 65 | 32/0 | [witness](results/raw/G2-v0-L1-20261106T090430125413Z/witness.json) |
| L1-v0-default | FAIL | 408 | 12 | 66 | directional_wait | 67 | 56 | 0/67 | [witness](results/raw/L1-v0-default-20261106T090430915881Z/witness.json) |
| L1-v0-y0 | FAIL | 370 | 11 | 60 | directional_wait | 61 | 50 | 0/61 | [witness](results/raw/L1-v0-y0-20261106T090431686597Z/witness.json) |
| L1-v0-any | FAIL | 408 | 12 | 66 | directional_wait | 67 | 56 | 0/67 | [witness](results/raw/L1-v0-any-20261106T090432492617Z/witness.json) |
| L1-v0-L1 | FAIL | 1630 | 48 | 254 | directional_wait | 64 | 63 | 0/67 | [witness](results/raw/L1-v0-L1-20261106T090433253634Z/witness.json) |

G2/default, y0 and any fail on 61 counted green intervals, even though controller
age is only 50: warmup was omitted from its accounting. G2/static first fails
the separate controller-age check (65 >60) while displayed green age is 29.
This matches the shared double-check harness and does not establish overlong
displayed green in that particular witness.

L1/default and any reach EW wait 67 >66; y0 reaches 61 >60. Static L1 eventually
fails after online takeover allows repeated NS requests to starve EW. The current
DFS witness is 48 decisions and is not claimed shortest. Other properties are
disabled during each selected check, so an earlier violation of another property
does not stop these searches.

S3 validation: 14 test methods passed (32 synthetic monitor searches in total);
96 finite source-reference cases still match 18,898 records. The raw test,
trace, S3 matrix, S2 regression and archived/new replay outputs are linked from
the S3 entry in report.md. Frozen CSVs: [S3 only](results/snapshots/s3-v0-results.csv)
and [through S3](results/snapshots/through-s3-v0-results.csv). Detailed measured
time/memory, assumptions and source digests are preserved in the raw metadata.
