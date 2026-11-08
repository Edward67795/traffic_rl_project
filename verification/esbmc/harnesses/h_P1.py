# h_P1.py -- P1: every decision step advances simulated time by at least 1 s
# (otherwise an episode never terminates).
K: int = 4
D_LO: int = -1
D_HI: int = 6


# Homebrew ESBMC 8.6.0 leaves an object's fields unconstrained after the try that built it
# when the constructor cannot raise (v0; see results/raw/P1-v0-try-quirk.txt). So the
# configuration is checked on a throw-away probe, and the env is built outside try.
def accepts(d: int, y: int, mn: int, mx: int, n: int) -> bool:
    try:
        probe: SumoTrafficEnvCore = SumoTrafficEnvCore(d, y, mn, mx, n)
    except ValueError:
        return False     # v1 rejects this configuration in __init__
    return True


def main() -> None:
    d: int = choose_int(D_LO, D_HI)
    ok: bool = accepts(d, 3, 10, 60, 3600)
    if not ok:
        return
    env: SumoTrafficEnvCore = SumoTrafficEnvCore(d, 3, 10, 60, 3600)
    env.reset()
    k: int = 0
    while k < K:
        before: int = env.current_step
        a: int = choose_action(False)
        env.step(a)
        assert env.current_step >= before + 1, "P1: a decision step did not advance time"
        k = k + 1


main()
