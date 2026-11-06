# h_G2_ind.py -- unbounded proof of G2 and C1 by induction on decision steps.
# ESBMC's own --k-induction disables its inductive step here ("cannot havoc what a loop
# writes through a pointer": every Python object field is behind a pointer), so the
# induction is written out by hand:
#   Inv(s) := 0 <= phase_duration <= max_green and current_phase in {0, 1}
#             and the light shows the green of current_phase and is under control (online)
#   base: Inv holds after reset();  step: Inv(s) and one step(a) from ANY such s => Inv(s').
# Both checks are bounded (one reset, one step), so plain BMC proves Inv for every step count.
DELTA_TIME: int = 5
YELLOW_TIME: int = 3
MIN_GREEN: int = 10
MAX_GREEN: int = 60


def invariant_holds(env: SumoTrafficEnvCore) -> bool:
    if env.phase_duration < 0 or env.phase_duration > env.max_green:
        return False
    if env.current_phase != 0 and env.current_phase != 1:
        return False
    return traci.trafficlight.code == phase_code(env.current_phase) and traci.trafficlight.online


def main() -> None:
    env: SumoTrafficEnvCore = SumoTrafficEnvCore(DELTA_TIME, YELLOW_TIME, MIN_GREEN, MAX_GREEN, 3600)
    env.reset()
    assert invariant_holds(env), "base case: Inv fails right after reset()"
    # an arbitrary state that satisfies Inv
    env.phase_duration = choose_int(0, MAX_GREEN)
    env.current_phase = choose_int(0, 1)
    traci.trafficlight.code = phase_code(env.current_phase)
    traci.trafficlight.online = True
    a: int = choose_action(False)
    env.step(a)
    assert invariant_holds(env), "inductive step: Inv not preserved by step()"


main()
