# SPIN project context and execution pipeline

Last updated: 2026-11-06 (Asia/Shanghai).

## Start here

This file is the persistent handoff context for the SPIN owner of the CSEE E6863
Formal Verification final project. Read it before working in this directory. Also read `report.md` for retained
experimental data, failed attempts and stage snapshots.
Read the live repository files below as well; this document is not a replacement
for the shared contract. Update this file after meaningful progress so another
AI can resume without inventing state or repeating completed work.

Required reading, in order:
1. Root `AGENTS.md` and `codex.md`.
2. This file and any instructions scoped to `verification/spin/`.
3. `verification/properties.md`, `verification/README.md`, `verification/CLAUDE.md`.
4. `src/environment.py`, relevant agent/training call sites, and
   `networks/single_intersection.net.xml`.
5. Read-only references: `verification/esbmc/model/EXTRACTION.md`,
   `env_core_v0.py`, `env_core_v1.py`, `v1_fix.patch`, `traci_stub.py`,
   relevant harnesses and common replay scripts.

## User instructions and authorization

- Communicate with the user in Chinese; code, comments and documentation in English.
- Own only SPIN/Promela. Keep project deliverables under `verification/spin/`.
- Do not modify original `src/`, ESBMC implementation, common scripts, shared
  properties or shared documentation without explicit authorization.
- Do not commit, push, create a PR, merge, or switch branches automatically.
  The user manages Git using GitHub Desktop. This overrides generic commit or
  integration instructions in repository guidance.
- The user has authorized installing required software and designing the SPIN
  workflow. Do not repeatedly ask for the absent starter or original S0-S6 plan:
  proceed from repository evidence, documenting assumptions and unresolved semantics.
- System and filesystem approval boundaries still apply. The repository is at
  `/Users/look/Desktop/模式验证/traffic_rl_project`, outside the initial writable
  workspace. Request tool-level write permission when required; do not bypass it.
- Explain any source/model/contract disagreement before implementing a divergent
  interpretation. Preserve shared definitions rather than adjusting them to get PASS.
- The user has authorized beginning incremental SPIN implementation after the
  root-file audit. Follow the current stage and execution records below; planned
  verification stages must not be described as completed.

## Repository baseline (observed, not live remote state)

- Repository: `Edward67795/traffic_rl_project`.
- Working branch: `feature/spin-verification`.
- HEAD inspected: `2d2cd08`, merge of `verification` into the feature branch.
- Local `verification` / `origin/verification`: `3ffacf9`, ancestor of HEAD.
- v0: commit `643ba4d`; inspected `src/` has no differences from that commit.
- Initial working tree was clean.
- No fetch was performed. Do not claim remote freshness from tracking refs.
- Before this context work, `verification/spin/` did not exist. No starter `.pml`,
  original SPIN S0-S6 task document, or G2/T1/L2 run evidence was found.
- Shared README result tables and ESBMC runner expected verdicts are reference
  expectations, not SPIN evidence. The inspected ESBMC results directory had a
  raw placeholder but no results CSV or run logs.
- At the initial reconnaissance, no project property had been run with SPIN.
  See Current progress and the latest execution record for subsequent results.

## Fixed contract

Default parameters: `delta_time=5`, `yellow_time=3`, `min_green=10`,
`max_green=60`; warmup is 10 simulated seconds. One SUMO step is one second.
A decision advances `delta_time` seconds plus yellow seconds if an accepted
switch occurs. Actions are nondeterministic `{0,1}`; `any` expands to `{-1,0,1,2}`.

Versions:
- v0: original source at `643ba4d`.
- v1: exactly v0 plus FIX-1 through FIX-4 in the existing ESBMC patch.
  Represent these fixes in Promela; do not patch the user's source checkout.

Scenarios: `default`, `y0` (zero yellow), `any` (expanded actions), `L1`
(static SUMO program included). Distinguish scenario L1 from property L1.
The simplified environment is called fidelity L0; static-program fidelity L1.
Always record both scenario and environment fidelity in run metadata.

