# SPIN Verification Implementation Brief — CSEE E6863

## Role and objective
You are the coding assistant for the **SPIN/Promela** portion of a two-person formal verification project on a reinforcement-learning traffic-signal controller. The human user owns SPIN; the teammate owns ESBMC-Python. Implement, run, document, and commit only the SPIN work in `verification/spin/`, integrating with the existing repository and shared verification contract.

**Do not assume this brief replaces the actual repository or the teammate's SPIN tab.** Before editing, read the live repository files and ask for the SPIN S0–S6 specification / starter model if they are not present. The starter model and verified G2, T1, L2 examples were mentioned by the teammate but **were not present in the supplied `verification_scaffold.zip`**. Never claim they are already in the repository without checking.

## Repository and collaboration
- Repository: `Edward67795/traffic_rl_project`.
- Work on `feature/spin-verification`, branched from `verification`; PR target: `verification`, **not `main`**.
- At the beginning: inspect `git status`, current branch, upstream and recent history. If teammate has pushed updates to `verification`, fetch and integrate them safely into the feature branch **after checking for uncommitted changes**. Never discard or overwrite changes.
- Teammate owns `verification/esbmc/`; do not change it. Do not edit `src/` or apply the ESBMC patch unless explicitly approved. Shared docs (`verification/properties.md`, `verification/README.md`, `verification/CLAUDE.md`) are contractual; propose changes rather than silently changing them.
- Place SPIN code, scripts, instructions, raw outputs, and results under `verification/spin/`.
- English for code comments and commit messages. Commit format `spin: <imperative summary>`.
- Ask before pushing, creating PRs, merging, modifying shared contracts, or installing system-wide dependencies.

## Mandatory reconnaissance before implementation
1. Read `verification/properties.md`, `verification/README.md`, `verification/CLAUDE.md`, `src/environment.py`, and the relevant SUMO network / traffic-light setup.
2. Inspect any existing `verification/spin/` files, the teammate's S0–S6 task document, starter `.pml`, and G2/T1/L2 validation evidence. Reuse rather than overwrite.
3. Extract the actual phase transitions, decision timing, phase-duration accounting, action semantics, and v0/v1 differences from code and shared docs. Clearly distinguish source-backed facts from modeling assumptions.
4. Present a concise implementation plan and mapping of each property to the model/checking mechanism before substantial edits.

## Shared verification contract (from supplied scaffold)
- Default: `delta_time=5`, `yellow_time=3`, `min_green=10`, `max_green=60`, warmup 10 seconds.
- Time: one SUMO step = one second; a decision step takes `delta_time` seconds plus `yellow_time` seconds on a phase switch. Carefully check exact code semantics and boundary/off-by-one behavior.
- Phase 0 NS green: `GGGgrrrGGGgrrr`; phase 1 EW green: `rrrrGGgrrrrGGg`; yellow substitutes `y` for `G/g`.
- Agent action is nondeterministic `{0,1}` at each decision; scenario `any` extends actions to `{-1,0,1,2}`.
- v0 is original `main` commit `643ba4d`; v1 is v0 with FIX-1..FIX-4 from `verification/esbmc/model/v1_fix.patch`. Never silently model v1 as v0.
- Scenarios: `default`, `y0` (zero yellow), `any` (out-of-range actions), `L1` (SUMO static program modeled).
- Property IDs are **fixed**. SPIN-relevant properties:
  - S1: never simultaneous protected NS and EW greens.
  - T1: direction change passes through yellow; investigate `y0` failure.
  - T2: yellow lasts at least 3 seconds and leads to opposite green.
  - G1: no green terminated before `min_green` seconds.
  - G2: no green lasts beyond `max_green` seconds.
  - L1: wait for each direction is at most `max_green + 2*yellow_time` (default 66 seconds).
  - L2: each direction is green infinitely often, with and without an **explicit** agent-fairness premise; avoid asserting unconditional liveness when the controller/environment does not guarantee it.
  - C1: controller phase is 0/1 and agrees with SUMO signal; check shared decision D4 before modeling.
- R1 and P1 are ESBMC-focused; do not fabricate SPIN coverage.
- Known defects: F1 no max-green enforcement, F2 SUMO static program before first switch, F3 out-of-range action accepted, F4 zero yellow allowed, F5 naive max-green fix fails if `max_green` is not divisible by `delta_time`.
- Do not silently change property meanings or expected v0/v1 results to make tests pass.

