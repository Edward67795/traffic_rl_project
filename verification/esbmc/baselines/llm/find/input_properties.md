# Properties

| ID | Property |
|---|---|
| S1 | No two conflicting links are protected green (G) at the same time; NS and EW are never green together |
| T1 | A change of green direction always passes through an all-yellow interval |
| T2 | Yellow lasts at least 3 s (the default `yellow_time`) and is followed by the other direction's green |
| G1 | A green phase is never cut before `min_green` s |
| G2 | No green phase lasts longer than `max_green` s |
| L1 | No direction waits more than `max_green + 2*yellow_time` s (66 s) for green |
| L2 | Each direction is green infinitely often |
| C1 | The controller's `current_phase` is 0 or 1 and matches the signal SUMO shows |
| R1 | No runtime errors (division by zero, index errors) for any configuration in range |
| P1 | Every decision step advances simulated time by at least 1 s |