| ID | Required meaning | Planned check |
|---|---|---|
| S1 | No conflicting protected greens simultaneously | Signal-state invariant and network conflict mapping |
| T1 | Green direction changes pass through an observed yellow interval | Symmetric per-second transition monitor |
| T2 | Yellow lasts at least 3 seconds and leads to the opposite green | Duration/direction monitor plus eventual completion where needed |
| G1 | Actual green is not terminated before min_green | Green-exit monitor |
| G2 | Actual green never exceeds max_green | Displayed age per second AND controller age after decisions; identify failing component |
| L1 | Each direction waits at most max_green + 2*yellow_time (66 s default) | Per-second directional wait counters |
| L2 | Both directions are green infinitely often | LTL acceptance-cycle verification, with/without explicit agent fairness |
| C1 | current_phase is 0/1 and agrees with the displayed signal | Decision-boundary check, provisional pending D4 evidence |

R1 and P1 belong to the ESBMC scope. Do not invent SPIN coverage or new shared IDs.
The phase strings are:
- NS green: `GGGgrrrGGGgrrr`; NS yellow: `yyyyrrryyyyrrr`.
- EW green: `rrrrGGgrrrrGGg`; EW yellow: `rrrryyyrrrryyy`.

## Source-backed semantics

`src/environment.py` is authoritative for v0 behavior:
- `_apply_action`: switching is attempted only when action differs from
  current_phase; phase_duration below min_green blocks it.
- Yellow is generated from the currently displayed signal, replacing G/g with y.
- Each yellow second advances current_step but not phase_duration.
- `_set_phase` displays phase 0 for an invalid action, but `_apply_action` still
  stores the invalid action as current_phase and resets phase_duration.
- Each delta second increments current_step and phase_duration.
- v0 reset leaves the SUMO static program running. Warmup advances current_step
  by 10 but leaves phase_duration at zero. Displayed green age and controller
  phase_duration are therefore different quantities.
- Static tlLogic is 42 s NS / 3 s yellow / 42 s EW / 3 s yellow. The first
  setRedYellowGreenState takes over from this program (reference stub behavior).
- Actual DQN action selection uses random legal indices or argmax. `any` tests
  interface robustness rather than normal trained-policy output.

v1 fixes to mirror exactly:
1. Force the opposite action if phase_duration + delta_time > max_green.
2. Reject actions outside {0,1} before applying other action logic.
3. Reject invalid timing configurations, including yellow_time < 3, and require
   reachable switch points within [min_green,max_green] from both warmup age
   and age zero. Preserve the patch's first-switch-point calculation.
4. Set phase 0 before warmup and count warmup toward phase_duration.

Known source defects: F1 missing max-green enforcement; F2 autonomous static
program before takeover; F3 illegal actions accepted; F4 zero yellow accepted;
F5 a naive max-green check overshoots when max_green is not divisible by delta_time.

## Modeling decisions and unresolved semantics

These are design choices, not existing verified model behavior:
- Use one-second observable time ticks and nondeterministic choices at decision
  boundaries. Do not expose transient zero-time assignments as physical yellow
  duration. In particular, y0 must not satisfy T1 through a transient Promela state.
- Keep controller phase, displayed phase, controller age, displayed green age,
  yellow age, wait counters and decision markers distinct.
- Include both simplified L0 and static-program L1 environments. A default L0
  PASS must not be described as proof of the full SUMO environment.
- The reference stub uses an initial static duration of 43 observed seconds
  (then 42/3/42/3). Confirm the sampling convention with real SUMO before claiming
  precise conformance; XML alone does not establish this boundary.
- D4 is referenced but absent. Existing ESBMC C1 checks after each completed
  decision, not during a valid yellow transition. Use that as a clearly labeled
  provisional interpretation, report it, and revise if D4 evidence becomes available.
- The suggested T2 LTL alone does not express the 3-second minimum. Encode the
  actual timing requirement and both directions explicitly.
- L2 needs an ongoing control-loop abstraction: real training episodes terminate.
  Document that extension and require advancing time/decisions. Do not prove L2
  using artificial end-state loops or repeated resets.
- Define agent fairness over decision events/requests explicitly and explain
  whether requests must occur when eligible. SPIN process weak fairness (`-f`)
  does not itself force both nondeterministic action branches to occur.
