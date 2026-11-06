# SPIN experimental record and report material

Last updated: 2026-11-06 (Asia/Shanghai). Current milestone: **S6 technical validation complete; human review pending**.
This is a chronological research record for the final CSEE E6863 report, not a
claim that all project stages are finished. Code/documentation remain in English.

## Record policy

- Append a stage/run entry after meaningful experiments, including PASS, FAIL,
  UNKNOWN, TIMEOUT, ERROR, implementation mistakes and corrected attempts.
- Preserve the original record. Append a correction or superseding run instead
  of rewriting an unsuccessful attempt as a successful one.
- Distinguish controller defects, model defects, tool/environment failures,
  search incompleteness and supplementary tests.
- Each entry records question, version/fidelity/parameters, commands, assumptions,
  actual outcome/metrics, evidence, interpretation, limitations and next step.
- Raw timestamped runs are primary evidence. results.csv is a replaceable current
  view; retain a stage CSV snapshot so later stages cannot erase past numbers.
- Never infer missing measurements. Use "not recorded" and identify when an
  entry was reconstructed from earlier context rather than retained raw output.
- Tests/simulation and model-level proofs have different guarantees. Record
  real SUMO and human review status separately.
- Future assistants must update this record at each stage, as well as the brief
  current status in README and handoff decisions in node-spin.md.

Document roles: [README](README.md) is the reproduction entry point;
[node-spin](node-spin.md) holds AI instructions/decisions;
[FINDINGS](FINDINGS.md) summarizes interpreted results;
this file preserves experimental history for writing the final report.

## Milestone status at the S2 checkpoint (historical)

| Stage | Status at this checkpoint | Remaining qualification |
|---|---|---|
| S0 | Toolchain installed and smoke checks executed | Historical smoke logs were not archived |
| S1 | Initial v0 model and finite reference comparison implemented | Real SUMO fidelity not yet established |
| S2 | Five properties, four scenarios; 20 current results | C1/D4 provisional; real SUMO/human review pending |
| S3 | Not started | G2 and L1 timing/waiting checks |
| S4 | Not started | L2 and explicit agent fairness |
| S5 | Not started | Exact v1 FIX-1..4 and comparison |
| S6 | Not complete | Final integration, report, supplementary validation |

### Fixed experimental setup

v0 is original source commit 643ba4d. Repository HEAD at this checkpoint remains
2d2cd08 on feature/spin-verification; the SPIN files are uncommitted additions.
Defaults: delta 5 s, yellow 3 s, min green 10 s, max green 60 s, warmup 10 s.
y0 changes yellow to zero; any expands actions to -1/0/1/2; L1 enables the
reference static program. default/y0/any use fidelity L0. No trained policy is
required because legal actions are nondeterministic.

Tooling: SPIN 6.5.2, Apple Clang 21.0.0, Python 3.13.7, macOS arm64.
For S2 the verifier uses depth limit 100000, memory limit 512 MB, hash table
-w18, full-state storage and no process fairness option. Subprocess timeout is
120 s each. T2 includes acceptance-cycle search; other properties use safety mode.

## S0: installation and tool smoke (2026-11-06)

Question: can this Mac generate, compile and run a SPIN verifier and replay errors?

Commands: `brew install spin`, `spin -V`, `brew list --versions spin`,
`cc --version`; for smoke models, `spin -a model.pml`,
`cc -O2 -o pan pan.c`, `./pan -m10000`, or `./pan -a -m10000` for LTL,
and `spin -t -p -g model.pml` for replay.

| Attempt | Actual outcome | Interpretation / follow-up |
|---|---|---|
| Homebrew installation | Overall command exit 1; API download/update warning | Package nevertheless installed; independently confirmed spin 6.5.2 and functional execution |
| assert(1) smoke | errors 0, depth 2 | Completed safety smoke, not a project property |
| assert(0) smoke | errors 1, depth 0; trail replayed | Intended assertion failure detected |
| Unconditional skip loop for LTL smoke | pan rejected an unconditional self-loop | Smoke-model construction issue; replaced with state-changing Boolean toggle |
| Boolean toggle with []<> false | Acceptance cycle, errors 1, depth 5; cycle replayed | Intended liveness failure detected |
| Unquoted spin -? in zsh | Shell reported no matches found | Quote help arguments as spin '-?' |

Evidence provenance: reconstructed from node-spin.md and previous tool output;
original temporary smoke models/logs were not retained. Elapsed time, memory and
full process output are therefore not available for these historical attempts.
These entries must not be included in the shared property result counts.

Methodological lesson: pan can return exit code 0 for a property violation.
Classify from verifier diagnostics, error count and search completion, not exit
status alone. Stopping on a witnessed violation differs from resource truncation.

## S1: model translation and conformance (2026-11-06)

Question: does the Promela v0 control flow agree with the Python reference at
pre-second and post-decision observation points?

```sh
python3 verification/spin/scripts/check_traces.py \
  --output verification/spin/results/raw/s1-trace-comparison.json
```

Actual outcome: **96 finite cases matched, 18,898 observation records**, including
72 targeted configurations and 24 random cases with seed 6863. Coverage includes
static program on/off, delta 1/5/7, yellow 0/3, prolonged holds, switching requests,
static takeover and invalid actions. The S2 instrumentation was followed by a
rerun with the same matching counts; the retained JSON reflects that current model.
Evidence: [trace case data and hashes](results/raw/s1-trace-comparison.json),
[source mapping](MODEL_MAPPING.md). Historical pre-S2 JSON was overwritten; its
reported counts are preserved in context but its exact prior hashes are not.
The finite trace check did not record elapsed-time or memory metrics.

Initial non-TRACE build smoke, before property monitors, used
`spin -DSTATIC_PROGRAM=<0|1> -DANY_ACTION -a controller.pml`,
`cc -O2 -o pan pan.c`, `./pan -m100000 -w18`:

| Static program | Errors | Depth reached | Stored states |
|---|---|---|---|
| Disabled | 0 | 2068 | 5026 |
| Enabled | 0 | 2669 | 90183 |

These historical smoke counts are from node-spin.md; original raw logs were not
archived. They checked model-domain assertions/invalid end states, not shared
properties. No S1-property PASS is inferred from the S1 work-stage smoke.

Translation issues retained for the final report:
- Controller phase_duration excludes v0 warmup; displayed green age differs.
- Before first takeover, SUMO's static program can diverge from controller phase.
- The stub's first 43 samples are an unconfirmed SUMO boundary convention.
- Invalid action fallback changes the displayed state and stored phase differently.
- Root README's max-green enforcement claim disagrees with v0 source.
- The older baseline script counts decisions while labeling its interval seconds.
- The model omits episode termination for an ongoing control abstraction and
  uses a documented age saturation; this does not verify full DQN or traffic dynamics.

## S2: safety and transition verification (2026-11-06)

Question: which of S1/T1/T2/G1/C1 hold for v0 under each shared scenario?

```sh
python3 verification/spin/scripts/run_spin.py --all
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/test_verification.py
```

### Two executed verification sweeps

Sweep A was the initial 20-case matrix. Sweep B reran the same matrix after
hardening resource-limit classification (MEMLIM handling). Both sweeps returned
14 PASS and 6 FAIL, with no UNKNOWN/TIMEOUT/ERROR. They are repeated measurements
of the same 20 cases, not 40 distinct property configurations or a statistical
benchmark. Each run's raw metadata retains its exact model/runner digests.

The table below preserves both sweeps. time_s is measured verifier wall time,
excluding compile/generation/replay. memory_mb is pan's reported total actual
memory. Depth is Promela search depth; CE is started decision events, not seconds
or transitions. Search state counts are read directly from verify.txt.

