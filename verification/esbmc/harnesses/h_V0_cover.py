# h_V0_cover.py -- sanity check: the assumptions do not rule out the interesting behaviour.
# Run with --multi-property. A reachable cover is reported as a "failed" property,
# so the expected summary is that every cover "failed" (= is reachable).
K: int = 16
STATIC_PROGRAM = False      # stub: True = L1 (SUMO static program modelled)


def main() -> None:
    env: SumoTrafficEnvCore = SumoTrafficEnvCore(5, 3, 10, 60, 3600)
    env.reset()
    switched_to_ew: bool = False
    switched_back: bool = False
    k: int = 0
    while k < K:
        a: int = choose_action(False)
        before: int = env.current_phase
        env.step(a)
        if before == 0 and env.current_phase == 1:
            switched_to_ew = True
        if switched_to_ew and env.current_phase == 0:
            switched_back = True
        k = k + 1
    __ESBMC_cover(switched_to_ew)
    __ESBMC_cover(switched_back)
    __ESBMC_cover(env.phase_duration >= 60)


main()
