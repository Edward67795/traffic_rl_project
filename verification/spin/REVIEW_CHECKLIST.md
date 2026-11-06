# Human review checklist

Status: **pending human review**. Automated checks and AI inspection do not
constitute the manual review described in the proposal. Record a reviewer/date
only when that person has actually reviewed the evidence.

Reviewer: not supplied. Date: not supplied. Decision: pending.

| Topic | Evidence to inspect | Human decision |
|---|---|---|
| v0 correspondence | MODEL_MAPPING; original _apply_action/_set_phase/_set_yellow_phase/reset/step | Pending |
| v1 exact patch | VERSION branches against FIX-1..4; rejection before forcing | Pending |
| Phase abstraction | Four exact strings, protected vs permissive greens; link/request mapping | Pending |
| Static timing | Initial43 samples and subsequent42/3/42/3; real SUMO records | Pending |
| Time semantics | Pre-second vs post-decision sampling; yellow0 not an observed interval | Pending |
| Clock abstraction | Saturation preserves selected guards and bad thresholds; no wraparound | Pending |
| Property meanings | Assertions/LTL, direction symmetry, C1 provisional D4 boundary | Pending |
| Fairness | Request events and eligibility; conditional vs unconditional L2 | Pending |
| Infinite model | Positive-time ongoing loop; omitted real episode termination | Pending |
| Rejection | Constructor/action errors are not normal operation PASSs | Pending |
| Counterexamples | Finite/loop lengths; original and illustrative witnesses; source reproductions | Pending |
| Residual defect | v1 delta12/min0/max11 accepted but G2 fails; patch left unchanged | Pending |
| Proof strength | Model checking vs finite reference tests vs actual SUMO observations | Pending |
| Joint comparison | ESBMC supplied evidence, aligned domains and bounded/unbounded coverage | Pending |

Suggested review sequence: read README and MODEL_MAPPING, inspect controller.pml
and properties.pml alongside source/patch, examine one finite and one cyclic
witness, then read S6 SUMO validation outcomes and the final report limitations.
Record disagreements with evidence paths and required reruns. Do not check boxes
merely because a script ran or every default v1 case passed.