| Sweep | Case | Result | Depth | CE decisions | time_s | memory_mb | Stored states | Evidence |
|---|---|---|---|---|---|---|---|---|
| A | C1-v0-L1 | FAIL | 277 | 7 | 0.010020 | 7.536 | 278 | [metadata](results/raw/C1-v0-L1-20261106T084218699021Z/metadata.json) |
| A | C1-v0-any | FAIL | 1210 | 33 | 0.012363 | 7.536 | 1452 | [metadata](results/raw/C1-v0-any-20261106T084217846282Z/metadata.json) |
| A | C1-v0-default | PASS | 1181 | - | 0.007919 | 7.536 | 1723 | [metadata](results/raw/C1-v0-default-20261106T084216318025Z/metadata.json) |
| A | C1-v0-y0 | PASS | 1165 | - | 0.007038 | 7.536 | 1453 | [metadata](results/raw/C1-v0-y0-20261106T084217081360Z/metadata.json) |
| A | G1-v0-L1 | FAIL | 1759 | 28 | 0.014929 | 8.122 | 10738 | [metadata](results/raw/G1-v0-L1-20261106T084215499791Z/metadata.json) |
| A | G1-v0-any | PASS | 1813 | - | 0.004673 | 7.829 | 5560 | [metadata](results/raw/G1-v0-any-20261106T084214698365Z/metadata.json) |
| A | G1-v0-default | PASS | 1117 | - | 0.008028 | 7.634 | 1761 | [metadata](results/raw/G1-v0-default-20261106T084213261170Z/metadata.json) |
| A | G1-v0-y0 | PASS | 1101 | - | 0.007322 | 7.536 | 1497 | [metadata](results/raw/G1-v0-y0-20261106T084213960978Z/metadata.json) |
| A | S1-v0-L1 | PASS | 1756 | - | 0.014994 | 9.099 | 29974 | [metadata](results/raw/S1-v0-L1-20261106T084206070100Z/metadata.json) |
| A | S1-v0-any | PASS | 2197 | - | 0.013803 | 7.731 | 5365 | [metadata](results/raw/S1-v0-any-20261106T084205269471Z/metadata.json) |
| A | S1-v0-default | PASS | 1117 | - | 0.007367 | 7.536 | 1653 | [metadata](results/raw/S1-v0-default-20261106T084203624497Z/metadata.json) |
| A | S1-v0-y0 | PASS | 1101 | - | 0.009655 | 7.536 | 1383 | [metadata](results/raw/S1-v0-y0-20261106T084204531261Z/metadata.json) |
| A | T1-v0-L1 | PASS | 1759 | - | 0.018890 | 9.099 | 30007 | [metadata](results/raw/T1-v0-L1-20261106T084209219053Z/metadata.json) |
| A | T1-v0-any | PASS | 2197 | - | 0.008899 | 7.731 | 5377 | [metadata](results/raw/T1-v0-any-20261106T084208460496Z/metadata.json) |
| A | T1-v0-default | PASS | 1117 | - | 0.007413 | 7.536 | 1656 | [metadata](results/raw/T1-v0-default-20261106T084206843625Z/metadata.json) |
| A | T1-v0-y0 | FAIL | 571 | 17 | 0.012548 | 7.536 | 580 | [metadata](results/raw/T1-v0-y0-20261106T084207637945Z/metadata.json) |
| A | T2-v0-L1 | FAIL | 1161 | 17 | 0.012934 | 7.536 | 635 | [metadata](results/raw/T2-v0-L1-20261106T084212470946Z/metadata.json) |
| A | T2-v0-any | FAIL | 2397 | 35 | 0.019223 | 7.634 | 1591 | [metadata](results/raw/T2-v0-any-20261106T084211559933Z/metadata.json) |
| A | T2-v0-default | PASS | 2235 | - | 0.008366 | 7.634 | 1904 | [metadata](results/raw/T2-v0-default-20261106T084209995075Z/metadata.json) |
| A | T2-v0-y0 | PASS | 2203 | - | 0.008273 | 7.536 | 1386 | [metadata](results/raw/T2-v0-y0-20261106T084210789133Z/metadata.json) |
| B | C1-v0-L1 | FAIL | 277 | 7 | 0.012433 | 7.536 | 278 | [metadata](results/raw/C1-v0-L1-20261106T084458111435Z/metadata.json) |
| B | C1-v0-any | FAIL | 1210 | 33 | 0.008818 | 7.536 | 1452 | [metadata](results/raw/C1-v0-any-20261106T084457547770Z/metadata.json) |
| B | C1-v0-default | PASS | 1181 | - | 0.004064 | 7.536 | 1723 | [metadata](results/raw/C1-v0-default-20261106T084456533352Z/metadata.json) |
| B | C1-v0-y0 | PASS | 1165 | - | 0.003393 | 7.536 | 1453 | [metadata](results/raw/C1-v0-y0-20261106T084457030998Z/metadata.json) |
| B | G1-v0-L1 | FAIL | 1759 | 28 | 0.014948 | 8.122 | 10738 | [metadata](results/raw/G1-v0-L1-20261106T084455513246Z/metadata.json) |
| B | G1-v0-any | PASS | 1813 | - | 0.003100 | 7.829 | 5560 | [metadata](results/raw/G1-v0-any-20261106T084455009857Z/metadata.json) |
| B | G1-v0-default | PASS | 1117 | - | 0.004394 | 7.634 | 1761 | [metadata](results/raw/G1-v0-default-20261106T084454025105Z/metadata.json) |
| B | G1-v0-y0 | PASS | 1101 | - | 0.004189 | 7.536 | 1497 | [metadata](results/raw/G1-v0-y0-20261106T084454511483Z/metadata.json) |
| B | S1-v0-L1 | PASS | 1756 | - | 0.008746 | 9.099 | 29974 | [metadata](results/raw/S1-v0-L1-20261106T084449173335Z/metadata.json) |
| B | S1-v0-any | PASS | 2197 | - | 0.003417 | 7.731 | 5365 | [metadata](results/raw/S1-v0-any-20261106T084448646944Z/metadata.json) |
| B | S1-v0-default | PASS | 1117 | - | 0.006811 | 7.536 | 1653 | [metadata](results/raw/S1-v0-default-20261106T084447515392Z/metadata.json) |
| B | S1-v0-y0 | PASS | 1101 | - | 0.006791 | 7.536 | 1383 | [metadata](results/raw/S1-v0-y0-20261106T084448068154Z/metadata.json) |
| B | T1-v0-L1 | PASS | 1759 | - | 0.011552 | 9.099 | 30007 | [metadata](results/raw/T1-v0-L1-20261106T084451247981Z/metadata.json) |
| B | T1-v0-any | PASS | 2197 | - | 0.003095 | 7.731 | 5377 | [metadata](results/raw/T1-v0-any-20261106T084450767225Z/metadata.json) |
| B | T1-v0-default | PASS | 1117 | - | 0.007826 | 7.536 | 1656 | [metadata](results/raw/T1-v0-default-20261106T084449679009Z/metadata.json) |
| B | T1-v0-y0 | FAIL | 571 | 17 | 0.006468 | 7.536 | 580 | [metadata](results/raw/T1-v0-y0-20261106T084450210734Z/metadata.json) |
| B | T2-v0-L1 | FAIL | 1161 | 17 | 0.006141 | 7.536 | 635 | [metadata](results/raw/T2-v0-L1-20261106T084453446889Z/metadata.json) |
| B | T2-v0-any | FAIL | 2397 | 35 | 0.010565 | 7.634 | 1591 | [metadata](results/raw/T2-v0-any-20261106T084452869814Z/metadata.json) |
| B | T2-v0-default | PASS | 2235 | - | 0.004690 | 7.634 | 1904 | [metadata](results/raw/T2-v0-default-20261106T084451788181Z/metadata.json) |
| B | T2-v0-y0 | PASS | 2203 | - | 0.004148 | 7.536 | 1386 | [metadata](results/raw/T2-v0-y0-20261106T084452331030Z/metadata.json) |

The frozen current-stage CSV is [S2 snapshot](results/snapshots/s2-v0-results.csv).
[Current results.csv](results/results.csv) may change as later stages run.
All current rows link to sweep B. Detailed generation, compile, verifier and
replay commands/timings are in each run's metadata; raw pan outputs are alongside.
Tool versions and the fixed network digest are recorded per run.

### Interpreted matrix (both sweeps)

| Property | default (L0) | y0 (L0) | any (L0) | static L1 |
|---|---|---|---|---|
| S1 | PASS | PASS | PASS | PASS |
| T1 | PASS | FAIL | PASS | PASS |
| T2 | PASS | PASS* | FAIL | FAIL |
| G1 | PASS | PASS | PASS | FAIL |
| C1 | PASS | PASS | FAIL | FAIL |

* T2/y0 is conditionally vacuous: no yellow sample exists to trigger its yellow
obligation. T1/y0 independently fails for the missing interval. Report both;
T2/y0 PASS is not proof that zero-yellow switching is safe.

### Failure witnesses, not unsuccessful project outcomes

Each FAIL is a genuine model assertion witness cross-checked by independent
execution of the extracted Python v0 core/stub. No counterexample has yet been
replayed in real SUMO. All six selected witnesses are finite; their reported
lengths are first DFS witnesses, not guaranteed minimum lengths.

