# Formal verification of traffic-signal control with SPIN

Status: SPIN technical draft for the joint CSEE E6863 report. Automated checks
and real-source validation are complete for the experiments below; human model
review and the teammate's numerical ESBMC evidence remain pending.

## Objective and scope

We verify the phase-transition and timing logic of the existing SUMO traffic
controller, rather than its Dueling Double DQN network or traffic efficiency.
The agent is abstracted as a nondeterministic input stream. Legal actions are
0/1; the separate any scenario expands the interface domain to -1/0/1/2.

v0 is original source commit `643ba4d`. v1 is exactly that source with the shared
FIX-1..4 patch. The worktree controller, network, shared contract and ESBMC
implementation were not modified. Promela models are in models/; detailed
source correspondence and abstraction arguments are in MODEL_MAPPING.md.

## Abstraction and temporal semantics

The model retains displayed signal, controller phase, controller age, optional
SUMO static-program state and property-specific monitors. Signal codes represent
NS green, NS yellow, EW green and EW yellow. The finite age projection saturates
above all comparisons used in each experiment; first over-limit monitor states
remain distinguishable and immediately trigger assertions. There is no wrapping
clock that could falsely restore a safe state.

Source analysis revealed that v0 warmup advances 10 seconds without increasing
controller phase_duration. Before first explicit takeover, SUMO also runs its
static signal program. Thus controller phase/age and displayed phase/age cannot
be treated as the same state. L0 omits the static program; L1 includes it.
L0 is a simplified environment, not automatically a conservative abstraction.

One observation tick corresponds to one SUMO step. Monitors sample before the
step, and C1/controller-age checks run after completed decisions. Zero-time
signal assignments do not count as a yellow interval. Observed propositions
for LTL are updated only at ticks. For infinite L2, the model continues the
control loop with positive decision time instead of terminating a training
episode; this is an explicit extension of the original application lifecycle.

## Properties and search method

| ID | Meaning | Mechanism |
|---|---|---|
| S1 | No simultaneous conflicting protected greens | State invariant and fixed-network protected-conflict audit |
| T1 | Green direction changes include an observed yellow interval | Symmetric per-second transition assertion |
| T2 | Yellow lasts at least3 observations and leads to opposite green | Duration/target assertions and eventual-completion LTL |
| G1 | Displayed green is not ended before min_green | Green-exit assertion |
| G2 | Green duration is bounded | Per-second displayed age plus shared harness's decision-boundary controller-age check |
| L1 | Directional waiting is bounded by max+2*yellow | Per-second NS/EW counters |
| L2 | Both directions are green infinitely often | GF NS AND GF EW, with three explicit input-premise variants |
| C1 | Phase is0/1 and agrees with display | Completed-decision assertion; provisional D4 interpretation |

Each run selects one property. SPIN generates a C verifier; safety checks use
-DSAFETY, while T2/L2 include acceptance-cycle search. Searches use full-state
storage with explicit depth/memory/time limits. PASS requires completed search;
resource truncation is UNKNOWN rather than proof. Witness lengths count started
input decisions, not Promela transitions. Replays preserve original flags and
source hashes. R1/P1 are outside this SPIN coverage.