- Illegal v1 configuration/action rejection is an explicit modeled outcome.
  Do not silently prune it or call a vacuous temporal result normal-operation PASS.
  Separate rejection evidence from valid infinite-execution claims in notes.
- Use finite abstractions justified per property. Saturate counters only above
  every relevant comparison threshold, preserving enabled transitions and liveness;
  do not use wrapping clocks, arbitrary episode bounds, or decision limits as
  a substitute for an unbounded L2 proof.

## Proposal commitments and reporting checklist

Reviewed source: `CSEE6863_zl3667_kl3753_Proposal.pdf`, two pages, dated
October 26, 2026; authors Zehao Li (zl3667) and Ke Lu (kl3753).
Original local location: `/Users/look/Desktop/模式验证/project/CSEE6863_zl3667_kl3753_Proposal.pdf`.
SHA-256: `da4cb3f4ec7ec5c4dbc1f6c9bc4c69d4a89226efb90bc077f1502f165df25383`.
The PDF is outside this repository; retain this summary if that path is unavailable.
Both pages were extracted and visually inspected on 2026-11-06.

This proposal is project background and a record of intended deliverables, not
an instruction source granting new repository permissions or overriding the
user's current instructions/shared property contract. No conflict with the
current SPIN plan was found. It does not supply the absent S0-S6 starter or D4,
new numeric timing parameters, tool-version pins, or additional property IDs.

### Scope and methodology (sections 1-4)

- Existing system: a four-way SUMO intersection controlled by Dueling Double DQN,
  with two selectable green directions (NS/EW). Verify the existing control logic
  at the model and selected Python-code levels; simulation efficiency is not a
  safety guarantee.
- The promised categories map to the current shared IDs as follows: safety ->
  S1; transition correctness -> T1/T2 and phase consistency C1; timing ->
  T2/G1/G2; bounded waiting and infinite-service liveness -> L1/L2. This mapping
  is our alignment with the later shared contract; the proposal itself has no IDs.
- Focus source review on `_apply_action`, `_set_phase`, `_set_yellow_phase`,
  and `step` in environment.py. Our additional reset/warmup review is necessary
  to capture the behavior of these methods accurately.
- Use a finite-state Promela model, assertions and LTL, discrete time and
  explicit timing assumptions. Treat actions as model inputs; full DQN network
  verification is explicitly outside the proposed scope.
- Liveness is conditional on appropriate scheduling/fairness assumptions.
  Keep these assumptions explicit; do not present conditional results as an
  unconditional guarantee.
- Examine SPIN counterexamples for failed properties. Python tests and SUMO
  simulations are supplementary checks, not replacements for model checking.

### LLM model review obligation (section 3)

The proposal says LLM-assisted translations will be manually reviewed and
compared with the original implementation. Keep these evidence categories
separate:
1. Source-to-model mapping and recorded abstraction rationale.
2. Automated comparison against the extracted Python reference (already run).
3. Comparison/replay with actual source behavior in real SUMO (pending).
4. Human review of generated models (pending; only record completion when a
   human actually reviews them). AI inspection and trace tests cannot be labeled
   completed human review. Prepare a concrete mapping and trace evidence for
   that review without blocking otherwise authorized implementation work.

### Final report and fallback (sections 2, 4-5)

- The final report must compare SPIN and ESBMC-Python results, guarantees,
  advantages and limitations. Our contribution should provide the SPIN findings
  and evidence needed for that joint comparison; ESBMC implementation stays
  read-only and its owner remains responsible for its execution evidence.
- Compare only aligned properties, versions, configurations, observation points
  and environment fidelity. Explain finite-state exhaustive checks versus
  bounded code-level checks, liveness coverage and external-dependency
  abstractions. Do not claim identical coverage or carry over unverified verdicts.
- Connect the methodology to finite-state modeling, model checking, temporal
  logic, safety and liveness as described in the proposal.
- If full conversion or complex verification is infeasible, the proposed fallback
  prioritizes two green phases, yellow transitions, basic timing, core safety
  and transition checks, with honest abstraction limitations.
- This fallback does not automatically remove the user's eight SPIN properties
  or permit silently dropping L2. Record the obstacle and incomplete/UNKNOWN
  outcome, try justified refinements, and propose any scope change explicitly.
