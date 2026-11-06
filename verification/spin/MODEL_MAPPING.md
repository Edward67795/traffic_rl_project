# v0 model mapping (S1-S2 stages)

The current model implements v0 control flow and selected shared checks:
S1, T1, T2, G1 and C1. The S2 runner emits a verification results CSV.
v1, G2, L1 and L2 remain pending.

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
checks. Counters not used by the selected property remain unchanged. No wait
counters or G2 monitor exist yet.

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
