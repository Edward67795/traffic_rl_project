# h_C1.py -- C1: current_phase is 0 or 1 and matches the signal SUMO shows after every step.
K: int = 16
DELTA_TIME: int = 5
YELLOW_TIME: int = 3
MIN_GREEN: int = 10
MAX_GREEN: int = 60
STATIC_PROGRAM = False      # stub: True = L1 (SUMO static program modelled)
ANY_ACTION: bool = False


def main() -> None:
    env: SumoTrafficEnvCore = SumoTrafficEnvCore(DELTA_TIME, YELLOW_TIME, MIN_GREEN, MAX_GREEN, 3600)
    env.reset()
    k: int = 0
    while k < K:
        a: int = choose_action(ANY_ACTION)
        env.step(a)
        assert env.current_phase == 0 or env.current_phase == 1, "C1: current_phase out of range"
        shown: int = traci.trafficlight.code
        if env.current_phase == 0:
            assert shown == C_NS, "C1: controller believes NS green but SUMO shows something else"
        else:
            assert shown == C_EW, "C1: controller believes EW green but SUMO shows something else"
        k = k + 1


main()