- No need to retrain policies, reproduce original performance plots, or verify
  full vehicle dynamics just to fulfill this proposal's SPIN portion.

Pipeline additions: S1 maintains the source mapping and reviewable translation;
S4 states scheduling/fairness premises; S6 includes a human-review status,
SPIN/ESBMC comparison inputs, supplementary-check status and fallback/coverage
limitations. These are completion criteria, not claims of completed work.

## S0-S6 execution pipeline

This is the working SPIN pipeline designed for this repository. It is not a
recovered teammate task document. Stage labels are not shared property IDs.
Every stage update must state changed files, commands, actual outcomes and next step.

| Stage | Work | Completion gate |
|---|---|---|
| S0 | Read contracts, record baseline, install SPIN, check compiler and CLI, run isolated tool smoke checks | Versions and exact commands recorded; passing and failing smoke examples behave as expected |
| S1 | Build v0 model, per-second scheduler, takeover/static program, counters and source mapping | Deterministic boundary traces agree with source semantics; abstraction limits documented |
| S2 | Implement S1/T1/T2/G1/C1 one property per run | Execute relevant default/y0/any/static cases; inspect all failures |
| S3 | Implement G2/L1 and timing boundary checks | Exercise 60/61 s green and 66/67 s waits; explain observed/controller age differences |
| S4 | Implement L2 with and without explicit agent fairness | Completed acceptance-cycle searches; loop witnesses and fairness premise explained |
| S5 | Mirror v1 FIX-1..4 and compare versions | Actual matrix runs, explicit rejection handling, non-divisible timing checks; no copied verdicts |
| S6 | Final runner, CSV, raw evidence, replay, README and findings | Reproduction command works; every result has provenance; diff stays SPIN-only; no automatic Git actions |

Proposed deliverables (create only as their stages are implemented):

```text
verification/spin/
  AGENTS.md
  node-spin.md
  README.md
  MODEL_MAPPING.md
  FINDINGS.md
  models/controller.pml
  models/properties.pml
  scripts/run_spin.py
  scripts/replay_trail.py
  results/results.csv
  results/raw/
```

## Commands and evidence rules

Run project commands from repository root. The Python runner should use the
standard library where practical. Isolate each verifier build so claims,
versions, trails and pan files cannot overwrite one another.

Tool inspection: `spin -V`, `spin -?`, `cc --version`, `python3 --version`.
Use the installed CLI help to confirm flags before finalizing the runner.
Typical generation/verification sequence, executed in an isolated build directory:

```sh
spin -a model.pml
cc -O2 -o pan pan.c
./pan -m100000
./pan -a -m100000
spin -t -p -g model.pml
```

These are templates: choose a single property explicitly, preserve model
preprocessor settings during replay, and run safety versus acceptance checks
with appropriate compilation flags. Inspect `./pan -?` for the built verifier.
Only a completed exhaustive search supports PASS. Simulation, bitstate sampling,
depth truncation or incomplete exploration does not. Depth/memory exhaustion is
UNKNOWN; timeout is TIMEOUT; invocation/build/parser failures are ERROR.
A real assertion or acceptance-cycle witness is FAIL, subject to model review.

Runner CLI (implemented in S2; --all currently covers 20 v0 S2 cases):

```sh
python3 verification/spin/scripts/run_spin.py --list
python3 verification/spin/scripts/run_spin.py --all
```

Current gate: list exposes the implemented matrix; all executes its cases
independently and records actual metrics. Future stages must extend the matrix
explicitly rather than implying coverage of unimplemented properties or v1.

Exact shared CSV header:

```text
tool,property,version,config,bound,result,ce_length,time_s,memory_mb,notes
```

- Use only PASS, FAIL, UNKNOWN, TIMEOUT, ERROR for SPIN results.
- bound is `depth=<depth reached>`, not a guessed decision or second bound.
- ce_length counts decision steps; blank for PASS. For cyclic witnesses state
  how prefix and cycle decisions are counted. Include a partially executed
  decision if the violation happens inside it, and document that convention.
- Record actual wall time, reported memory with units, tool/compiler versions,
  commands, limits, fidelity, assumptions, claim and trail paths. Missing metrics
  stay empty with an explanation; never fabricate values.