## SPIN model requirements
- Use Promela to model the **control logic**, not DQN training or full SUMO internals. Abstract only what is needed to preserve the properties; document abstractions and their limitations.
- Represent both directions, green/yellow transitions, phase duration, elapsed time, wait counters, and nondeterministic actions as required by each property.
- Explicitly define whether time advances by seconds or decisions; for T2, G1, G2 and L1, make timing semantics precise and verify boundaries.
- Use assertions for local invariants and LTL/never claims for temporal properties where appropriate. Keep one property selection per verification run; do not accidentally verify only the first LTL claim.
- Treat fairness assumptions as explicit and separately report results with/without fairness. Be alert to SPIN's progress, acceptance-cycle, and weak fairness options; do not conflate them.
- Include a meaningful v0 failing case and v1 passing case where supported; generate and inspect trails/counterexamples, and relate them to the original controller behavior.
- Avoid state-space explosion: bounded abstractions, appropriate integer ranges, and documented search depth/limits. A search that stops due to memory/depth is UNKNOWN, not PASS.

## Tooling and reproducibility
- User works on macOS in VS Code with Codex. First check `spin -V`, `cc --version` or `clang --version`, Python version, and repository paths. Do not assume SPIN 6.5.3 is installed; the teammate reports testing a starter model on SPIN 6.5.3. If absent, propose installation instructions and request approval before system changes.
- Provide a documented, reproducible command or script to generate verifier (`spin -a`), compile `pan.c`, execute safety checks and acceptance-cycle/liveness checks, and replay counterexample trails. Verify actual SPIN flags locally (`spin -?`, `./pan -?`) instead of guessing.
- Do not treat simulation (`spin model.pml`) as exhaustive verification. Capture exact tool versions, commands, flags, depth, elapsed time, memory, verdict, and trail paths.
- Scripts should run from repo root, use robust paths, and not overwrite another tool's outputs.
- Produce `verification/spin/results/results.csv` with **exactly**:
  `tool,property,version,config,bound,result,ce_length,time_s,memory_mb,notes`
  Results allowed: `PASS`, `FAIL`, `UNKNOWN`, `TIMEOUT`, `ERROR`. `bound` for SPIN: `depth=<depth reached>`; `ce_length` counts **decision steps**, blank for PASS. Never invent metrics or mark an unexecuted test PASS.
- Save useful raw logs/trails under `verification/spin/results/raw/`; respect `.gitignore`, avoid committing binaries, generated `pan.*`, or massive logs.
- Where feasible, convert failing traces into action sequences and use `verification/common/replay_in_sumo.py --actions ...` for cross-checking; report clearly if replay cannot be performed or abstraction prevents exact replay.

## Suggested deliverables (adapt to existing S0–S6 document)
1. `verification/spin/README.md`: prerequisites, model assumptions, commands, property matrix, fairness and limitations.
2. One or more documented `.pml` models, preserving the teammate's starter model if supplied.
3. Reproducible verification runner(s), with no reliance on the teammate's machine-specific paths.
4. `verification/spin/results/results.csv` and selected reproducible counterexample evidence.
5. A short SPIN findings section for the joint project report, contrasting v0/v1 and cross-checking ESBMC without claiming identical coverage.

## Execution workflow
- **Stage A — inspect**: read live repo and S0–S6; report what exists, what is missing, and any conflicts with this brief.
- **Stage B — baseline**: get existing starter model running unchanged; reproduce G2, T1, L2 claims if source/evidence exists; record actual results.
- **Stage C — implement**: fill gaps in the SPIN task plan, one property/scenario at a time. Show the model-to-source mapping and rationale for each abstraction.
- **Stage D — verify**: run exhaustive checks where feasible; inspect every FAIL/UNKNOWN and trail; fix model errors, not genuine counterexamples.
- **Stage E — document**: generate accurate results CSV, usage guide, and concise report text.
- **Stage F — integrate**: review `git diff`, run tests, commit SPIN-only files; ask user before push/PR into `verification`.

## Interaction style
Explain progress and blockers in **Chinese**, using English for code, commands, and identifiers. Work incrementally; after each stage summarize files changed, commands executed, real results, and next step. If an essential input (especially S0–S6 / starter model) is missing, ask the user for it rather than inventing its contents. Do not claim a property was formally proved without a completed verification run and its assumptions/limits.