| Case | CE decisions | Reference time_s | Reference explanation | Witness |
|---|---|---|---|---|
| C1-v0-L1 | 7 | 45 | C1: displayed state mismatch | [actions and state](results/raw/C1-v0-L1-20261106T084458111435Z/witness.json) |
| C1-v0-any | 33 | 181 | C1: phase out of range | [actions and state](results/raw/C1-v0-any-20261106T084457547770Z/witness.json) |
| G1-v0-L1 | 28 | 145 | G1: green cut before min_green | [actions and state](results/raw/G1-v0-L1-20261106T084455513246Z/witness.json) |
| T1-v0-y0 | 17 | 90 | T1: NS green -> EW green without yellow | [actions and state](results/raw/T1-v0-y0-20261106T084450210734Z/witness.json) |
| T2-v0-L1 | 17 | 93 | T2: yellow not followed by the other direction | [actions and state](results/raw/T2-v0-L1-20261106T084453446889Z/witness.json) |
| T2-v0-any | 35 | 189 | T2: yellow not followed by the other direction | [actions and state](results/raw/T2-v0-any-20261106T084452869814Z/witness.json) |

Cause analysis: T1/y0 changes direction directly. T2/any can return to the same
green because invalid actions desynchronize the controller; T2/L1 can yellow
an already displayed EW phase and return to EW during takeover. G1/L1 cuts a
displayed green after only 9 seconds despite a large controller age. C1/any
stores an illegal phase while falling back to NS; C1/L1 detects a static-program
yellow at a completed decision while controller phase remains NS.

For G1/L1, Promela controller age saturates at 76 while Python reports 135;
both satisfy the switch guard. The independent observed green age is 9. This
illustrates why controller age alone cannot establish displayed-signal timing.

### Test and runner-development record

- Initial monitor/classifier test suite: 9 test methods passed. It includes
  deliberate short-yellow, wrong-direction, direct-switch, phase and signal faults.
- Final test suite: 10 methods passed in 8.021 s (test-run elapsed time, not
  verifier benchmark time). The additional actual depth-exhaustion case returns
  UNKNOWN; the reverse-direction transition fixture was also strengthened.
- Final tests contain 15 synthetic monitor searches. The infinite-yellow fixture
  deliberately triggers an acceptance cycle, verifying the T2 completion check
  is active. A property failure in such a fixture is the expected test outcome.
- The runner was hardened to recognize the MEMLIM resource message as UNKNOWN.
  This was preventative parser hardening, not a measured memory-exhaustion event
  in the project matrix. Classifier tests exercise the diagnostic string.
- The standalone replay_trail.py command was checked against retained T1/y0
  evidence; it reproduced the assertion after verifying model hashes.
- Ten-test aggregate output is retained in conversation/context rather than a
  raw test log. Test behavior is reproducible from scripts/test_verification.py.
- No project UNKNOWN/TIMEOUT/ERROR was observed in either sweep; do not fabricate
  such project results from synthetic tests or historical smoke failures.

### Assumptions, risks and scope limits

1. S1 uses a fixed four-state codebook plus foes-matrix preflight, with the explicit
   network-specific assumption that signal link i maps to junction request i.
   Permissive g is not treated as protected G.
2. C1 is checked after complete decisions, provisionally following the ESBMC
   harness. The referenced D4 decision is unavailable.
3. Static timing follows the shared stub, including initial 43 samples. No real
   SUMO validation is claimed. The reference itself is an abstraction.
4. PASS is exhaustive for the selected finite-state configuration, not the full
   Python/SUMO/DQN system or all timing parameters.
5. No process fairness is used in S2. L2 will require separate explicit agent
   fairness premises and acceptance-cycle reasoning.
6. Human model review required by the proposal is pending. AI review, reference
   tests and formal checks do not substitute for a human sign-off.

## Final report outline and pending evidence

Use the source mapping for methodology, the stage snapshots/raw logs for
quantitative results, and counterexample data for source-level explanations.
The eventual joint comparison must align property, version, configuration,
observation point and environment fidelity; explain exhaustive finite-state
SPIN checking versus bounded ESBMC coverage without claiming equal guarantees.

| Needed next | Evidence to append here |
|---|---|
| S3 G2/L1 | Actual timing/wait counters, boundary cases, all verdicts and trails |
| S4 L2 | Fairness premise, completed cycle searches, prefix/cycle lengths |
| S5 v1 | Exact patch mapping, rejected-input handling, comparison and limits |
| SUMO checks | Dependency versions, commands, replay matches/mismatches |
| Human review | What was reviewed, by whom/when if supplied, unresolved issues |
| Final report | Aligned tool comparison, abstractions, fallback and limitations |

## Template for the next appended entry

```text
Stage / attempt / date:
Question and expected diagnostic behavior:
Version, parameters, scenario, fidelity and fairness:
Model/runner digests and source revision:
Exact command(s), tool versions and limits:
Actual verdict, depth, CE decisions, timing/memory and units:
Raw evidence and frozen stage snapshot:
What worked / what failed / corrected attempts:
Interpretation and limitations:
Next step:
```

## Report evidence checklist (user confirmed 2026-11-06)

The final narrative should connect source, abstraction, formal properties,
model-checking evidence, counterexamples and repairs. The following priorities
are our project presentation plan, not a known instructor grading rubric.
Record supporting material as each stage proceeds rather than reconstructing
technical choices at report-writing time.

| Topic | Evidence to retain during implementation |
|---|---|
| Source-to-Promela abstraction | Source revision and method/line references, model locations, retained/omitted variables and behaviors, rationale and property-specific preservation argument |
| Discrete-time semantics | Tick/update ordering, warmup accounting, decision versus second units, yellow handling, threshold boundary traces |
| Controller/environment distinction | Controller phase versus displayed signal, controller age versus observed age, L0/L1 assumptions and takeover behavior |
| Finite-state construction | Counter ranges/saturation thresholds, comparisons they preserve, introduced limitations and changes needed for each property/version |
| Property specification | Natural-language statement, exact assertion/LTL, observation point, safety/liveness classification, trigger reachability and vacuity checks |
| Search configuration | Selected claim, exact flags, fairness premise, depth/memory/time limits, search completeness, state/transition counts, measured time/memory and units |
| Failed properties | Original trail, action sequence, prefix/cycle when applicable, sampled states/timestamps, source cause, reference/SUMO reproduction status |
| Model/tool failures | Original error or mismatch, diagnosis, correction and rerun; distinguish these from controller defects |
| v0/v1 repair comparison | Exact FIX mapping, aligned parameters/fidelity/observation points, before/after evidence, invalid-input rejection and residual issues |
| Validation and limitations | Finite reference tests versus real SUMO, human review status, neural-network/traffic abstraction, episode extension and conditional guarantees |
| Joint tool comparison | Aligned SPIN/ESBMC cases, differing bounds/assumptions, liveness support, guarantee strength and unverified teammate results |

Keep at least one reviewable end-to-end case study linking the original source
behavior, Promela representation, property, raw witness and repair outcome.
G1/static-program is a candidate: S2 has a reference-reproduced 9-second green
termination, but its real SUMO replay and v1 outcome are still pending. Do not
write those pending results as established facts.

A genuine FAIL can be a successful verification finding. Keep its evidence and
explain its meaning; do not adjust models/properties merely to obtain PASS.
No new experiment or metric was produced by adding this checklist.

## S3: maximum-green and bounded-waiting stage (2026-11-06)

Status: completed for v0; next is S4 (L2/fairness). Question: can the controller
exceed the green or directional-wait limits, and do the abstractions preserve
the first violating boundary?

### Specification and modeling choices

- G2 checks both per-second displayed green age and controller phase_duration
  after a completed decision, matching the shared ESBMC h_G2 harness. These
  quantities are distinct; identify the failing component instead of claiming
  one measures the other. This choice was explained before implementation.
- L1 checks NS/EW wait <=MAX_GREEN+2*YELLOW_TIME. Warmup and yellow count toward
  waiting; a direction's green resets its wait. L1 is bounded waiting, checked
  as safety, not an infinite fairness/liveness argument.
- Observed green saturates at 61 and default wait counters at 67, preserving
  first bad threshold states. y0's wait limit is 60 and first bad state is 61.
  These are monitor counters; no original controller transition was changed.
- Source mapping, sampling order and preservation arguments are in
  MODEL_MAPPING.md. G2's controller-age saturation remains above max/min guards.
- TIMING events capture post-update monitor values before assertions. Reference
  times are pre-step timestamps or completed boundaries; the interval sampled
  at t=60 is the 61st since t=0. Interpret timestamps with that convention.

### Commands and completion evidence

```sh
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/test_verification.py
python3 verification/spin/scripts/check_traces.py \
  --output verification/spin/results/raw/s1-trace-comparison.json
python3 verification/spin/scripts/run_spin.py --stage S3
python3 verification/spin/scripts/run_spin.py --stage S2
```

