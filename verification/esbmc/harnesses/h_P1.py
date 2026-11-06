# h_P1.py -- P1: every decision step advances simulated time by at least 1 s
# (otherwise an episode never terminates).
K: int = 4
D_LO: int = -1
D_HI: int = 6


def main() -> None:
    d: int = choose_int(D_LO, D_HI)
    try:
        env: SumoTrafficEnvCore = SumoTrafficEnvCore(d, 3, 10, 60, 3600)
    except ValueError:
        return   # v1 rejects this configuration in __init__
    env.reset()
    k: int = 0
    while k < K:
        before: int = env.current_step
        a: int = choose_action(False)
        env.step(a)
        assert env.current_step >= before + 1, "P1: a decision step did not advance time"
        k = k + 1


main()
