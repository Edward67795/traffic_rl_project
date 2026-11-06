# SPIN findings: S2 v0 baseline

Run date: 2026-11-06. Tool: SPIN 6.5.2; Apple Clang 21; Python 3.13.7.
Scope: v0 only, S1/T1/T2/G1/C1, default timing except y0. v1 and G2/L1/L2
are not implemented in this stage. No real SUMO run or human model review is
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
