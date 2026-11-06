# h_R1.py -- R1: no runtime error (division by zero) in the arithmetic the observation uses,
# for any configuration in range. ESBMC adds the division-by-zero checks itself.
D_LO: int = 0
D_HI: int = 10
MAXG_LO: int = 0
MAXG_HI: int = 90


def main() -> None:
    d: int = choose_int(D_LO, D_HI)
    mx: int = choose_int(MAXG_LO, MAXG_HI)
    try:
        env: SumoTrafficEnvCore = SumoTrafficEnvCore(d, 3, 0, mx, 3600)
    except ValueError:
        return   # v1 rejects this configuration in __init__
    feats: list[float] = env.phase_features()
    q_now: int = choose_int(0, 50)
    q_before: int = choose_int(0, 50)
    deriv: float = env.queue_derivative(q_now, q_before)


main()
