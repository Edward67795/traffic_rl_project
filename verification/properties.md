# Shared property catalogue

Both tools use these IDs, parameters and result format. To change anything here, comment in the
shared status doc first (tab "总览与约定", section 共享约定).

## Parameters and versions

| Item | Value |
|---|---|
| Default parameters | `delta_time=5`, `yellow_time=3`, `min_green=10`, `max_green=60`, warmup 10 s |
| Time | 1 SUMO step = 1 s; 1 decision step = `delta_time` s, plus `yellow_time` s when the phase switches |
| Signal states | phase 0 (NS green) `GGGgrrrGGGgrrr`; phase 1 (EW green) `rrrrGGgrrrrGGg`; yellow = G/g replaced by y |
| Agent | any action in {0, 1} at every decision step (nondeterministic); scenario `any` widens this to {-1, ..., 2} |
| v0 | original code, branch `main`, commit `643ba4d` |
| v1 | v0 + FIX-1 ... FIX-4 (`verification/esbmc/model/v1_fix.patch`) |
| Scenarios | `default`, `y0` (`yellow_time=0`), `any` (out-of-range actions), `L1` (SUMO static program modelled) |

## Properties

| ID | Property | ESBMC | SPIN (suggested) | v0 | v1 |
|---|---|---|---|---|---|
| S1 | No two conflicting links are protected green (G) at the same time; NS and EW are never green together | stub checks the displayed state every second | `[] !(ns_green && ew_green)` | PASS | PASS |
| T1 | A change of green direction always passes through an all-yellow interval | stub compares consecutive seconds | NS green never directly followed by EW green | PASS; FAIL with `yellow_time=0` | PASS |
| T2 | Yellow lasts at least 3 s (the default `yellow_time`) and is followed by the other direction's green | stub counts yellow seconds (at least 3) and checks the next green | `[] (ns_yellow -> (ns_yellow U ew_green))` | FAIL with out-of-range actions or the static program | PASS |
| G1 | A green phase is never cut before `min_green` s | stub records when each green started | `assert(pd >= MIN_GREEN)` at a switch | PASS; FAIL with the static program | PASS |
| G2 | No green phase lasts longer than `max_green` s | harness asserts `phase_duration <= max_green`; stub measures the displayed green | `[] (pd <= MAX_GREEN)` | FAIL (13 steps with the static program) | PASS |
| L1 | No direction waits more than `max_green + 2*yellow_time` s (66 s) for green | stub wait counters | wait counter + assert | FAIL | PASS |
| L2 | Each direction is green infinitely often | not checkable by BMC (unbounded liveness) | `[]<> ns_green && []<> ew_green`, with and without an agent-fairness premise | FAIL without the premise | PASS |
| C1 | The controller's `current_phase` is 0 or 1 and matches the signal SUMO shows | harness assert | depends on decision D4 | FAIL with out-of-range actions or the static program | PASS |
| R1 | No runtime errors (division by zero, index errors) for any configuration in range | ESBMC built-in checks, nondet parameters | n/a | FAIL (`delta_time=0` or `max_green=0`) | PASS |
| P1 | Every decision step advances simulated time by at least 1 s | harness assert | n/a | FAIL (`delta_time<=0`) | PASS |

## Results format

Each tool writes `verification/<tool>/results/results.csv` with exactly these columns:

```
tool,property,version,config,bound,result,ce_length,time_s,memory_mb,notes
```

- `result` is one of PASS, FAIL, UNKNOWN, TIMEOUT, ERROR (ESBMC also uses COVERED for cover checks).
- `ce_length` counts decision steps; empty for PASS.
- `bound`: ESBMC writes `K=<steps>`; SPIN writes `depth=<depth reached>`.
- Counterexamples are replayed with `verification/common/replay_in_sumo.py --actions <a1,a2,...>`.
