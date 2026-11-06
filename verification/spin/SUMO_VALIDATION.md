# Real SUMO validation (S6)

This dataset directly executes original src/environment.py on SUMO 1.28.0.
v1 uses a temporary full-source copy with the unchanged shared patch; the
worktree controller and ESBMC files remain unchanged. Live monitors are implemented
independently in scripts/validate_sumo.py and do not import the TraCI stub/core.

## Executed checks

-38 source/Promela conformance cases matched, totaling7,205 projected records.
  They cover both versions, both traffic route files, static boundaries,
  takeover, illegal input, zero yellow, selected timing profiles and seeded
  policies. Some v1 inputs reject early; a MATCH is not a normal-operation PASS.
- One deliberate v0/L0 negative control mismatched as expected. L0 is a simplified
  environment, not a conservative model of the autonomous static behavior.
-21 original finite assertion witnesses were replayed:12 reproduce the target
  property and9 do not within their original finite action prefix. The detailed
  original formal outcomes remain unchanged; these are separate replay outcomes.
- Three additional short real-source sequences demonstrate T1/y0, overlong green
  and bounded-wait failures despite some original L0 prefixes not reproducing.
- A finite repeat of the compact L2 input pattern shows NS-only/yellow behavior;
  it does not prove an infinite real-SUMO execution.

The direct source/model projection compares sampled signal, controller phase,
projected controller age, controller time and online status at pre-second and
post-decision points. SUMO program/phase/next-switch metadata are also saved,
but abstract frozen static-cursor values are not asserted as source fields.

Actual v0 pre-step signal changes: t0 NS, t43 NS-yellow, t46 EW, t88 EW-yellow,
t91 NS. This confirms43 initial pre-step observations and the later42/3/42/3
sequence for this SUMO build and observation convention. It is not a general
claim that every sampling convention measures the initial XML42-s phase as43 s.

## Original finite-witness replay outcomes

A reproduced target need not occur at the model's first-failure time or by the
same intermediate trace. Some L0 source runs already diverge under the static
program. C1/any, for example, has early signal disagreement and later illegal
phase; both events are retained. No finite prefix is called an infinite proof.

| Case | Fidelity | Target reproduced | First live target time_s | Original reference time_s | Evidence |
|---|---|---|---|---|---|
| G2-v0-default-dt7 | L0 | False | - | 60 | [live record](results/raw/s6-sumo-full/replay-G2-v0-default-dt7.json) |
| G2-v0-default-max61 | L0 | False | - | 61 | [live record](results/raw/s6-sumo-full/replay-G2-v0-default-max61.json) |
| G2-v0-default-dt3max16 | L0 | True | 16.0 | 16 | [live record](results/raw/s6-sumo-full/replay-G2-v0-default-dt3max16.json) |
| G2-v0-default-min0dt7 | L0 | True | 11.0 | 11 | [live record](results/raw/s6-sumo-full/replay-G2-v0-default-min0dt7.json) |
| G2-v0-default-min12dt1 | L0 | True | 16.0 | 16 | [live record](results/raw/s6-sumo-full/replay-G2-v0-default-min12dt1.json) |
| G2-v0-default-delta_gt_max | L0 | True | 11.0 | 11 | [live record](results/raw/s6-sumo-full/replay-G2-v0-default-delta_gt_max.json) |
| G2-v1-default-delta_gt_max | L0 | True | 24.0 | 24 | [live record](results/raw/s6-sumo-full/replay-G2-v1-default-delta_gt_max.json) |
| T1-v0-y0 | L0 | False | - | 90 | [live record](results/raw/s6-sumo-full/replay-T1-v0-y0.json) |
| T2-v0-any | L0 | True | 93.0 | 189 | [live record](results/raw/s6-sumo-full/replay-T2-v0-any.json) |
| T2-v0-L1 | L1 | True | 93.0 | 93 | [live record](results/raw/s6-sumo-full/replay-T2-v0-L1.json) |
| G1-v0-L1 | L1 | True | 145.0 | 145 | [live record](results/raw/s6-sumo-full/replay-G1-v0-L1.json) |
| C1-v0-any | L0 | True | 45.0 | 181 | [live record](results/raw/s6-sumo-full/replay-C1-v0-any.json) |
| C1-v0-L1 | L1 | True | 45.0 | 45 | [live record](results/raw/s6-sumo-full/replay-C1-v0-L1.json) |
| G2-v0-default | L0 | False | - | 60 | [live record](results/raw/s6-sumo-full/replay-G2-v0-default.json) |
| G2-v0-y0 | L0 | False | - | 60 | [live record](results/raw/s6-sumo-full/replay-G2-v0-y0.json) |
| G2-v0-any | L0 | False | - | 60 | [live record](results/raw/s6-sumo-full/replay-G2-v0-any.json) |
| G2-v0-L1 | L1 | True | 75.0 | 75 | [live record](results/raw/s6-sumo-full/replay-G2-v0-L1.json) |
| L1-v0-default | L0 | False | - | 66 | [live record](results/raw/s6-sumo-full/replay-L1-v0-default.json) |
| L1-v0-y0 | L0 | False | - | 60 | [live record](results/raw/s6-sumo-full/replay-L1-v0-y0.json) |
| L1-v0-any | L0 | False | - | 66 | [live record](results/raw/s6-sumo-full/replay-L1-v0-any.json) |
| L1-v0-L1 | L1 | True | 254.0 | 254 | [live record](results/raw/s6-sumo-full/replay-L1-v0-L1.json) |

