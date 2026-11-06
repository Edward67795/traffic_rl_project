# How env_core_v0.py was extracted from src/environment.py

Source: `src/environment.py` at commit `643ba4d` (branch `main`).
Signal states: `networks/single_intersection.net.xml`, lines 112–117 (`tlLogic id="center"`, static program `0`).

## Rule

Keep every statement that reads or writes the control state (`current_phase`, `phase_duration`,
`current_step`, `last_action`, `phase_states`) or the traffic light. Drop everything else:
observation features, reward, throughput, pedestrians (`enable_pedestrians=False` by default),
gym, numpy and sumolib plumbing. The dropped code only reads the control state, so it cannot
change which signals are shown.

## Line map

| Original lines | In the model | Edit | Reason |
|---|---|---|---|
| L113–L118 | `__init__` fields | kept: `num_seconds`, `delta_time`, `yellow_time`, `min_green`, `max_green`; other constructor arguments dropped | only these five affect control |
| L148 | `tls_id = "center"` | constant instead of `sumolib` net parsing | the net file has one traffic light, `center` |
| L155 | `num_phases = 2` | verbatim | |
| L203–L205 | `current_step`, `current_phase`, `phase_duration` | verbatim | |
| L206, L611 | `last_action = -1` | `None` → `-1` | ESBMC needs one type per field; `-1` is not a valid action, so it still means "no action yet" |
| L599–L602 | `phase_states` in `__init__` | moved from `reset()`; values = `phases[0].state` and `phases[2].state` of the net file (`PHASE_NS`, `PHASE_EW` in `traci_stub.py`) | reading `getAllProgramLogics` needs SUMO; the values are the same |
| L530–L545 | `_apply_action` | verbatim | |
| L554–L558 | `_set_phase` | verbatim, except the f-string in the `print` on L557 became a constant string | printing does not touch the control state; f-string formatting is extra string work for ESBMC |
| L564–L566 | `_set_yellow_phase` | verbatim | |
| L584–L589 | `traci.start()` | `super().reset()`, `traci.close()` and `_start_simulation()` replaced by the stub's `start()` | the stub's `start()` resets time and the light, which is what a fresh SUMO run does |
| L591–L598, L603–L606 | — | dropped | phase-count check and log prints |
| L608–L610 | `reset()` | verbatim | |
| L612–L628 | — | dropped | statistics, feature history, pedestrians |
| L631–L634 | warmup loop | verbatim | |
| L636–L645 | — | dropped | observation and info dict |
| L667, L670 | `step()` | verbatim | |
| L672–L690 | — | dropped | pedestrians, off by default |
| L692–L696 | delta loop | verbatim | |
| L698–L704 | — | dropped | throughput, observation, reward |
| L706 | `terminated` | verbatim; `step()` returns it | |
| L425–L430 | `phase_features()` | verbatim | used by R1: L429 divides by `max_green` |
| L337 | `queue_derivative()` | one lane instead of a numpy array | used by R1: divides by `delta_time` |

## Int abstraction applied at build time

`scripts/run_esbmc.py` rewrites these seven lines of the model before ESBMC sees it (table
`INT_REWRITES`). The file on disk stays verbatim; the build stops if one of the lines is missing.

| Model line | Becomes |
|---|---|
| `self.phase_states: dict[int, str] = {0: PHASE_NS, 1: PHASE_EW}` | `self.phase_states: int = 0` |
| `if phase in self.phase_states:` | `if phase == 0 or phase == 1:` |
| `...setRedYellowGreenState(self.tls_id, self.phase_states[phase])` | `...setCode(self.tls_id, phase_code(phase))` |
| `...setRedYellowGreenState(self.tls_id, self.phase_states[0])` | `...setCode(self.tls_id, C_NS)` |
| `current_state: str = ...getRedYellowGreenState(self.tls_id)` | `current_state: int = ...getCode(self.tls_id)` |
| `yellow_state: str = current_state.replace('G', 'y').replace('g', 'y')` | `yellow_state: int = yellow_of(current_state)` |
| `...setRedYellowGreenState(self.tls_id, yellow_state)` | `...setCode(self.tls_id, yellow_state)` |

Why it is sound: the light only ever holds one of the four strings of the static program
(the codes `C_NS`, `C_YNS`, `C_EW`, `C_YEW`) or something else (`C_OTHER`). The lemma harness
`harnesses/h_S0_strings.py` runs on the verbatim string model and proves that

- for each of the four strings, `replace('G','y').replace('g','y')` gives the string whose code
  is `yellow_of(code)`;
- for every phase index `p` in −2…3, `p in phase_states` holds exactly when `p` is 0 or 1, and
  then `phase_states[p]` is the string whose code is `phase_code(p)`;
- `phase_states[0]` (the fallback on L558) is the string with code `C_NS`.

Suite entry `S0-strings-str` must PASS before any other result is trusted. Without the
abstraction, string comparisons unroll into 14-character loops and the formula grows past 6 GB.

## v1

`env_core_v1.py` = `env_core_v0.py` + the four fixes marked `FIX-1` … `FIX-4` (same code as
`v1_fix.patch` applies to `src/environment.py`). `env_core_v1_naive.py` = v1 with the naive
max-green check (`phase_duration >= max_green`) and without the two switch-point checks of FIX-3.
