# Static analysis of `src/environment.py` (v0): warning classification (plan step E9.2)

Target: `src/environment.py` as on `main` (commit `643ba4d`, v0). Tools and versions: see
`versions.txt` (mypy 2.4.1, pylint 4.1.3, gymnasium 1.4.0, numpy 2.5.4). Raw output:
`mypy.txt` (default: 14 errors), `mypy_strict.txt` (`--strict`: 28 errors) and `pylint.txt`
(`--disable=C0301,C0103`: 16 messages, 9.48/10).

Categories: **false positive** (the tool is wrong), **real, low** (a real defect that does not
affect the signal-control logic), **style** (annotations, structure), **missed** (a real defect
that no warning points at).

| Tool | Warning | Line(s) | Category | Note |
|---|---|---|---|---|
| mypy | `"None" has no attribute "copy"` [attr-defined] | 409, 410 | False positive | `_get_instant_features()` (called on line 406) always sets `prev_queue_counts` and `prev_wait_times` to arrays (lines 312–313) before its only `return` (line 315). |
| mypy | `Signature of "reset" incompatible with supertype "gymnasium.core.Env"` [override] | 570 | Real, low | The declared signature differs from `Env.reset`: `seed` is not keyword-only, the types are not Optional, and there is no return type. At run time it accepts `seed=None` and returns `(state, info)` (line 652), so callers are unaffected. |
| pylint | W0221 arguments-differ (`reset`) | 570 | Real, low | Same issue as the mypy override error. |
| pylint | W0201 `phase_states` defined outside `__init__` | 599 | Real, low | Defined only in `reset()`. A phase switch before `reset()` raises `AttributeError: 'SumoTrafficEnv' object has no attribute 'phase_states'` (checked). The Gym API requires calling `reset()` first. |
| pylint | W0718 broad `except Exception: pass` | 494 | Real, low | If TraCI fails, a lane's CO2 term is dropped without any message. `total_co2` feeds the reward (line 509), not the control logic. |
| pylint | W0612 unused variable `departed` | 699 | Real, low | `getDepartedNumber()` is fetched but never used; throughput counts arrivals only. |
| mypy | implicit Optional (`x: T = None`) [assignment] | 85, 254, 570 (×2) | Style | `reward_weights`, `seed` (twice) and `options`: annotation only. |
| mypy | value assigned to an attribute that was first set to `None` [assignment] | 312, 313, 667 | Style | `prev_queue_counts`, `prev_wait_times` and `last_action` start as `None` (lines 206, 213–214) and have no `Optional[...]` annotation. |
| mypy | `Need type annotation` for a `deque` [var-annotated] | 159–162 | Style | Four history deques have no element type. |
| pylint | W0612 unused variable `lane_id` | 362 | Style | The `enumerate()` loop uses only the index. |
| pylint | W0107 unnecessary `pass` | 745 | Style | `render()` has a docstring and a `pass`. |
| pylint | R0902, R0913, R0917, R0914 (×3), R0915 | 43, 75, 377, 654 | Style | Size and complexity: 38 attributes, 13 constructor arguments, many locals and statements. |
| pylint | C0411 wrong import order | 29–31 | Style | Standard-library imports come after third-party ones. |
| mypy `--strict` only | no-untyped-def (×8), type-arg (×4), no-any-return, no-untyped-call | 85, 223, 254, 516, 520, 536, 547, 560, 570, 654, 741, 747, 754 | Style | Missing or incomplete annotations. None of them points at F1–F5. |
| — | F1–F5 | — | Missed | No warning points at any of them. Static analysis checks types and style, not functional properties such as enforcing max_green, the yellow interval or the action range. |

Totals: mypy (default) 14 = 2 false positives + 1 real, low + 11 style; pylint 16 = 4 real, low
+ 12 style; the 14 errors that only `--strict` reports are all style. F1–F5: all 5 missed.