All 9 non-reproduced original prefixes are L0 cases. The static program changes
the actual displayed phase before the model's indefinitely held initial green
would violate its duration/wait bound; the long DFS y0 prefix also reaches a
static yellow before its switch. These outcomes expose environment fidelity,
not a reason to delete model FAILs or relabel them source PASSs. Source-backed
conclusions should use L1 and/or actual replay evidence. L0 also omits autonomous
transitions, so it is not automatically a safe overapproximation for PASS claims.

## Short source-backed examples

| Example | Actions | Independent live finding |
|---|---|---|
| Missing yellow | [0,0,1], yellow0 | T1 direct direction change at pre-step t20 |
| Overlong green | [0,0,1] + twelve1 inputs | Displayed green exceeds60 at t83; controller-age check later fails at t88 |
| Bounded waiting | [0,0,1] + thirteen1 inputs | NS wait67>66 at t86 |
| Residual v1 parameter defect | One input0, delta12/min0/max11/yellow3 | Observed EW green12>11 at t24, controller age11; boundary counter12 fails at t25 |

The times label observation callbacks before a simulated step, or completed
decision boundaries for controller checks. They must be interpreted with the
recorded sampling convention. A failure at the61st observed interval does not
mean the simulation clock has already returned from61 completed intervals.

## Reproduction

Tested runtime: Python 3.13.7, eclipse-sumo/traci/sumolib1.28.0,
gymnasium 1.4.0, NumPy 2.5.4. Exact dependencies: requirements-sumo.txt.
Python 3.12 Homebrew download repeatedly stalled/restarted and was cancelled
(exit130); no Python 3.12 run is claimed. This runtime difference from the
teammate's suggested Python 3.12 is explicit; SUMO itself matches the pinned1.28.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r verification/spin/requirements-sumo.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python verification/spin/scripts/validate_sumo.py \
  --output verification/spin/results/raw/s6-sumo-rerun
```

Use a new output directory. The script sets SUMO_HOME internally, needs local
TraCI sockets and records source/patch/network digests, exact package versions,
actions, traces, first failures, patch logs and rejected inputs. It never applies
the patch to src/. Do not run build_network.sh.

Evidence: [full summary](results/raw/s6-sumo-full/summary.json),
[smoke](results/raw/s6-sumo-smoke/summary.json), [replay CSV](results/sumo-replay.csv).
A separate official-library [network audit](results/raw/s6-network-audit.json)
confirms all 14 TLS indices match request indices and all four phases have zero
protected G/G conflicts. This strengthens the fixed-network mapping assumption
used by the formal S1 preflight; it does not generalize to arbitrary networks.

## Remaining limits

Finite source conformance supports the abstraction but is not an exhaustive
proof of all Python/SUMO behavior. Human model review remains pending. Full DQN,
vehicle collision freedom, network regeneration and arbitrary parameter domains
are outside the checked claim. L2 has separate formal acceptance-cycle evidence;
real finite samples cannot establish it by themselves. The residual v1 admission
bug is preserved and requires a jointly reviewed fix if the team chooses to repair it.
