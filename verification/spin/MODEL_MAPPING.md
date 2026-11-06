# v0/v1 model mapping (S1-S5 stages)

The model implements v0/v1 control flow and shared checks:
S1, T1, T2, G1, C1, G2, L1 and L2. The runner emits a shared-format results CSV.
v1 is selected with VERSION=1; input rejections are separate from normal operation.

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

## S4 L2 construction and fairness preservation

`observed` is updated from signal inside the per-second observation tick.
L2 requires GF(observed==0) AND GF(observed==2); transient assignments between
ticks cannot count as service. The model is an ongoing control loop with
DELTA_TIME>0, finite warmup/yellow/delta loops and no externally blocking process.
Real training episode termination is deliberately outside this infinite model.

At each chosen action, record_request captures requested_action and eligibility
(phase_duration>=MIN_GREEN), and sets request_event. The event is cleared at
the completed decision. The request value is captured before controller action
processing, so it remains an input event, not an inferred output direction.
The pulse can span several Promela transitions but positive-time finite decisions
ensure GF pulse/value means infinitely many input events, not a stuck flag.

AGENT_FAIRNESS=0 checks unconditional L2. Mode 1 checks
(GF request0 AND GF request1) -> L2. Mode 2 checks
(GF eligible_request0 AND GF eligible_request1) -> L2. Each build has exactly
one agent_service LTL claim. pan -a searches its negation; pan -f is not used.
Eligible-request fairness is a stronger environment premise, not a controller fix.

The v0 age projection min(age,76) preserves phase_duration>=10, the only age
guard used by v0 switching and the new eligibility proposition. Signal/phase,
input domain and static cursor are retained. Absolute time and episode length
are absent, but every accepted loop must include ACTION events and OBS samples;
a time-free internal loop is rejected by the witness interpreter.

For each FAIL, split replay at START OF CYCLE, identify prefix/period ACTION
and REQUEST events, measure period sample count and missing green directions,
and verify the selected premise on the loop. Rotate to completed decision
boundaries and execute the extracted Python reference action period twice:
its projected control state must close, sampled services must match and time
must increase. This checks the quotient interpretation; it does not establish
full Python/SUMO liveness or eliminate the need for human review.

FAIRNESS_FEASIBILITY changes the sole claim to !FAIR_INPUT. Its acceptance
cycle is positive feasibility evidence, not a shared-property FAIL. Eight full
model premise checks and 11 synthetic LTL controls are stored separately from
the 12 main S4 rows. The fixed-policy example only restricts agent inputs to
produce a compact existential witness; controller transitions are unchanged.

## S5 exact v1 patch mapping

| Patch behavior | Promela | Observation / validation |
|---|---|---|
| first_switch_point(start,delta,min) | FIRST_POINT macro with integer ceil calculation and the start>=min branch | Constructor rejects warmup point and restart point separately |
| FIX-3 base checks | Reject delta<1, yellow<3, invalid min/max; delta0 avoids division | REJECT1; no simulation begins |
| FIX-2 | Validate chosen action before FIX-1 | REJECT4 + ABORT; no time/phase change |
| FIX-1 | Force action=1-current_phase if age+delta>max | ACTION/REQUEST retain original input; FORCED records resulting target |
| FIX-4a | show_green for phase0 before warmup | online=true; autonomous static cursor stays unused |
| FIX-4b | Increment controller age each warmup second | First green age includes all10 warmup ticks |

VERSION=0 preprocesses these branches away. v0 regression checks preserve
all previous verdicts and depths. The age cap is max+min+delta+1, above min,
max and max-delta thresholds for the tested nonnegative parameters, so the
look-ahead predicate and current controller comparisons remain preserved.
No counter saturation is used to hide the first bad G2 state.

The main v1 matrix models accepted default parameters with legal input streams,
including both no-static and static environments. Terminal expected rejections
are checked separately with finite TRACE data and are not called normal-operation
PASS or included in infinite L2 claims. Constructor rejection means no reference
environment object/reset exists; only its rejection reason is compared. Action
rejection additionally compares the exact unchanged time and control state.

42 dedicated cases compare both static settings: accepted forced-switch traces,
non-divisible timing, base parameter rejections, warmup/restart switch-point
rejections and action rejection before forcing. The wider 96-case v1 comparison
includes many early rejected sequences; its smaller observation count is not
comparable as execution coverage to 96 v0 trajectories.

The original patch accepts delta12/min0/max11/yellow3. FIRST_POINT(10)=10 and
FIRST_POINT(0)=0 pass validation, but a forced new green advances for12 seconds.
Both Promela and the unchanged v1 reference violate G2 at observed age12.
This is a discovered parameter-contract gap outside the referenced dt1..7 sweep.
It does not contradict the executed default-parameter PASSs. Do not strengthen
validation or patch source to make this row pass without owner authorization.

## S6 direct-source validation and environment refinement limits

The actual full-source traces match the projected Promela signal, controller
phase/age/time and online state in38 selected cases (7,205 records), including
v1 early errors. The static environment confirms observed transitions at43/46/
88/91. Abstract static-cursor bookkeeping is not compared as a source controller
field, especially after online takeover where it is disabled.

L0 is not a conservative source abstraction: it omits autonomous transitions and
permits indefinite initial displayed green.9 of21 original finite assertion
prefixes did not reproduce their selected target in SUMO; all9 are L0. Some
other L0 targets reproduce via a different actual trace/time. These differences
were not hidden by changing the formal verdict. Source-backed interpretation
uses L1 and actual independent replay; finite matching does not prove a general
bisimulation or exhaustive full-source correctness.

A SUMO-library audit directly compared getJunctionIndex/getTLLinkIndex on every
controlled connection and found identity for all14, with no protected G/G foes
in any phase. This discharges the fixed-network index assumption empirically
for this file/library, not arbitrary regenerated networks. Original source/patch/
network hashes are retained. Human review and C1's D4 interpretation remain
explicitly pending; code/models were not modified to conceal fidelity gaps.
