# h_S0_strings.py -- lemma for the string -> int-code abstraction used in every other harness.
# (1) For each of the four signal states the light can show, the controller's string code
#         yellow = state.replace('G', 'y').replace('g', 'y')
#     produces exactly the state that yellow_of() predicts;
# (2) the model's dict {0: PHASE_NS, 1: PHASE_EW} behaves like phase_code() for every key.
# Built on the verbatim string model (suite id ends in "-str").


def main() -> None:
    c: int = choose_int(0, 3)
    s: str = text_of(c)
    y: str = s.replace('G', 'y').replace('g', 'y')
    assert code_of(y) == yellow_of(c), "S0: replace() disagrees with yellow_of()"
    d: dict[int, str] = {0: PHASE_NS, 1: PHASE_EW}
    p: int = choose_int(-2, 3)
    assert (p in d) == (p == 0 or p == 1), "S0: dict membership"
    if p in d:
        assert code_of(d[p]) == phase_code(p), "S0: dict value"
    assert code_of(d[0]) == C_NS, "S0: fallback value"


main()
