# h_G2.py -- G2: no green phase lasts longer than max_green seconds.
# Checked twice: on the controller's own counter (phase_duration) after every decision step,
# and on the green a driver actually sees (traci_stub.py, CHK_G2, once per second).
K: int = 16                 # the shortest v0 counterexample has 11 steps (observed green)
DELTA_TIME: int = 5
YELLOW_TIME: int = 3
MIN_GREEN: int = 10
MAX_GREEN: int = 60
ANY_ACTION: bool = False
STATIC_PROGRAM = False
CHK_G2 = True
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
        assert env.phase_duration <= env.max_green, "G2: phase_duration exceeds max_green"
        k = k + 1


main()