- Store useful raw text under results/raw/*.txt. Root .gitignore ignores *.log,
  pan, pan.*, *.trail and _spin_nvr.tmp. Retain readable trace evidence and a
  reproduction recipe; do not force-add generated binaries or large logs.
- FAIL witnesses should show actions, signal states, simulated times, controller
  age, observed age, failing property and source interpretation.
- Replay finite v0 witnesses where feasible with:
  `python verification/common/replay_in_sumo.py --actions <sequence> --property <ID>`.
  Its exit code 0 means a violation reproduced. It imports current src/; it
  does not provide a v1 selector. Do not apply the patch to the worktree for
  replay; use an isolated temporary source copy if v1 replay is needed.
- Finite SUMO replay validates a witness, not an infinite L2 proof. Record
  unavailable dependencies and abstraction/replay mismatches honestly.

## Tooling baseline and dependency policy

Observed before installation: macOS arm64; Apple Clang 21.0.0; Homebrew 5.0.15;
Python 3.13.7 at /opt/homebrew/bin/python3. SPIN and SUMO were absent from PATH.
Current Python could import numpy but not traci, sumolib, sumo or gymnasium;
there was no repository .venv and no python3.12 on PATH.

SPIN installation was authorized by the user: `brew install spin`.
Record its final outcome and smoke results below after execution.
Clang and existing Python suffice for core Promela verification and runner work.
Do not install ESBMC, PyTorch or training packages for SPIN.

SUMO dependencies are needed at the conformance/replay stage. Install them when
that stage requires them, using a project virtual environment; match the shared
reference environment (Python 3.12 and eclipse-sumo/traci/sumolib 1.28.0) where
feasible. Keep environment files/generated outputs out of version control.

## Current progress and next action

- Reconnaissance: complete for the initial baseline.
- Durable context and SPIN scope instructions: created in this change.
- S0 tool installation/smoke: see execution record below.
- S1: v0 control flow, source mapping and finite reference conformance check
  implemented. Real SUMO fidelity remains unconfirmed.
- S2: complete for v0 S1/T1/T2/G1/C1 across four scenarios: 20 executed
  checks, 14 PASS and 6 FAIL, with all six finite failures reference-reproduced.
  Results are model-level; real SUMO validation and human review remain pending.
- S3: complete for v0 G2/L1: eight executed FAIL cases, all reference-reproduced.
  Boundary tests and S2 regression passed. Current matrix: 28 cases, 14 PASS/14 FAIL.
- S4-S6: pending (documentation work ongoing). Next is S4, L2/fairness.
- The user requested one stage at a time; report S3 completion before proceeding.
  Keep README meanings/status current for teammates and append data to report.md.

## Execution record

Update this section with actual commands, versions and results after each stage.

### 2026-11-06: context and toolchain bootstrap

- Created this context and scoped AGENTS.md; no model or property result created.
- Executed `brew install spin` with user-authorized escalation. Homebrew's overall
  command returned exit 1 with an API download/update warning and automatic
  maintenance output. The package itself is installed: `brew list --versions spin`
  reports `spin 6.5.2`; `spin -V` reports
  `Spin Version 6.5.2 -- 6 December 2019`.
- Confirmed the functional toolchain in temporary directories using Python
  subprocess calls (no generated verifier files left in the repository):
  - `init { assert(1) }`: `spin -a model.pml`,
    `cc -O2 -o pan pan.c`, `./pan -m10000`: errors 0, depth 2,
    completed exhaustive search.
  - `init { assert(0) }`: same commands: assertion violation, errors 1,
    depth 0; `spin -t -p -g model.pml` successfully replayed the witness.
  - A Boolean toggling loop with `ltl recurrence { []<> false }`:
    `./pan -a -m10000` detected an acceptance cycle, errors 1, depth 5;
    replay displayed START OF CYCLE.
  - The first liveness smoke used an unconditional skip loop and was rejected
    by pan as an unconditional self-loop. Replacing it with the Boolean toggle
    yielded the valid cycle-detection smoke above. This was a smoke-model issue,
    not a project finding.
- Important runner lesson: both a successful check and a property violation can
  return pan exit code 0. Parse errors/search diagnostics and claim results;
  exit status alone cannot classify PASS versus FAIL. A search stopping on a
  concrete counterexample can legitimately report Search not completed.
- On zsh, quote question-mark help arguments: `spin '-?'` and `./pan '-?'`.
- These are toolchain smoke outcomes only, not S1/T1/T2/G1/G2/L1/L2/C1 results.
- S0: installation and safety/failure/liveness smoke gates completed. Per-model
  help/claim configuration, persistent evidence capture and fidelity validation
  remain work for the runner/model stages. SUMO dependencies deferred to replay.

### Root-file audit and implementation authorization

The user asked to audit all eight files shown in the root screenshot, supplement
this context where needed, and begin the project. All eight have now been read:
AGENTS.md, CLAUDE.md, codex.md, README.md, baseline_comparison.py,
evaluation.py, multi_baseline_eval.py and build_network.sh.

- Root CLAUDE.md only delegates to verification/CLAUDE.md. No additional SPIN
  restrictions were found in the evaluation or plotting scripts.
- Root README claims min/max green constraints are applied. Source v0 does not
  enforce max_green; preserve the defect, and use actual code plus the shared
  verification catalogue rather than this descriptive claim as model semantics.
- build_network.sh overwrites networks/single_intersection.net.xml through
  netconvert with guessed traffic lights. Do not run it for the verification
  setup: use the committed network as the fixed baseline. Regeneration can alter
  phase strings/timings and invalidate the shared contract. The README's network
  build and training steps are original-app setup examples, not SPIN prerequisites.
- baseline_comparison.py increments its fixed-cycle phase_timer by one per
  decision while labeling cycle_time as seconds. Do not infer physical timing or
  formal verification properties from its baseline labels/results.
- multi_baseline_eval.py uses info['step'] seconds for its fixed cycle and all
  controllers ultimately call env.step(action). Policies are covered by the
  nondeterministic legal-action abstraction; their statistical performance does
  not prove the shared properties. Virtual pedestrians remain outside this
  control-logic verification scope.
- Root README's broad dependency requirements belong to training/evaluation.
  SPIN does not require trained checkpoints, torch, GPU, or performance plots.
- The earlier immediate scope of context/tooling is now extended: begin model
  implementation incrementally, maintaining the SPIN-only write boundary.

S1 implementation started: models/controller.pml, MODEL_MAPPING.md and
scripts/check_traces.py. The model currently covers v0 control flow and finite
trace comparison only. Shared monitors, v1 and exhaustive results are not yet
implemented. See the next execution record for actual validation results.

### 2026-11-06: initial v0 implementation validation

- Command: `python3 verification/spin/scripts/check_traces.py --output
  verification/spin/results/raw/s1-trace-comparison.json` (one shell line).
  Actual result: MATCH, 96 finite cases and 18,898 observation records.
  Includes static on/off, delta 1/5/7, yellow 0/3, prolonged holds, alternating
  actions, takeover around static yellow/EW, invalid actions and 24 seeded
  random sequences. Evidence includes actions, reference/model/script hashes,
  tool version and record counts. References were read, never modified.
- Non-TRACE build smoke, in temporary directories, for static=0 and static=1:
  `spin -DSTATIC_PROGRAM=<0|1> -DANY_ACTION -a controller.pml`;
  `cc -O2 -o pan pan.c`; `./pan -m100000 -w18`.
  Both completed with errors 0: static=0 reached depth 2068 (5026 stored
  states); static=1 reached depth 2669 (90183 stored states).
  These searches check build viability, supported-domain assertions and invalid
  end states only. No shared property monitor or LTL claim is implemented, so
  these outcomes do not prove any of S1/T1/T2/G1/G2/L1/L2/C1.
- No real SUMO run, shared results CSV or v1 implementation yet.
- Only files under verification/spin/ were created/updated. No Git write
  operations, network regeneration or source/controller changes performed.

### 2026-11-06: proposal alignment review

- Read and visually inspected both pages of the supplied project proposal.
- Added the proposal commitments/reporting checklist above, including the
  explicit human review obligation, supplementary-check distinction, joint
  comparison requirements and fallback limitations.
- No conflicting SPIN scope or additional numeric requirements found.
- This change updates context only; model code, prior run evidence, shared
  contracts, ESBMC and source files are unchanged. No new verification run.

### 2026-11-06: SPIN README entry point

- Added verification/spin/README.md as the human-facing SPIN entry point.
- It documents actual status, existing files, prerequisites, executable trace
  commands, expected output, model limitations, planned property coverage,
  S0-S6 gates and evidence/collaboration rules.
- Keep README status and commands synchronized with implementation. This context
  retains detailed AI handoff/history; README is not a substitute for it.
- Documentation-only change; no new project verification claims or model changes.

### 2026-11-06: S2 completed (v0 safety and transition baseline)

- Added models/properties.pml with S1/T1/T2/G1/C1 checks. T2 combines
  duration/next-direction assertions with the sole yellow_completion LTL claim.
  One property is compiled per run; T2 uses acceptance-cycle search, others
  safety search. C1 is checked after complete decisions, provisionally pending D4.
- Added run_spin.py, replay_trail.py and test_verification.py; updated the trace
  checker to copy/hash properties.pml and retain unchanged reference comparison.
- Actual commands and results:
  - `python3 verification/spin/scripts/check_traces.py --output
    verification/spin/results/raw/s1-trace-comparison.json` (one shell line):
    MATCH, 96 cases, 18,898 observation records.
  - `python3 verification/spin/scripts/run_spin.py --all`: completed 20 cases,
    14 PASS and 6 FAIL; no UNKNOWN/TIMEOUT/ERROR. Final matrix is in FINDINGS.md
    and results/results.csv with exact shared columns. Raw runs are timestamped.
  - `PYTHONDONTWRITEBYTECODE=1 python3 verification/spin/scripts/test_verification.py`:
    10 test methods passed, covering synthetic monitor faults and classification.
    Actual depth truncation is UNKNOWN, not PASS; infinite yellow is detected
    by an acceptance cycle.
  - Independent replay_trail.py invocation against the stored T1/y0 evidence
    reproduced its assertion witness with matching model hashes. All six FAIL
    trails were also replayed by the runner and independently reference-checked.
- FAIL cases: T1/y0, T2/any, T2/L1, G1/L1, C1/any, C1/L1. Reference failure
  times were 90, 189, 93, 145, 181, 45 seconds respectively. DFS witnesses
  contain 17, 35, 17, 28, 33, 7 started decisions; they are not claimed shortest.
- T2/y0 PASS is conditionally vacuous (no observed yellow); T1/y0 detects the
  missing interval. Never report it as proof of zero-yellow safety.
- S1 network preflight validates the fixed codebook and protected conflicts,
  explicitly assuming link i maps to junction request i as in the shared checker.
- CSV time_s is verifier wall time; generation/compile/replay timings are in
  metadata. Prior raw runs are retained when current CSV entries are replaced.
- Updated README, MODEL_MAPPING and FINDINGS. No source, ESBMC, common script,
  shared-contract, network or Git state mutations. Real SUMO and human review
  remain pending. Stop at this stage and report; next stage is S3 (G2/L1).

### 2026-11-06: persistent report record and S2 checkpoint

- User requires every stage's data and both favorable/unfavorable outcomes to
  be preserved for final report writing. Added report.md as the chronological
  experimental record; future stage work must append commands, actual metrics,
  failed/corrected attempts, interpretations, limitations and evidence links.
- Preserve prior entries; append corrections/superseding runs. Keep raw outputs
  and freeze stage CSVs because results.csv is an upserted current view.
- Created results/snapshots/s2-v0-results.csv from the actual current CSV.
  report.md preserves both existing 20-case sweeps (40 recorded searches),
  with all metrics/metadata links and six selected witness explanations. These
  are 20 distinct cases, not 40 distinct configurations.
- Historical S0/S1 attempts without archived raw data are labeled reconstructed
  from context; missing metrics remain not recorded. No new verification run.
- Current checkpoint is v0 through S2: initial model and tooling plus five
  properties across four scenarios, 14 PASS/6 FAIL. S3 has not started; real
  SUMO, human review, L2 and v1 remain pending.
- Suggested commit: spin: implement v0 SPIN verification through S2. User will
  commit/push via GitHub Desktop; do not perform Git writes automatically.

### 2026-11-06: final-report evidence priorities confirmed

- User confirmed that the modeling/verification narrative should be documented
  throughout implementation. Follow the Report evidence checklist in report.md
  at each subsequent stage, not only the numeric result-table requirements.
- Retain source-to-Promela rationale, time/state abstraction and preservation
  arguments, exact assertions/LTL and vacuity checks, search assumptions and
  completeness, state/transition/resource metrics, raw counterexamples and
  source causes, failed/corrected attempts, repair comparisons and limitations.
- Prepare an end-to-end case study with linked source/model/property/witness/
  repair evidence. G1/static-program is a candidate; real SUMO and v1 validation
  are pending and must not be inferred from current S2 findings.
- These are user-confirmed report priorities, not an instructor rubric. No new
  verification run; checkpoint remains v0 through S2, next stage S3.

### 2026-11-06: S3 started and teammate-facing progress policy

- User authorized the next stage and requested README stage meanings and live
  progress for teammates. README now defines S0-S6, deliverables/completion gates
  and status; update it at stage start, validation milestones and completion.
- S3 now in progress. Add G2 and L1, boundary tests, actual searches, witness
  checks, stage CSV snapshot and report data; do not advance to S4 this turn.
- G2 will align with the existing shared harness: per-second observed green
  <= max_green AND controller phase_duration <= max_green at decision boundaries.
  Record which component fails. The static-program counter violation alone
  does not establish that the displayed green was overlong.
- L1 measures both directions' waits, including warmup/yellow, resetting only
  on that direction's green; limit is max_green + 2*configured yellow_time.
  y0 therefore has a 60-second wait limit, not the default 66.

### 2026-11-06: S3 completed

- Added G2 displayed green <=60 per second AND controller age <=60 after decisions,
  matching the shared harness. Added L1 NS/EW counters with configured wait limit.
  Recorded which component fails; monitors do not change v0 control transitions.
- G2 monitors saturate at 61; L1 waits at limit+1 (67 default, 61 in y0).
  TIMING replay events store post-update counter values before failure assertions.
- Added --stage S2/S3 selection; --all now runs 28 v0 cases. New raw runs retain
  model copies and reference hashes. replay_trail.py resolves matching run-local
  or frozen stage source so earlier witnesses remain reproducible after edits.
- Executed tests (14 methods, 32 synthetic searches), finite trace comparison
  (96 cases, 18,898 records), S3 matrix (eight FAIL) and S2 regression (14 PASS,
  six FAIL). All 14 current finite failures are reference-reproduced. No project
  UNKNOWN/TIMEOUT/ERROR. Full logs and metrics are linked in report.md.
- G2 default/y0/any: observed green61, controller50, t=60, decision11.
  G2/static: controller65, observed29, t=75, decision13. Do not describe that
  static counter failure as an overlong displayed-green counterexample.
- L1 default/any: EWwait67 at t=66/decision12; y0 wait61 at t=60/decision11;
  static wait67 at t=254/decision48. Times use pre-step sample convention except
  the G2 controller boundary. Witnesses are not claimed shortest.
- Frozen S3 and through-S3 CSV snapshots; preserved original S2 model snapshot.
  Updated README stage guide/status, MODEL_MAPPING, FINDINGS and report material.
- No real SUMO or human review completed. No source/ESBMC/shared/network/Git
  writes. Stop at S3 and report; next stage S4 is not started.

### S3 closeout formatting correction

- git diff --check flagged CRLF line endings from Python csv.DictWriter as
  trailing whitespace in modified CSV rows. Saved the diagnostic in the S3
  validation directory, changed future writer output to LF, and normalized
  current/new S3 CSV files without changing parsed rows or measured metrics.
  Original S2 snapshots were left unchanged.
- Archived the measurement runner as results/snapshots/s3-runner.py before this
  serializer-only correction. Raw metadata hashes describe that measured runner,
  not a claim that its hash equals the final formatting-corrected script.
- Repository HEAD observed at closeout is 7ccc6ea (user's S2 commit); no Git
  commit/push/merge was performed by the assistant.