Actual outcomes: 14 test methods passed in 25.488 seconds; 96 finite comparison
cases / 18,898 records matched; all eight S3 searches FAIL with reproduced
finite witnesses; S2 regression remains 14 PASS / 6 FAIL. No new project
UNKNOWN/TIMEOUT/ERROR. The combined current matrix is 28 cases, 14 PASS / 14 FAIL.
Test duration is not the verifier wall-time metric used in results.csv.

Test coverage: 32 synthetic monitor searches, including 60/61 greens in both
directions, controller age 60/61, resets across yellow/direction changes,
66/67 waits in both directions, wait reset, yellow inclusion, y0 wait 60/61,
prior S2 faults, infinite yellow and actual depth truncation. Expected fixture
FAILs remain successful tests. No failing development test was observed in
this S3 implementation; do not invent a failed attempt.

Validation logs:
- [tests.txt](results/raw/s3-validation-20261106T090359Z/tests.txt)
- [traces.txt](results/raw/s3-validation-20261106T090359Z/traces.txt)
- [s3-matrix.txt](results/raw/s3-validation-20261106T090359Z/s3-matrix.txt)
- [s2-regression.txt](results/raw/s3-validation-20261106T090359Z/s2-regression.txt)
- [archived-s2-replay.txt](results/raw/s3-validation-20261106T090359Z/archived-s2-replay.txt)
- [s3-g2-replay.txt](results/raw/s3-validation-20261106T090359Z/s3-g2-replay.txt)

The replay CLI successfully replayed a stored S2 T1/y0 assertion using matching
historical source, and a new G2 assertion using run-local source. S2 model copies
were frozen before edits; new runs now retain their own controller/properties
source alongside hashes. Old results are not overwritten by model changes.

### S3 measured results

| Case | Verdict | Depth | CE decisions | Verifier time_s | memory_mb | Stored states | Transitions | Reference violation time_s | Component | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| G2-v0-default | FAIL | 380 | 11 | 0.008876 | 7.536 | 381 | 381 | 60 | observed_green | [metadata](results/raw/G2-v0-default-20261106T090427766230Z/metadata.json) |
| G2-v0-y0 | FAIL | 380 | 11 | 0.010772 | 7.536 | 381 | 381 | 60 | observed_green | [metadata](results/raw/G2-v0-y0-20261106T090428544566Z/metadata.json) |
| G2-v0-any | FAIL | 380 | 11 | 0.010230 | 7.536 | 381 | 381 | 60 | observed_green | [metadata](results/raw/G2-v0-any-20261106T090429354453Z/metadata.json) |
| G2-v0-L1 | FAIL | 474 | 13 | 0.010844 | 7.536 | 475 | 475 | 75 | controller_age | [metadata](results/raw/G2-v0-L1-20261106T090430125413Z/metadata.json) |
| L1-v0-default | FAIL | 408 | 12 | 0.009843 | 7.536 | 409 | 409 | 66 | directional_wait | [metadata](results/raw/L1-v0-default-20261106T090430915881Z/metadata.json) |
| L1-v0-y0 | FAIL | 370 | 11 | 0.012018 | 7.536 | 371 | 371 | 60 | directional_wait | [metadata](results/raw/L1-v0-y0-20261106T090431686597Z/metadata.json) |
| L1-v0-any | FAIL | 408 | 12 | 0.007617 | 7.536 | 409 | 409 | 66 | directional_wait | [metadata](results/raw/L1-v0-any-20261106T090432492617Z/metadata.json) |
| L1-v0-L1 | FAIL | 1630 | 48 | 0.014452 | 7.634 | 1639 | 1640 | 254 | directional_wait | [metadata](results/raw/L1-v0-L1-20261106T090433253634Z/metadata.json) |

time_s is actual verifier subprocess wall time (generation/compilation excluded);
memory_mb is pan's total actual memory. These are single runs, not statistically
stable performance estimates. The raw metadata records tool versions, commands,
limits, network hash, model/runner hashes and read-only Python reference hashes.
All current 28 rows were executed with the S3 models and measurement runner
retained in [s3-runner.py](results/snapshots/s3-runner.py). The frozen
[S3 CSV](results/snapshots/s3-v0-results.csv) has eight cases; the
[through-S3 snapshot](results/snapshots/through-s3-v0-results.csv) has all 28.
The original S2 snapshots and two historical S2 sweeps remain preserved.

### Failure interpretation and final-report material

1. G2/default, y0 and any share a valid repeated-NS action witness: the first
   offending green count is 61 at pre-step t=60, during started decision 11.
   Controller age is only 50 because v0 warmup was not counted. Do not attribute
   these any-case failures specifically to an invalid action: the witness uses
   ordinary legal actions.
2. G2/static fails after decision 13 at t=75: controller age 65 exceeds 60, but
   displayed EW green age is 29. This is controller timing drift under the
   static program, not proof of an overlong displayed interval at that instant.
3. L1/default and any violate the 66-second bound with EW wait 67 at pre-step
   t=66 during decision 12. y0's configured bound is 60; it fails at wait 61,
   pre-step t=60, decision 11. Warmup is part of directional waiting.
4. L1/static's DFS witness reaches EW wait 67 at pre-step t=254, decision 48,
   after takeover. The static program alone alternates, but online control can
   retain one green indefinitely because v0 never forces a switch. This is
   a finite safety witness, not yet an L2 infinite-starvation proof.
5. All eight original trails were replayed and their action sequences reproduced
   the selected check in the extracted Python reference. No real SUMO replay
   has been performed; the same abstraction/fidelity caveats remain.

The result is evidence of controller defects (including F1/F2 and accounting
issues), not an implementation failure of this stage. Other properties are
isolated per run, so a witness may have violated another property earlier.
Do not conflate first DFS witnesses with shortest counterexamples or compare
lengths across different observation semantics without explanation.

### S2 regression and next stage

Twenty S2 cases were rerun after shared monitor/runner edits: all verdicts and
search depths were unchanged. This is a regression measurement, not 20 new
property configurations. Their detailed measured timings and raw evidence are
preserved by the combined stage snapshot and the current CSV. The historical
S2 checkpoint must remain labeled with its historical model hashes.

README was updated at stage start, after validation and at completion, with
stage meanings and gates for teammates. Stop at S3. S4 must introduce explicit
agent-fairness premises and L2 cycle reasoning; no L2/v1 claim is made here.
Human review and real SUMO fidelity remain pending.

### S3 closeout correction: CSV line endings

The final git diff --check reported Python CSV's default CRLF as trailing
whitespace in modified rows. This is a serialization/repository-check issue,
not a property or model failure. The original diagnostic is retained in the
S3 validation directory as pre-normalization-diff-check.txt. Changed the runner
writer to LF and normalized the current/new S3 CSV files; verified that every
parsed header/field/row remained identical. Original S2 history was not changed.
No verifier rerun was needed for this formatting-only correction. The measured
runner source was archived before the change, preserving its raw-metadata hash.

Repository HEAD at this stage is 7ccc6ea, the user's S2 commit. All S3 changes
remain uncommitted; no assistant Git write operation was performed.

## S4: infinite service, fairness and acceptance cycles (2026-11-06)