The fixed network's14 TLS/request indices were compared with SUMO's
getJunctionIndex/getTLLinkIndex APIs and found identical; all four states have
zero protected G/G conflicts. This was checked explicitly because TLS and
junction indices can differ in general. See the [official network documentation](https://sumo.dlr.de/docs/Networks/SUMO_Road_Networks.html).
Protected G and permissive g have different meanings; permissive green is not
counted as protected priority in S1. See [SUMO signal semantics](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html).

## Model-level results

There are 72 recorded configurations:46 PASS and 26 FAIL, with no
UNKNOWN/TIMEOUT/ERROR in the final dataset. These counts mix versions, scenarios,
fairness variants and selected parameter probes; they are not independent
statistical samples. Detailed rows, actual timings/memory and raw evidence are
in results/results.csv and the frozen through-S5 snapshot.

For default timing and the static environment, the primary comparison is:

| Property | v0 | v1 |
|---|---|---|
| S1 | PASS | PASS |
| T1 | PASS | PASS |
| T2 | FAIL | PASS |
| G1 | FAIL | PASS |
| G2 | FAIL* | PASS |
| L1 | FAIL | PASS |
| L2, unconditional | FAIL | PASS |
| C1 | FAIL | PASS |

* The first G2/static witness violates the controller counter, not displayed
green duration at that same point. A different concrete post-takeover source
trace independently demonstrates overlong displayed green. The two components
must not be conflated.

All 20 default-parameter/legal-input v1 runs pass across static/no-static and
all implemented property/fairness variants. This is not universal parameter
correctness. y0 and illegal actions are explicitly rejected by v1, not reported
as normal-operation PASS.42 contract cases matched the reference extraction,
including 26 expected rejections. The v1 action guard runs before forced switching.

## Liveness and the fairness counterexample

L2 checks recurring sampled service. Three modes were checked separately:

| Input premise | default | y0 | any | static L1 |
|---|---|---|---|---|
| None | FAIL | FAIL | FAIL | FAIL |
| GF request0 AND GF request1 | PASS | PASS | FAIL | PASS |
| GF eligible_request0 AND GF eligible_request1 | PASS | PASS | PASS | PASS |

These are v0 results. Eligibility means controller age>=min at request time.
Fairness is an LTL implication over captured input events, not process weak
fairness or a property enforced by the agent. Separate acceptance-cycle checks
showed each conditional premise realizable. Eleven synthetic controls exercised
both genuine service and intentionally vacuous premises.

The any/request counterexample has a compact explanatory input policy: prepare
with [0,0,2,1,0], then repeat [0,2,1,0]. Each 26-second period retains NS, uses
invalid 2 to return to NS/reset age, requests EW too early, then returns to NS.
Both legal inputs recur but EW never receives green. Original and compact
witnesses are retained; neither is claimed shortest. Five original L2 lassos
have positive-time cycles and matching closed reference projections. A finite
real-SUMO prefix supports the behavior but is not an infinite-system proof.

v1 passes unconditional default L2 because the controller forces switches.
Recurring requests alone also permit arbitrarily long finite gaps, so L2 does
not imply L1's numeric wait bound.

## Residual v1 parameter-admission defect

Six G2 parameter pairs were checked: v0 fails all six; v1 passes five and fails
one. delta12/yellow3/min0/max 11 is admitted because the patch's computed first
switch points are10 and0. Yet a new green must advance for a12-second decision.
SPIN, the Python extraction and actual patched-source SUMO execution all detect
observed green 12>11 at pre-step t24. The controller boundary check fails at t25.

This case is outside the teammate's dt1..7 sweep and does not contradict the
executed default PASSs. No patch was silently strengthened. An additional
admissibility restriction or redesigned intra-decision switching would require
a separately reviewed repair/version and re-verification.

## Independent validation on real SUMO

The full source was executed on SUMO 1.28.0 with fixed action sequences. v1 used
an isolated source copy patched with the shared patch. Independent live monitors
do not import the extraction or stub.38 source/Promela cases matched 7,205
projected observations, including early-rejected inputs; a deliberate L0
negative control mismatched. Both traffic route files were exercised.

Pre-step static changes occurred at t43,46,88,91, confirming the model's initial
43 observations and later42/3/42/3 convention for this build. This is a sampling
statement, not a universal reinterpretation of the XML phase duration.

Only 12 of 21 original finite assertion prefixes reproduced their target in
actual SUMO. All 9 non-reproduced prefixes are L0 cases affected by autonomous
static behavior. Some reproduced targets also occur at different times along
the live trace. These results were preserved separately in results/sumo-replay.csv;
model FAILs were neither deleted nor converted to source PASSs.

The G1/static source replay also confirms that controller age 135 permits
cutting a displayed EW green after only 9 observations (t145), directly linking
the source guard, separate age variables, assertion and actual SUMO failure.

Concrete source examples establish the underlying defects: [0,0,1] with yellow0
causes T1 at t20; [0,0,1] followed by held EW causes G2 at t83 and L1 at t86.
The unchanged shared replay utility also reproduced T1/G2/C1 on selected source
traces. Main conclusions about original initialization therefore use L1 and
source evidence rather than an unqualified L0-to-source inference.

## Reproducibility, tool comparison and limitations

A fresh temporary code copy reran all 72 formal cases in 64.059 wall seconds,
matching verdicts, depth and witness-decision counts. It used the same installed
toolchain, not a second Mac. Compilation is included in that total; per-row
CSV time_s measures only verifier subprocess time. No cross-tool performance
ranking is inferred from single-run millisecond measurements.

| Evidence | Guarantee / limitation |
|---|---|
| SPIN exhaustive search | Selected finite-state model and explicit premises |
| Python extraction comparisons | Finite agreement with a reference abstraction |
| Real SUMO/source checks | Finite actual-source agreement and replay; not exhaustive source proof |
| ESBMC contribution | Repository describes bounded code checks and some induction; teammate raw results are not present in this checkout |

A numerical joint comparison requires the teammate's actual evidence aligned
by property/version/parameters/fidelity. No ESBMC verdict or metric was invented
or independently claimed here. Model fidelity tests do not prove all source
paths, vehicle collision freedom or DQN correctness. C1/D4 interpretation and
human review remain explicit outstanding items. Review obligations are listed
in REVIEW_CHECKLIST.md; the author must not report them completed merely because
automated checks passed.

## Evidence navigation

- README.md: commands, environment and current stage status.
- MODEL_MAPPING.md: source translation and property-specific abstractions.
- FINDINGS.md: interpreted model results and counterexamples.
- SUMO_VALIDATION.md: real-source matches and non-reproduced prefixes.
- report.md: chronological data, unsuccessful/corrected attempts and metrics.
- results/snapshots/: immutable stage CSVs and source snapshots.
- results/raw/: original commands, pan logs, trails, live traces and audits.

Tested live runtime is Python 3.13.7 with pinned SUMO 1.28.0 dependencies. A
Python 3.12 Homebrew download was cancelled after repeated transfer restarts;
no Python 3.12 test is claimed. The exact installed versions are preserved.
