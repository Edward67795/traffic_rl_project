# h_R1.py -- R1: no runtime error (division by zero) in the arithmetic the observation uses,
# for any configuration in range. ESBMC adds the division-by-zero checks itself.
D_LO: int = 0
D_HI: int = 10
MAXG_LO: int = 0
MAXG_HI: int = 90


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
    mx: int = choose_int(MAXG_LO, MAXG_HI)
    ok: bool = accepts(d, 3, 0, mx, 3600)
    if not ok:
        return
    env: SumoTrafficEnvCore = SumoTrafficEnvCore(d, 3, 0, mx, 3600)
    feats: list[float] = env.phase_features()
    q_now: int = choose_int(0, 50)
    q_before: int = choose_int(0, 50)
    deriv: float = env.queue_derivative(q_now, q_before)


main()