Stage completed for v0; next is S5. Repository HEAD at stage start was 717786c
(the user's S3 commit). No Git write operation was performed by the assistant.

### Research question and exact specification

Does each direction obtain green infinitely often in the ongoing control-loop
abstraction? Check L2 = GF sampled_NS AND GF sampled_EW under three alternatives:
none (unconditional); request fairness (GF input0 AND GF input1); eligible-request
fairness (GF eligible_input0 AND GF eligible_input1). Eligibility is controller
age>=min_green at the captured decision input. The latter is a stronger premise,
not a relabeling of the first. Fairness concerns the input stream, not the
scheduler; no pan -f is used. Each model build contains one LTL claim.

Samples update only at simulated seconds. Decisions have delta>0 and finite
internal loops; there is no arbitrary episode cutoff in this infinite model.
The min(age,76) quotient preserves both switching and eligibility comparisons.
Human review and source/SUMO fidelity remain pending; see MODEL_MAPPING.md.

### Attempts, controls and regression

An initial 12-case sweep gave 7 PASS / 5 FAIL. Before the final sweep, reference
cycle validation was strengthened to compare service sets and selected input
fairness, and the new event-clear hook was scoped so non-L2 control graphs
remain unchanged. No initial cycle mismatch was observed. The final 12-case
sweep gave the same verdicts and depths. Initial raw runs remain preserved.
Both sweeps are repeated measurements of 12 configurations, not 24 new cases.

Eleven synthetic LTL controls matched their intended results: starvation of
both directions; alternating service; finite EW followed by permanent NS;
request-fair starvation; eligible-fair starvation; successful fair service;
intentional premise vacuity; and no phantom fairness from non-event values.
Eight full-model checks of !FAIR_INPUT found acceptance cycles demonstrating
premise feasibility for both fairness modes in all four scenarios. These
auxiliary verifier FAILs are expected positive evidence, not controller-defect
rows. Their source/logs/cycles are retained separately. A fixed-policy compact
counterexample adds one explanatory execution without changing the controller.

Existing safety/timing tests: 14 methods passed in 24.814 s; 96 finite trace
cases / 18,898 records still match the extraction/stub. All 28 S2/S3 regression
verdicts and search depths remained unchanged. No project UNKNOWN/TIMEOUT/ERROR
was observed. Final current matrix: 40 cases, 21 PASS / 19 FAIL. Fourteen FAILs
are finite assertions and five are L2 acceptance-cycle witnesses.

Commands (repository root):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/run_spin.py --stage S4
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/run_spin.py --stage S2
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/run_spin.py --stage S3
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/test_verification.py
python3 verification/spin/scripts/check_traces.py \
  --output verification/spin/results/raw/s1-trace-comparison.json
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/check_liveness.py \
  --output verification/spin/results/raw/s4-controls-rerun
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/explain_l2_counterexample.py \
  --output verification/spin/results/raw/s4-short-witness-rerun
```

The last two commands require new output paths to preserve prior evidence.
Original auxiliary [summary](results/raw/s4-liveness-controls/summary.json) and
[compact witness analysis](results/raw/s4-short-request-fair-witness/analysis.json)
are retained. Main validation logs:
- [commands.json](results/raw/s4-validation-20261106T092809Z/commands.json)
- [s2-regression.txt](results/raw/s4-validation-20261106T092809Z/s2-regression.txt)
- [s3-regression.txt](results/raw/s4-validation-20261106T092809Z/s3-regression.txt)
- [s4-matrix.txt](results/raw/s4-validation-20261106T092809Z/s4-matrix.txt)
- [short-fair-witness.txt](results/raw/s4-validation-20261106T092809Z/short-fair-witness.txt)
- [tests.txt](results/raw/s4-validation-20261106T092809Z/tests.txt)
- [traces.txt](results/raw/s4-validation-20261106T092809Z/traces.txt)

### Final measured S4 results

Depth is actual Promela search depth; time_s is measured verifier wall time;
memory_mb is reported pan total memory. Generation/compile/replay timings and
commands are recorded separately in metadata. Single-run times are not a
performance benchmark. Every search used full-state storage and the existing
100000-depth / 512-MB limits. No depth/memory truncation occurred.

| Case | Result | Depth | CE decisions | time_s | memory_mb | Stored states | Transitions | Evidence |
|---|---|---|---|---|---|---|---|---|
| L2-v0-default-none | FAIL | 1207 | 17 | 0.014523 | 7.536 | 604 | 604 | [metadata](results/raw/L2-v0-default-none-20261106T092837197598Z/metadata.json) |
| L2-v0-default-request | PASS | 2801 | - | 0.013218 | 7.927 | 7826 | 23420 | [metadata](results/raw/L2-v0-default-request-20261106T092838073024Z/metadata.json) |
| L2-v0-default-eligible | PASS | 2801 | - | 0.008290 | 7.829 | 6647 | 16832 | [metadata](results/raw/L2-v0-default-eligible-20261106T092839187916Z/metadata.json) |
| L2-v0-y0-none | FAIL | 1207 | 17 | 0.012273 | 7.536 | 604 | 604 | [metadata](results/raw/L2-v0-y0-none-20261106T092840397158Z/metadata.json) |
| L2-v0-y0-request | PASS | 2747 | - | 0.013759 | 7.829 | 6241 | 18229 | [metadata](results/raw/L2-v0-y0-request-20261106T092841227604Z/metadata.json) |
| L2-v0-y0-eligible | PASS | 2747 | - | 0.011163 | 7.731 | 5060 | 12268 | [metadata](results/raw/L2-v0-y0-eligible-20261106T092842336371Z/metadata.json) |
| L2-v0-any-none | FAIL | 1207 | 17 | 0.011875 | 7.536 | 604 | 604 | [metadata](results/raw/L2-v0-any-none-20261106T092843450262Z/metadata.json) |
| L2-v0-any-request | FAIL | 4981 | 37 | 0.010167 | 7.829 | 5898 | 7597 | [metadata](results/raw/L2-v0-any-request-20261106T092844259554Z/metadata.json) |
| L2-v0-any-eligible | PASS | 4305 | - | 0.015851 | 8.610 | 20767 | 44152 | [metadata](results/raw/L2-v0-any-eligible-20261106T092845590793Z/metadata.json) |
| L2-v0-L1-none | FAIL | 2365 | 33 | 0.015956 | 7.634 | 1915 | 3677 | [metadata](results/raw/L2-v0-L1-none-20261106T092846701680Z/metadata.json) |
| L2-v0-L1-request | PASS | 5041 | - | 0.068917 | 16.423 | 145623 | 448952 | [metadata](results/raw/L2-v0-L1-request-20261106T092847522020Z/metadata.json) |
| L2-v0-L1-eligible | PASS | 5041 | - | 0.062323 | 15.739 | 133797 | 354396 | [metadata](results/raw/L2-v0-L1-eligible-20261106T092848684396Z/metadata.json) |

Stage snapshots: [S4 only](results/snapshots/s4-v0-results.csv) and
[through S4](results/snapshots/through-s4-v0-results.csv). Source/script snapshots
are retained under results/snapshots/s4-model and s4-scripts. Earlier stage
snapshots were not replaced; run-local sources preserve original trails.

### Cycle analysis and interpretation

A replay marker can split a decision. ce_length counts ACTION starts in the
prefix plus one period; it is not elapsed seconds or a shortest-witness claim.
REQUEST events record original input and eligibility. Loop OBS samples identify
which greens recur; no ACTION or time samples would invalidate interpretation.

For each failing loop, the selected premise holds and at least one direction
is absent. Rotating to completed decision boundaries and repeating the input
period in the Python extraction closes the documented projected state, with
positive time and matching services/fairness. This is supplementary quotient
validation, not a finite simulation proof of infinite full-system behavior.

| Case | Prefix ACTION events | Period ACTION events | Period sample seconds | Recurrent greens | Missing direction | Reference period seconds |
|---|---|---|---|---|---|---|
| L2-v0-default-none | 16 | 1 | 5 | [0] | EW | 5 |
| L2-v0-y0-none | 16 | 1 | 5 | [0] | EW | 5 |
| L2-v0-any-none | 16 | 1 | 5 | [0] | EW | 5 |
| L2-v0-any-request | 1 | 36 | 192 | [0] | EW | 192 |
| L2-v0-L1-none | 32 | 1 | 5 | [2] | NS | 5 |

The four unconditional cases fail, including static fidelity: after online
takeover a nondeterministic agent can retain one direction forever. Input
request fairness suffices on the legal-action scenarios in the checked model,
but fails under any's invalid actions. Stronger eligible-request fairness passes
all four scenarios. These are conditional guarantees, not assumptions shown
true of a trained policy. Fair premises were separately witnessed realizable;
this does not mean every input execution satisfies them. Conditional y0 L2
PASS coexists with T1/y0 FAIL because recurring service does not guarantee safety.

### Compact report case study: request fairness is insufficient

Constrain only the input generator to prefix [0,0,2,1,0], then repeat [0,2,1,0].
The prefix reaches online NS with controller age5. In each period:

| Input | Age at request | Effect |
|---|---|---|
| 0 | 5 | Retain NS; delta advances age to10 |
| 2 | 10 | Invalid action; yellow then NS fallback, stored phase2, age resets to5 |
| 1 | 5 | EW request ignored because minimum green is not met; age advances to10 |
| 0 | 10 | Yellow then NS, stored phase0, age resets to5 |

A period is 4*5 +2*3 =26 seconds. Requests0/1 occur infinitely often but EW
never gets green; the request1 is always ineligible. SPIN reports an acceptance
cycle and the reference quotient closes. Its saved Buchi marker rotates the
four-action word (prefix/cycle event counts need not equal policy segmentation).
No shortest/minimality claim is made. Original 36-decision DFS period remains
preserved separately. This links source fallback/min-green semantics, Promela
translation, temporal assumptions and a concrete counterexample for the report.

### Limits and next step

Infinite claims apply to ongoing positive-time control and the documented
abstraction; real training episodes terminate. The request-event sampling and
age projection require human review. No SUMO execution or v1 proof is claimed.
Do not call the stronger input premise a repair. S5 must implement FIX-1..4
and separately handle invalid-input rejection and unconditional service.
README now marks S4 complete. Stop at this stage and report; next is S5.

S4 interpretation note: infinitely frequent requests can have arbitrarily long
finite gaps. Conditional L2 service therefore does not establish the numeric
L1 waiting bound; the S3 L1 failures and S4 conditional L2 passes are compatible.

## S5: exact v1 modeling and comparison (2026-11-06)

Stage complete. HEAD at start:30a3b1f, user's S4 commit. Source, shared contracts
and ESBMC implementation were not modified; no assistant Git write occurred.

### Questions and patch mapping

Does exactly FIX-1..4 remove the observed v0 defects on shared default inputs?
Does the accepted timing domain justify a universal max-green claim?

VERSION=1 mirrors the patch: reject invalid parameters and both unreachable
switch points; take control before warmup and count its10 seconds; reject illegal
actions before forcing; force opposite phase if age+delta>max, then use the
existing minimum-green guard. Original chosen input is retained in ACTION and
REQUEST instrumentation; FORCED shows its effective target. VERSION=0 preserves
the original source behavior, as checked by40 regression cases.

The model uses the patch's exact first-switch-point expression. Its integer
conditional and ceil calculation were checked through accepted/rejected traces,
including delta0 where division must never occur. Controller saturation remains
above the min/max/look-ahead thresholds for all selected cases; the first bad
observed-green state is preserved. See MODEL_MAPPING.md for line/function mapping.

### Input contracts and avoiding vacuous results

The main v1 matrix has20 default-parameter checks: seven finite properties and
three L2 fairness modes in both default/static scenarios. Inputs are legal0/1.
We do not silently prune errors and call y0/any normal-operation PASS:
- y0 is rejected by FIX-3 before reset/traffic time begins.
- illegal actions are rejected by FIX-2 before forcing or time advancement.
- finite rejected executions are not included in normal infinite L2 claims.

Dedicated comparison command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/check_v1.py \
  --output verification/spin/results/raw/s5-v1-contract-traces.json
```

The original evidence file exists; choose a fresh path to rerun. Actual outcome:
42 cases matched the unchanged Python v1 extraction:16 accepted traces and26
expected rejections (21 input sequences/configurations times static on/off).
The complete records, including REJECT reasons and ABORT states, are retained
in [contract evidence](results/raw/s5-v1-contract-traces.json). ACCEPTED here is
an input outcome, not a property verdict. Rejected constructor cases compare
reason only because no reference environment object/reset exists. Rejected
actions compare unchanged control/time state as well.

Cases cover prolonged0/1 requests; non-divisible intervals; delta0/negative;
yellow0/2; negative min, zero max, min>max; both unreachable switch-point guards;
illegal-1/2 initially, after a switch and exactly when forcing would otherwise
occur. The latter confirms validation priority. The accepted wide-delta trace
is retained as a diagnostic rather than being mislabeled safe.

### Main searches and validation commands

```sh
python3 verification/spin/scripts/run_spin.py --stage S5
python3 verification/spin/scripts/run_spin.py --stage S2
python3 verification/spin/scripts/run_spin.py --stage S3
python3 verification/spin/scripts/run_spin.py --stage S4
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/test_verification.py
python3 verification/spin/scripts/check_traces.py --version v0 \
  --output verification/spin/results/raw/s1-trace-comparison.json
python3 verification/spin/scripts/check_traces.py --version v1 \
  --output verification/spin/results/raw/s5-v1-trace-comparison.json
PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/check_liveness.py --version v1 \
  --output verification/spin/results/raw/s5-v1-liveness-controls
```

Actual S5 outcomes:25 PASS/7 FAIL out of32. All20 v1 default legal-input checks
PASS; six G2 probe pairs give six v0 FAILs and five v1 PASS/one v1 FAIL. All40
previous v0 verdicts/depths remained unchanged. No UNKNOWN/TIMEOUT/ERROR occurred.
Combined dataset:72 cases,46 PASS/26 FAIL. Existing14 tests passed in25.087 s;
v0 96 cases match18,898 records; v1 96 cases match5,752 records, including early
rejection events. These trajectory counts do not imply equal executed coverage.
Eleven LTL controls matched expected outcomes and four full-model v1 fairness
premises were witnessed feasible (default/static times request/eligible modes).

Retained validation logs:
- [commands.json](results/raw/s5-validation-20261106T112109Z/commands.json)
- [s2-regression.txt](results/raw/s5-validation-20261106T112109Z/s2-regression.txt)
- [s3-regression.txt](results/raw/s5-validation-20261106T112109Z/s3-regression.txt)
- [s4-regression.txt](results/raw/s5-validation-20261106T112109Z/s4-regression.txt)
- [tests.txt](results/raw/s5-validation-20261106T112109Z/tests.txt)
- [v0-traces.txt](results/raw/s5-validation-20261106T112109Z/v0-traces.txt)
- [v1-fairness-controls.txt](results/raw/s5-validation-20261106T112109Z/v1-fairness-controls.txt)
- [v1-traces.txt](results/raw/s5-validation-20261106T112109Z/v1-traces.txt)

These are one main S5 sweep and regression measurements, not a repeated
performance study. Frozen [S5](results/snapshots/s5-results.csv) contains32 rows;
[through S5](results/snapshots/through-s5-results.csv) contains72. Earlier stage
snapshots are unchanged. Model/script sources are frozen under s5-model and
s5-scripts; raw runs retain their own model copies, digests and exact commands.

### Measured S5 rows

| Case | Version | Result | Depth | CE decisions | Verifier time_s | memory_mb | Stored states | Transitions | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| S1-v1-default | v1 | PASS | 908 | - | 0.007054 | 7.536 | 1439 | 1466 | [metadata](results/raw/S1-v1-default-20261106T111935622794Z/metadata.json) |
| S1-v1-L1 | v1 | PASS | 908 | - | 0.008907 | 7.536 | 1439 | 1466 | [metadata](results/raw/S1-v1-L1-20261106T111936924314Z/metadata.json) |
| T1-v1-default | v1 | PASS | 908 | - | 0.008646 | 7.536 | 1439 | 1466 | [metadata](results/raw/T1-v1-default-20261106T111937668961Z/metadata.json) |
| T1-v1-L1 | v1 | PASS | 908 | - | 0.005567 | 7.536 | 1439 | 1466 | [metadata](results/raw/T1-v1-L1-20261106T111938460122Z/metadata.json) |
| T2-v1-default | v1 | PASS | 1817 | - | 0.008617 | 7.536 | 1623 | 2216 | [metadata](results/raw/T2-v1-default-20261106T111939224072Z/metadata.json) |
| T2-v1-L1 | v1 | PASS | 1817 | - | 0.007344 | 7.536 | 1623 | 2216 | [metadata](results/raw/T2-v1-L1-20261106T111940037751Z/metadata.json) |
| G1-v1-default | v1 | PASS | 908 | - | 0.007940 | 7.536 | 1439 | 1466 | [metadata](results/raw/G1-v1-default-20261106T111940898098Z/metadata.json) |
| G1-v1-L1 | v1 | PASS | 908 | - | 0.008033 | 7.536 | 1439 | 1466 | [metadata](results/raw/G1-v1-L1-20261106T111941654415Z/metadata.json) |
| C1-v1-default | v1 | PASS | 952 | - | 0.012098 | 7.536 | 1491 | 1518 | [metadata](results/raw/C1-v1-default-20261106T111942408467Z/metadata.json) |
| C1-v1-L1 | v1 | PASS | 952 | - | 0.007761 | 7.536 | 1491 | 1518 | [metadata](results/raw/C1-v1-L1-20261106T111943182486Z/metadata.json) |
| G2-v1-default | v1 | PASS | 930 | - | 0.008404 | 7.536 | 1465 | 1492 | [metadata](results/raw/G2-v1-default-20261106T111943960598Z/metadata.json) |
| G2-v1-L1 | v1 | PASS | 930 | - | 0.008455 | 7.536 | 1465 | 1492 | [metadata](results/raw/G2-v1-L1-20261106T111944748573Z/metadata.json) |
| L1-v1-default | v1 | PASS | 997 | - | 0.006657 | 7.634 | 2118 | 2156 | [metadata](results/raw/L1-v1-default-20261106T111945523238Z/metadata.json) |
| L1-v1-L1 | v1 | PASS | 997 | - | 0.009891 | 7.634 | 2118 | 2156 | [metadata](results/raw/L1-v1-L1-20261106T111946323534Z/metadata.json) |
| L2-v1-default-none | v1 | PASS | 1907 | - | 0.019178 | 7.634 | 3209 | 8417 | [metadata](results/raw/L2-v1-default-none-20261106T111947096685Z/metadata.json) |
| L2-v1-default-request | v1 | PASS | 2331 | - | 0.016136 | 7.927 | 7149 | 21257 | [metadata](results/raw/L2-v1-default-request-20261106T111947919741Z/metadata.json) |
| L2-v1-default-eligible | v1 | PASS | 2331 | - | 0.009926 | 7.829 | 6927 | 18337 | [metadata](results/raw/L2-v1-default-eligible-20261106T111949252525Z/metadata.json) |
| L2-v1-L1-none | v1 | PASS | 1907 | - | 0.005263 | 7.634 | 3209 | 8417 | [metadata](results/raw/L2-v1-L1-none-20261106T111950545516Z/metadata.json) |
| L2-v1-L1-request | v1 | PASS | 2331 | - | 0.013496 | 7.927 | 7149 | 21257 | [metadata](results/raw/L2-v1-L1-request-20261106T111951351516Z/metadata.json) |
| L2-v1-L1-eligible | v1 | PASS | 2331 | - | 0.013105 | 7.927 | 6927 | 18337 | [metadata](results/raw/L2-v1-L1-eligible-20261106T111952500654Z/metadata.json) |
| G2-v0-default-dt7 | v0 | FAIL | 353 | 8 | 0.013391 | 7.536 | 354 | 354 | [metadata](results/raw/G2-v0-default-dt7-20261106T111953668272Z/metadata.json) |
| G2-v1-default-dt7 | v1 | PASS | 922 | - | 0.010677 | 7.634 | 1684 | 1711 | [metadata](results/raw/G2-v1-default-dt7-20261106T111954497484Z/metadata.json) |
| G2-v0-default-max61 | v0 | FAIL | 385 | 11 | 0.014463 | 7.536 | 386 | 386 | [metadata](results/raw/G2-v0-default-max61-20261106T111955248408Z/metadata.json) |
| G2-v1-default-max61 | v1 | PASS | 930 | - | 0.009018 | 7.536 | 1465 | 1492 | [metadata](results/raw/G2-v1-default-max61-20261106T111956062969Z/metadata.json) |
| G2-v0-default-dt3max16 | v0 | FAIL | 88 | 3 | 0.008411 | 7.536 | 89 | 89 | [metadata](results/raw/G2-v0-default-dt3max16-20261106T111956814428Z/metadata.json) |
| G2-v1-default-dt3max16 | v1 | PASS | 414 | - | 0.010491 | 7.536 | 703 | 723 | [metadata](results/raw/G2-v1-default-dt3max16-20261106T111957629006Z/metadata.json) |
| G2-v0-default-min0dt7 | v0 | FAIL | 45 | 1 | 0.009492 | 7.536 | 46 | 46 | [metadata](results/raw/G2-v0-default-min0dt7-20261106T111958383180Z/metadata.json) |
| G2-v1-default-min0dt7 | v1 | PASS | 203 | - | 0.008994 | 7.536 | 219 | 223 | [metadata](results/raw/G2-v1-default-min0dt7-20261106T111959203700Z/metadata.json) |
| G2-v0-default-min12dt1 | v0 | FAIL | 124 | 7 | 0.007648 | 7.536 | 125 | 125 | [metadata](results/raw/G2-v0-default-min12dt1-20261106T111959955097Z/metadata.json) |
| G2-v1-default-min12dt1 | v1 | PASS | 645 | - | 0.007433 | 7.536 | 1221 | 1276 | [metadata](results/raw/G2-v1-default-min12dt1-20261106T112000778256Z/metadata.json) |
| G2-v0-default-delta_gt_max | v0 | FAIL | 45 | 1 | 0.006098 | 7.536 | 46 | 46 | [metadata](results/raw/G2-v0-default-delta_gt_max-20261106T112001523435Z/metadata.json) |
| G2-v1-default-delta_gt_max | v1 | FAIL | 139 | 1 | 0.006341 | 7.536 | 140 | 140 | [metadata](results/raw/G2-v1-default-delta_gt_max-20261106T112002334568Z/metadata.json) |

time_s is verifier wall time, not generation/compile duration; memory_mb is pan's
total actual memory. Single-run milliseconds should not be used to claim one
method faster without a controlled benchmark. All PASS searches completed with
full-state storage under the existing depth/memory limits. Finite S5 failures
were replayed and reproduced with the matching version/configuration reference.

### Default comparison: what the fixes achieve

G2 and L1 change from FAIL to PASS in default/static cases. T2/G1/C1 static
failures disappear after takeover-before-warmup and consistent phase accounting.
Unconditional L2 changes from FAIL to PASS without assuming agent fairness,
because FIX-1 forces switches under accepted default timings. Conditional variants
also pass and their premises are feasible. This does not prove a learned policy
fair or prove all possible parameter combinations correct. S2 safety PASSs stay
PASS where applicable. Detailed comparison matrix is in FINDINGS.md.

Input-domain changes are part of the comparison: y0/illegal actions become
explicitly rejected inputs. Do not present rejection as successful traffic
execution or interpret a halted error run as an infinite service guarantee.

### Residual accepted-parameter defect (preserved, not silently repaired)

Before editing the model, a direct execution of the unchanged Python v1 core
showed delta12/yellow3/min0/max11 is accepted but triggers its G2 monitor. This
was explained to the user before implementation. The main SPIN probe then
confirmed the same behavior with a stored trail and reference reproduction:

```sh
python3 verification/spin/scripts/run_spin.py G2-v1-default-delta_gt_max
```

The constructor computes first_switch_point(10)=10 and
first_switch_point(0)=0 when min_green=0; both are<=11, so it accepts. At the
first decision, age10+delta12>max11 forces EW, then the unchanged delta loop
shows EW for12 intervals. The selected G2 assertion fails at pre-step t24,
started decision1, observed green age12, controller age11. The v0 comparison
also fails, but earlier, because its first NS green exceeds11 after warmup.
This is a defect in the parameter-admission reasoning, not a Promela correction
or test malfunction. It is outside the teammate's recorded delta1..7 sweep,
so it does not contradict the default PASSs or that narrower experiment.

Five other selected probes (delta7/max60, delta5/max61, delta3/min10/max16,
delta7/min0/max11, delta1/min12/max16) pass G2 in v1 and fail in v0. These show
useful non-divisible-boundary behavior, not universal parameter correctness.
A candidate remedy is an additional delta<=max admissibility check, or a change
to intra-decision control. No remedy, shared contract amendment or original-source
patch was applied; any follow-up must be reviewed with the ESBMC owner/user.
No new shared property/defect ID was invented for this finding.

### Limits and next stage

S5 completes exact-patch modeling and comparison, not a declaration that every
v1 input accepted by the patch is safe. Real SUMO replay/conformance, human
model review, final tool comparison and report packaging remain S6. The original
controller/ESBMC/shared files are untouched. Stop after this stage and report.

## S6: real source validation, reproducibility and report preparation (2026-11-06)

Technical validation is complete. Human model review and joint-report sign-off
remain pending. HEAD at stage start was e02f7c2, the user's S5 commit. The
worktree controller, network, ESBMC and shared contracts were not modified.

### Runtime installation and an unsuccessful attempt

Python3.12 Homebrew installation was attempted to match the teammate's example.
Its bottle transfer repeatedly stalled/restarted and was cancelled (exit130);
no Python3.12 run is claimed. Rather than blocking validation, an ignored .venv
was created with the existing Python3.13.7 and the fixed SUMO1.28.0 packages.
SUMO wheel downloads and installation succeeded; exact package pins are saved
in requirements-sumo.txt. This is an explicit difference from the suggested
Python3.12 setup, not a hidden version substitution.

Tested versions: eclipse-sumo/traci/sumolib1.28.0; sumo-data1.28.0;
gymnasium1.4.0; NumPy2.5.4; other installed pins in requirements-sumo.txt.
SUMO binary build metadata is in the full live summary. No PyTorch/training
packages or ESBMC executable were needed for this SPIN stage.

### Saved-evidence audit and fresh-copy reproduction

```sh
python3 verification/spin/scripts/audit_results.py \
  --output verification/spin/results/raw/s6-audit.json
python3 verification/spin/scripts/reproduce.py \
  --output verification/spin/results/raw/s6-isolated-reproduction
```

Both original output paths exist; select new paths for reruns. Audit checked
all72 CSV rows against raw pan output, source hashes and21 finite/five cyclic
witnesses. A fresh temporary copy of code/network/reference files ran all72
formal cases, matching every verdict, depth and CE decision count. Measured
wall time was64.059141 s including generation/compilation; single-row verifier
timings were measured again and are not expected identical. The same installed
SPIN/compiler was used: this is isolated-path/output reproduction, not a second
machine or clean tool installation. Original results.csv was not overwritten.
Evidence: [audit](results/raw/s6-audit.json),
[reproduction](results/raw/s6-isolated-reproduction/summary.json).

### Independent real-source validation

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python verification/spin/scripts/validate_sumo.py \
  --output verification/spin/results/raw/s6-sumo-full
```

The script loads full original src/environment.py, rather than extracted core.
v1 is a temporary full-source copy patched by the unchanged shared patch. It
observes real TraCI signal/program/time states and uses independent monitors
that do not import the ESBMC stub/core. Both off_peak and morning_rush routes
were exercised. Projection compares source/controller time, displayed signal,
controller phase/projected age and online status; abstract frozen static-cursor
fields are not asserted to be real source fields after takeover.

Initial smoke: v0 hold and v1 hold traces matched; deliberate v0/L0 control
mismatched. Full test:38 selected source/model cases matched7,205 projected
records, including rejected v1 inputs, plus one expected negative control.
All tested L1 projected traces matched; this supports the chosen abstraction
but is not a universal source-model equivalence proof. Fixed and six seeded
input policies per version cover takeover, invalid actions, zero yellow and
selected timing profiles. Early rejection MATCHs are not normal-run PASSs.

Actual static transitions in the pre-step samples were t43/46/88/91. These
confirm43 initial samples and subsequent42/3/42/3 behavior for SUMO1.28.0 under
this convention; do not conflate pre-step sample counts with all possible
physical-duration/observation conventions. Actual transition metadata includes
program phase and next-switch time for independent review.

### Original finite witness replay: favorable and unfavorable outcomes

Twenty-one original finite assertion prefixes were replayed directly on source:
12 reproduced the selected target and9 did not within the original prefix.
All9 non-reproductions are L0. Model FAIL is retained; non-reproduction is a
separate evidence category, not a reason to change it to PASS. L0 both omits
autonomous behavior and admits held-initial-green paths, so it is not generally
conservative. Main source-backed conclusions use L1 and actual replay.

| Original case | Target reproduced | First live target time_s | Original reference time_s | Evidence |
|---|---|---|---|---|
| G2-v0-default-dt7 | False | - | 60 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-default-dt7.json) |
| G2-v0-default-max61 | False | - | 61 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-default-max61.json) |
| G2-v0-default-dt3max16 | True | 16.0 | 16 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-default-dt3max16.json) |
| G2-v0-default-min0dt7 | True | 11.0 | 11 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-default-min0dt7.json) |
| G2-v0-default-min12dt1 | True | 16.0 | 16 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-default-min12dt1.json) |
| G2-v0-default-delta_gt_max | True | 11.0 | 11 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-default-delta_gt_max.json) |
| G2-v1-default-delta_gt_max | True | 24.0 | 24 | [source trace](results/raw/s6-sumo-full/replay-G2-v1-default-delta_gt_max.json) |
| T1-v0-y0 | False | - | 90 | [source trace](results/raw/s6-sumo-full/replay-T1-v0-y0.json) |
| T2-v0-any | True | 93.0 | 189 | [source trace](results/raw/s6-sumo-full/replay-T2-v0-any.json) |
| T2-v0-L1 | True | 93.0 | 93 | [source trace](results/raw/s6-sumo-full/replay-T2-v0-L1.json) |
| G1-v0-L1 | True | 145.0 | 145 | [source trace](results/raw/s6-sumo-full/replay-G1-v0-L1.json) |
| C1-v0-any | True | 45.0 | 181 | [source trace](results/raw/s6-sumo-full/replay-C1-v0-any.json) |
| C1-v0-L1 | True | 45.0 | 45 | [source trace](results/raw/s6-sumo-full/replay-C1-v0-L1.json) |
| G2-v0-default | False | - | 60 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-default.json) |
| G2-v0-y0 | False | - | 60 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-y0.json) |
| G2-v0-any | False | - | 60 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-any.json) |
| G2-v0-L1 | True | 75.0 | 75 | [source trace](results/raw/s6-sumo-full/replay-G2-v0-L1.json) |
| L1-v0-default | False | - | 66 | [source trace](results/raw/s6-sumo-full/replay-L1-v0-default.json) |
| L1-v0-y0 | False | - | 60 | [source trace](results/raw/s6-sumo-full/replay-L1-v0-y0.json) |
| L1-v0-any | False | - | 66 | [source trace](results/raw/s6-sumo-full/replay-L1-v0-any.json) |
| L1-v0-L1 | True | 254.0 | 254 | [source trace](results/raw/s6-sumo-full/replay-L1-v0-L1.json) |

Examples of differing mechanisms/times are retained: T2/any reaches a live
same-direction return at t93 rather than the L0 reference's t189; C1/any first
has signal disagreement at t45 and later illegal phase at t181. Target
reproduction alone is not a claim of an identical counterexample trace.
The shared script independently reproduced short T1/G2/C1 examples; its exit0
means a property failure reproduced, not a property PASS. Original shared
script output is in results/raw/s6-common-replay/.

### Short source-backed examples and model-to-source narrative

| Example | Actual source finding | Input/evidence |
|---|---|---|
| y0 | Direct green change at t20, decision3 | [0,0,1] with yellow0 |
| Overlong green | Observed green61 at t83; controller age65 check at t88 | [0,0,1] then twelve1 inputs |
| Bounded wait | NS wait67>66 at t86 | [0,0,1] then thirteen1 inputs |
| G1/static | Displayed EW9 observations is terminated at t145 while controller age135 satisfies its guard | Original G1/L1 witness |
| v1 residual parameter defect | Observed EW12>11 at t24; controller age12 check at t25 | delta12/min0/max11/yellow3, input0 |

Timestamps are pre-step samples or completed boundaries as labeled; the run
continues through the actual step. The G1 example directly connects the source
minimum-green guard, separate model ages, SPIN assertion and real failure.
Full samples, monitor events, source/patch digests and captured output are
preserved. No fix to the residual parameter problem was applied.

### Infinite-model claims versus finite loop observations

The five L2 prefixes were additionally expanded for three periods and observed
on real source. Results below are finite conformance outcomes, never new
infinite L2 verdicts. The initial three pure0 L0 examples remain in static
program0; a finite NS-only tail does not establish eventual starvation because
the autonomous program will switch again. Online takeover changes that reasoning.

| Model witness | Full finite trace matches source | Final program | Last period green codes |
|---|---|---|---|
| L2-v0-default-none | False | 0 | [0] |
| L2-v0-y0-none | False | 0 | [0] |
| L2-v0-any-none | False | 0 | [0] |
| L2-v0-any-request | False | online | [0] |
| L2-v0-L1-none | True | online | [2] |

The static L1 witness matches the full finite source trace and is online in
the loop. The any/request witness differs during initial L0/static behavior,
then exhibits an online NS-only period. Its formal infinite conclusion still
comes from SPIN plus the stated abstraction, not three observed periods. The
compact fair-input example was also repeated on source, supporting its source
mechanism. Data: results/raw/s6-l2-finite-expansions/summary.json. Reproducer:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python verification/spin/scripts/validate_l2_sumo.py \
  --output verification/spin/results/raw/s6-l2-expansion-rerun
```

### Fixed-network identity check

The official SUMO library getJunctionIndex/getTLLinkIndex APIs were used to
compare all14 controlled connection indices, not merely their counts. Every
pair matched, and all four phase states had zero protected G/G foes. This
strengthens the fixed-network S1 assumption; TLS/junction indices can differ
in general networks. Data: results/raw/s6-network-audit.json. Official semantics
are linked in SPIN_REPORT.md; permissive g is not protected G.

### Final artifacts and remaining human work

- SUMO_VALIDATION.md and results/sumo-replay.csv preserve all live outcomes.
- SPIN_REPORT.md is a reviewable SPIN technical draft for the joint report.
- REVIEW_CHECKLIST.md is explicitly pending human review, as the proposal requires.
- requirements-sumo.txt pins the installed live environment; .venv is ignored.
- Original formal rows/metrics are unchanged; additional checks are supplementary.
- The teammate's actual ESBMC results.csv is absent in this checkout; no numerical
  comparison or teammate result was fabricated. Joint integration needs that evidence.

S6 technical work is ready for review. Do not mark human sign-off completed on
behalf of the user or imply complete-source/infinite SUMO proof. The open v1
parameter-admission defect and C1/D4 interpretation require explicit final-report
handling. No automatic commit/push/merge, source patch or network regeneration.
