# SPIN experimental record and report material

Last updated: 2026-11-06 (Asia/Shanghai). Current milestone: **v0 through S2**.
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

## Milestone status

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
