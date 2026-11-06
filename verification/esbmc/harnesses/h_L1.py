# h_L1.py -- L1: no direction waits more than max_green + 2*yellow_time seconds for green
# The check itself runs once per simulated second inside traci_stub.py (CHK_L1).
# Parameters can be overridden with scripts/run_esbmc.py --set NAME=VALUE.
K: int = 16                 # decision steps explored
DELTA_TIME: int = 5
YELLOW_TIME: int = 3
MIN_GREEN: int = 10
MAX_GREEN: int = 60
ANY_ACTION: bool = False    # True = actions in [-1, 2] (out-of-range values allowed)
STATIC_PROGRAM = False      # stub: True = L1 (SUMO static program modelled)
CHK_L1 = True
MON_MIN_GREEN = MIN_GREEN
MON_MAX_GREEN = MAX_GREEN
MON_YELLOW = YELLOW_TIME


def main() -> None:
    env: SumoTrafficEnvCore = SumoTrafficEnvCore(DELTA_TIME, YELLOW_TIME, MIN_GREEN, MAX_GREEN, 3600)
    env.reset()
    k: int = 0
    while k < K:
        a: int = choose_action(ANY_ACTION)
        env.step(a)
        k = k + 1


main()
