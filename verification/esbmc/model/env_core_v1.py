# env_core_v1.py -- control logic after the four v1 fixes (mirrors the patched src/environment.py).
# Differences from env_core_v0.py are marked "FIX-1" ... "FIX-4".

WARMUP_STEPS: int = 10
Y_MIN: int = 3


def first_switch_point(start: int, delta_time: int, min_green: int) -> int:
    # Smallest phase_duration >= min_green reachable from `start` in steps of delta_time.
    if start >= min_green:
        return start
    k: int = (min_green - start + delta_time - 1) // delta_time
    return start + k * delta_time


class SumoTrafficEnvCore:
    def __init__(self, delta_time: int, yellow_time: int, min_green: int,
                 max_green: int, num_seconds: int) -> None:
        # FIX-3: reject configurations under which the timing properties cannot all hold
        if delta_time < 1:
            raise ValueError("delta_time must be >= 1")
        if yellow_time < Y_MIN:
            raise ValueError("yellow_time must be >= 3")
        if min_green < 0 or max_green < 1 or min_green > max_green:
            raise ValueError("need 0 <= min_green <= max_green and max_green >= 1")
        if first_switch_point(WARMUP_STEPS, delta_time, min_green) > max_green:
            raise ValueError("first green has no switch point inside [min_green, max_green]")
        if first_switch_point(0, delta_time, min_green) > max_green:
            raise ValueError("no multiple of delta_time inside [min_green, max_green]")
        self.num_seconds: int = num_seconds
        self.delta_time: int = delta_time
        self.yellow_time: int = yellow_time
        self.min_green: int = min_green
        self.max_green: int = max_green
        self.tls_id: str = "center"
        self.num_phases: int = 2
        self.current_step: int = 0
        self.current_phase: int = 0
        self.phase_duration: int = 0
        self.last_action: int = -1
        self.phase_states: dict[int, str] = {0: PHASE_NS, 1: PHASE_EW}

    def _apply_action(self, action: int) -> None:
        # FIX-2: the action space is {0, 1}; anything else is a caller bug
        if action != 0 and action != 1:
            raise ValueError("action must be 0 or 1")
        # FIX-1: enforce max_green, looking one decision step ahead
        if self.phase_duration + self.delta_time > self.max_green:
            action = 1 - self.current_phase
        if action != self.current_phase:
            if self.phase_duration < self.min_green:
                return
            self._set_yellow_phase()
            for _ in range(self.yellow_time):
                traci.simulationStep()
                self.current_step += 1
            self._set_phase(action)
            self.current_phase = action
            self.phase_duration = 0

    def _set_phase(self, phase: int) -> None:
        if phase in self.phase_states:
            traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[phase])
        else:
            print("Warning: invalid phase index, using phase 0")
            traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[0])

    def _set_yellow_phase(self) -> None:
        current_state: str = traci.trafficlight.getRedYellowGreenState(self.tls_id)
        yellow_state: str = current_state.replace('G', 'y').replace('g', 'y')
        traci.trafficlight.setRedYellowGreenState(self.tls_id, yellow_state)

    def reset(self) -> None:
        traci.start()
        self._set_phase(0)       # FIX-4a: take control of the light before warmup (no static program)
        self.current_step = 0
        self.current_phase = 0
        self.phase_duration = 0
        self.last_action = -1
        warmup_steps: int = WARMUP_STEPS
        for _ in range(warmup_steps):
            traci.simulationStep()
            self.current_step += 1
            self.phase_duration += 1   # FIX-4b: the warmup green counts toward the first green

    def step(self, action: int) -> bool:
        self.last_action = self.current_phase
        self._apply_action(action)
        for _ in range(self.delta_time):
            traci.simulationStep()
            self.current_step += 1
            self.phase_duration += 1
        terminated: bool = self.current_step >= self.num_seconds
        return terminated

    def phase_features(self) -> list[float]:
        phase_one_hot: list[float] = [0.0] * self.num_phases
        if 0 <= self.current_phase < self.num_phases:
            phase_one_hot[self.current_phase] = 1.0
        duration_norm: float = min(self.phase_duration / self.max_green, 1.0)
        return phase_one_hot + [duration_norm]

    def queue_derivative(self, current_queue: int, prev_queue: int) -> float:
        return (current_queue - prev_queue) / self.delta_time
