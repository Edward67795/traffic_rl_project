# h_G2_param.py -- G2 for every configuration in range (the F5 experiment).
# A configuration the constructor rejects (ValueError) is not a violation.
K: int = 20
D_LO: int = 1
D_HI: int = 7
MIN_LO: int = 0
MIN_HI: int = 12
MAX_LO: int = 11
MAX_HI: int = 16


def main() -> None:
    d: int = choose_int(D_LO, D_HI)
    mn: int = choose_int(MIN_LO, MIN_HI)
    mx: int = choose_int(MAX_LO, MAX_HI)
    y: int = 3
    try:
        env: SumoTrafficEnvCore = SumoTrafficEnvCore(d, y, mn, mx, 3600)
    except ValueError:
        return
    env.reset()
    k: int = 0
    while k < K:
        a: int = choose_action(False)
        env.step(a)
        assert env.phase_duration <= env.max_green, "G2: phase_duration exceeds max_green"
        k = k + 1


main()
