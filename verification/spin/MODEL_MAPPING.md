# v0 model mapping (S1-S3 stages)

The current model implements v0 control flow and selected shared checks:
S1, T1, T2, G1, C1, G2 and L1. The runner emits a shared-format results CSV.
v1 and L2 remain pending.

| Source / reference | Promela |
|---|---|
| environment.py `_apply_action` | Decision branch tests action difference and MIN_GREEN; yellow loop then show_green |
| `_set_yellow_phase` | show_yellow converts the displayed signal, not current_phase |
| `_set_phase` | show_green displays NS for invalid action; stores the actual action in current_phase |
| `reset` warmup | 10 tick calls; controller age stays zero |
| `step` delta loop | DELTA_TIME tick calls, each followed by increment_age |
| traci_stub.py static cursor | sp_index, sp_left; 43 initial samples, subsequent 42/3/42/3 |
| setRedYellowGreenState | online becomes true and permanently disables autonomous static advancement |

Codes 0/1/2/3 mean NS green/NS yellow/EW green/EW yellow. The original strings
are retained in the shared contract. Static-program sampling follows the existing
stub, pending comparison with real SUMO. Fidelity L0 disables autonomous updates;
it does not claim to reproduce all SUMO behavior.

Each tick observes the displayed state before advancing the autonomous program.
Controller updates follow the simulation call in source order. DONE records are
emitted after warmup and after each complete decision, including static updates
that occur at the final tick. Zero-time yellow assignment is not an observed
second. S2 monitors sample inside tick accordingly, before autonomous advancement.

The non-TRACE build omits absolute elapsed time, episode termination and growing
decision numbers. It describes an ongoing controller. TRACE mode is explicitly
finite, supplies fixed actions and records exact elapsed seconds; it is for
conformance testing only and must never be used for an unbounded L2 proof.

Controller age is projected to min(actual_age, AGE_CAP), where
AGE_CAP = MAX_GREEN + MIN_GREEN + DELTA_TIME + 1. For this v0 model the only
control comparison using age is against MIN_GREEN, so the projection preserves
all choices and signal transitions above the cap. Future v1 checks/monitors must
reassess that abstraction. G1 now tracks displayed green age, saturated at MIN_GREEN + 1;
T2 tracks yellow age saturated at 3. These preserve the respective >= threshold
checks. Counters not used by the selected property remain unchanged. S3 adds G2 displayed-green age and L1 directional wait counters as described below.

Supported parameter domain currently requires DELTA_TIME > 0, YELLOW_TIME >= 0,
MIN_GREEN >= 0, MAX_GREEN >= 1. These model-domain assertions are not v0 input
validation and do not claim coverage of ESBMC R1 or P1. Current conformance cases
exercise delta 1/5/7 and yellow 0/3 with default minimum and maximum.

## Reproduce the finite conformance check

From repository root:

```sh
python3 verification/spin/scripts/check_traces.py \
  --output verification/spin/results/raw/s1-trace-comparison.json
```

Expected: all deterministic edge cases and seeded random cases MATCH. The checker
compares every pre-second and post-decision record to the read-only Python
extraction plus stub, including controller age projection, signal, phase,
online takeover, static cursor and elapsed time. It checks full trace lengths,
not merely a matching prefix. Builds use temporary directories. A mismatch or
SPIN error fails the command. Reference and model hashes are included in evidence.

This is a finite conformance check, not an exhaustive verification result and
not a real SUMO comparison. No shared property receives PASS from this command.

## S2 monitor mapping

The runner defines exactly one CHK_* macro per run. observe_second is in the
same deterministic tick as the sampled signal; it does not modify controller
variables. check_boundary runs only after complete decisions, not after warmup.

| Property | Mechanism | Observation point |
|---|---|---|
| S1 | Codebook invariant plus fixed-network preflight of protected G/G conflicts | Every second; codebook checked before generation |
| T1 | Assert no consecutive NS/EW green without a sampled yellow | Every second, both directions |
| T2 | Assert yellow age >=3 and next green differs from last_green; yellow_completion LTL requires eventual green | Every second, plus acceptance-cycle search |
| G1 | Assert displayed green_age >=MIN_GREEN whenever a green exits | Every second |
| C1 | Assert current_phase is 0/1 and matches signal | Each completed decision; provisional D4 interpretation |

T2 is a conjunction of its timing/direction assertions and the sole generated
LTL claim. Its finite first-failing assertion also suffices for FAIL. A PASS
means both assertion and acceptance-cycle searches completed. No scheduler
fairness flag is used for these single-controller checks.

T2/y0 is conditionally vacuous because there is no sampled yellow. Missing
yellow is detected by T1/y0; a T2/y0 PASS is not a zero-yellow safety guarantee.

For S1, the fixed-network preflight validates the four exact state strings,
42/3/42/3 durations, 14 link/request indices, foes symmetry and all protected
G/G conflicts. As in the shared reference checker, signal link i is interpreted
as junction request i. This network-specific mapping is an explicit assumption,
not a general parser guarantee for arbitrary SUMO networks. Permissive g does
not count as protected G.

ACTION and OBS prints are replay instrumentation only; no unbounded counters
are stored in verification states. The runner reconstructs started decisions
and sample time from replay events, counting the partial failing decision.
DFS witnesses can be long and are not claimed shortest.

## S3 timing and waiting semantics

| Property / component | State and threshold | Sampling |
|---|---|---|
| G2 displayed green | green_age increments on the same green, resets on yellow/change; assert <=MAX_GREEN | Each observed second, after the new sample counts |
| G2 controller age | Existing phase_duration; assert <=MAX_GREEN | After each completed decision |
| L1 NS wait | Reset to zero on NS green; otherwise increment; assert <=WAIT_LIMIT | Each observed second |
| L1 EW wait | Reset to zero on EW green; otherwise increment; assert <=WAIT_LIMIT | Each observed second |

G2 is the conjunction of displayed and controller-age checks, aligning the
shared harness rather than equating its two quantities. G2/static's current
counterexample violates controller age only at that point (65 vs displayed 29).
Each witness identifies the component; other properties are disabled per run.

WAIT_LIMIT is MAX_GREEN + 2*YELLOW_TIME, including warmup and yellow in waiting.
It is 66 for default/any/static and 60 for y0. This bounded waiting property is
checked as a safety invariant with a finite violation prefix; it is distinct
from L2's infinite liveness and does not rely on a fair agent.

The monitor ages saturate at one above the violated threshold (green 61,
wait 67 by default). Because an assertion checks that first over-limit state
immediately, saturation cannot hide a failure or wrap back into a safe value.
Controller AGE_CAP remains 76 at default timing, above both MIN_GREEN and
MAX_GREEN. It preserves v0 switch eligibility and the controller <=60 check.

TIMING replay events are emitted after monitor-counter updates and before their
assertions. Their columns are observed_green_age, ns_wait, ew_wait. OBS remains
the pre-update sample. Counters belonging to disabled checks stay at zero;
reference diagnostics may compute additional counters, so compare only the
selected check's active timing fields. Timestamps are reconstructed from sample
order; the first sample is at pre-step t=0. A failure at t=60 is the 61st counted
interval, not a claim that the simulation has already returned from step 61.

The tests cover both green directions at 60/61, controller age 60/61, green
reset across yellow/phase changes, waits 66/67 in both directions, wait reset,
yellow inclusion and the y0 60/61 waiting boundary. Real SUMO validation is still
pending. S2 source snapshots and run-local model copies retain old trail replay
when current monitor source changes.
