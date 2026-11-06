# env_core_v0.py -- control logic of SumoTrafficEnv, extracted from
# src/environment.py at commit 643ba4d (main). Line numbers in comments refer to that file.
#
# What was kept: every statement that reads or writes the control state
# (current_phase, phase_duration, current_step, last_action, phase_states)
# or the traffic light. What was dropped: observation features, reward,
# throughput, pedestrians (enable_pedestrians=False by default), gym/numpy/sumolib plumbing.
# Every edit is listed in verification/esbmc/model/EXTRACTION.md.
# The module expects a global `traci` object (traci_stub.py, or the real traci for replays).


class SumoTrafficEnvCore:
    def __init__(self, delta_time: int, yellow_time: int, min_green: int,
                 max_green: int, num_seconds: int) -> None:
        self.num_seconds: int = num_seconds          # L113
        self.delta_time: int = delta_time            # L115
        self.yellow_time: int = yellow_time          # L116
        self.min_green: int = min_green              # L117
        self.max_green: int = max_green              # L118
        self.tls_id: str = "center"                  # L148 (traffic_lights[0].getID())
        self.num_phases: int = 2                     # L155
        self.current_step: int = 0                   # L203
        self.current_phase: int = 0                  # L204
        self.phase_duration: int = 0                 # L205
        self.last_action: int = -1                   # L206 (None in the original; -1 = "no action yet")
        self.phase_states: dict[int, str] = {0: PHASE_NS, 1: PHASE_EW}  # L599-602 (values from the net file)

    # ==================== Action application (L520-566) ====================

    def _apply_action(self, action: int) -> None:
        if action != self.current_phase:             # L530
            if self.phase_duration < self.min_green: # L532
                return                               # L533
            self._set_yellow_phase()                 # L536
            for _ in range(self.yellow_time):        # L538
                traci.simulationStep()               # L539
                self.current_step += 1               # L540
            self._set_phase(action)                  # L543
            self.current_phase = action              # L544
            self.phase_duration = 0                  # L545

    def _set_phase(self, phase: int) -> None:
        if phase in self.phase_states:               # L554
            traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[phase])  # L555
        else:
            print("Warning: invalid phase index, using phase 0")                              # L557
            traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[0])      # L558

    def _set_yellow_phase(self) -> None:
        current_state: str = traci.trafficlight.getRedYellowGreenState(self.tls_id)  # L564
        yellow_state: str = current_state.replace('G', 'y').replace('g', 'y')        # L565
        traci.trafficlight.setRedYellowGreenState(self.tls_id, yellow_state)         # L566

    # ==================== Gym API (L570-739), control part only ====================

    def reset(self) -> None:
        traci.start()                                # L586-589 (_start_simulation)
        # L591-602: phase_states come from the program logic; set in __init__ (same values)
        self.current_step = 0                        # L608
        self.current_phase = 0                       # L609
        self.phase_duration = 0                      # L610
        self.last_action = -1                        # L611
        warmup_steps: int = 10                       # L631
        for _ in range(warmup_steps):                # L632
            traci.simulationStep()                   # L633
            self.current_step += 1                   # L634

    def step(self, action: int) -> bool:
        self.last_action = self.current_phase        # L667
        self._apply_action(action)                   # L670
        for _ in range(self.delta_time):             # L693
            traci.simulationStep()                   # L694
            self.current_step += 1                   # L695
            self.phase_duration += 1                 # L696
        terminated: bool = self.current_step >= self.num_seconds  # L706
        return terminated

    # ==================== Arithmetic that can raise (for R1) ====================

    def phase_features(self) -> list[float]:
        # L425-430 (_get_state, phase features)
        phase_one_hot: list[float] = [0.0] * self.num_phases
        if 0 <= self.current_phase < self.num_phases:
            phase_one_hot[self.current_phase] = 1.0
        duration_norm: float = min(self.phase_duration / self.max_green, 1.0)
        return phase_one_hot + [duration_norm]

    def queue_derivative(self, current_queue: int, prev_queue: int) -> float:
        # L337 (_get_temporal_derivatives), one lane
        return (current_queue - prev_queue) / self.delta_time
