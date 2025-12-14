"""
SUMO Traffic Signal Control Reinforcement Learning Environment (Enhanced with Temporal Features)

This module provides a SUMO simulation environment wrapper with temporal feature enhancement,
specifically designed for reinforcement learning training of single intersection traffic light control.

Main enhancements over base version:
- Temporal state representation (frame stacking)
- Derivative features (queue/waiting time change rates)
- Arrival rate estimation
- Enhanced state space with temporal dynamics

Original features:
- Automatically start and manage SUMO simulation
- Provide standardized state observations (queue length, waiting time, lane density, etc.)
- Support multiple reward function configurations
- Handle signal phase switching logic with yellow light transitions

New in this version:
- Optional virtual pedestrians (enable_pedestrians=True):
  - Simple pedestrian queue model on NS / EW crossings
  - Pedestrian waiting time enters reward and state (if enabled)
  - Info dict includes pedestrian statistics
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import os
import sys
from collections import deque

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please set SUMO_HOME environment variable")

import traci
import sumolib


class SumoTrafficEnv(gym.Env):
    """
    SUMO Traffic Signal Control Environment with Temporal Features

    This environment extends the base SUMO wrapper with temporal state representation
    to help RL agents learn traffic dynamics and patterns over time.

    Temporal enhancements:
        - Frame stacking: maintains history of recent states
        - Derivative features: queue and waiting time change rates
        - Arrival rate estimation: tracks vehicle arrival patterns
        - Phase duration tracking: time elapsed in current phase

    New (optional):
        - Virtual pedestrian queues on NS / EW crossings:
          - enable_pedestrians=True to turn on
          - Pedestrian waiting time enters reward via 'ped_wait' weight

    Attributes:
        net_file: SUMO network file path
        route_file: vehicle route file path
        use_gui: whether to use graphical interface
        num_seconds: simulation duration per episode (seconds)
        delta_time: time interval between decisions (seconds)
        yellow_time: yellow light duration (seconds)
        min_green: minimum green light time (seconds)
        max_green: maximum green light time (seconds)
        history_length: number of historical states to maintain
    """

    metadata = {'render_modes': ['human']}

    def __init__(
        self,
        net_file: str,
        route_file: str,
        use_gui: bool = False,
        num_seconds: int = 3600,
        delta_time: int = 5,
        yellow_time: int = 3,
        min_green: int = 10,
        max_green: int = 60,
        reward_weights: dict = None,
        history_length: int = 4,   # temporal history
        enable_pedestrians: bool = False,      # NEW: simulate pedestrians
        ped_arrival_rate_ns: float = 0.05,     # NEW: pedestrians per second on NS crossings
        ped_arrival_rate_ew: float = 0.05      # NEW: pedestrians per second on EW crossings
    ):
        """
        Initialize SUMO environment with temporal features

        Args:
            net_file: SUMO network file (.net.xml) path
            route_file: route file (.rou.xml) path
            use_gui: whether to enable graphical interface
            num_seconds: simulation duration per episode
            delta_time: decision interval time
            yellow_time: yellow light transition time
            min_green: minimum green light duration
            max_green: maximum green light duration
            reward_weights: weights for reward function components
            history_length: number of time steps to keep in history (default: 4)
            enable_pedestrians: whether to enable virtual pedestrians
            ped_arrival_rate_ns: average pedestrians/sec on NS crossings
            ped_arrival_rate_ew: average pedestrians/sec on EW crossings
        """
        super().__init__()

        self.net_file = net_file
        self.route_file = route_file
        self.use_gui = use_gui
        self.num_seconds = num_seconds
        self.delta_time = delta_time
        self.yellow_time = yellow_time
        self.min_green = min_green
        self.max_green = max_green
        self.history_length = history_length

        # Reward weights
        self.reward_weights = reward_weights or {
            'queue': 0.5,
            'waiting_time': 0.3,
            'co2': 0.1,
            'switch': 0.1,
            'ped_wait': 0.0   # NEW: pedestrian waiting penalty weight (default 0)
        }

        # Pedestrian options
        self.enable_pedestrians = enable_pedestrians
        self.ped_arrival_rate_ns = ped_arrival_rate_ns
        self.ped_arrival_rate_ew = ped_arrival_rate_ew

        # Set SUMO binary
        if use_gui:
            self.sumo_binary = sumolib.checkBinary('sumo-gui')
        else:
            self.sumo_binary = sumolib.checkBinary('sumo')

        # Load network
        self.net = sumolib.net.readNet(net_file)

        # Traffic light id
        traffic_lights = self.net.getTrafficLights()
        if not traffic_lights:
            raise ValueError("No traffic lights found in network")
        self.tls_id = traffic_lights[0].getID()

        # Incoming lanes
        self.incoming_lanes = self._get_incoming_lanes()
        print(f"Detected {len(self.incoming_lanes)} incoming lanes: {self.incoming_lanes}")

        # Number of controllable phases (we use 2 green phases: NS / EW)
        self.num_phases = 2
        print(f"Using {self.num_phases} controllable signal phases")

        # ========== Temporal state tracking ==========
        self.state_history = deque(maxlen=history_length)
        self.queue_history = deque(maxlen=history_length)
        self.wait_history = deque(maxlen=history_length)
        self.arrival_history = deque(maxlen=20)  # Track arrivals over longer window

        # Base features per lane: queue, wait, density (3)
        num_lanes = len(self.incoming_lanes)
        base_features = num_lanes * 3

        # Temporal derivative features: queue_deriv, wait_deriv (2 per lane)
        temporal_features = num_lanes * 2

        # Arrival rate features (1 per lane)
        arrival_features = num_lanes

        # Phase features: one-hot (2) + duration (1)
        phase_features = self.num_phases + 1

        # Pedestrian features (optional): NS/ew queue + waiting time (4)
        self.ped_feature_dim = 0
        if self.enable_pedestrians:
            self.ped_feature_dim = 4

        # Total state dimension
        state_dim = base_features + temporal_features + arrival_features + phase_features + self.ped_feature_dim

        print(f"Enhanced state dimension: {state_dim}")
        print(f"  - Base features (queue/wait/density): {base_features}")
        print(f"  - Temporal derivatives: {temporal_features}")
        print(f"  - Arrival rates: {arrival_features}")
        print(f"  - Phase features: {phase_features}")
        if self.enable_pedestrians:
            print(f"  - Pedestrian features: {self.ped_feature_dim}")

        self.observation_space = spaces.Box(
            low=-1.0,  # Allow negative values for derivatives
            high=1.0,
            shape=(state_dim,),
            dtype=np.float32
        )

        self.action_space = spaces.Discrete(self.num_phases)

        # Episode level states
        self.current_step = 0
        self.current_phase = 0
        self.phase_duration = 0
        self.last_action = None
        self.episode_count = 0

        self.total_waiting_time = 0.0
        self.total_throughput = 0

        # For derivative calculation
        self.prev_queue_counts = None
        self.prev_wait_times = None

        # Pedestrian state
        self.ped_queue_ns = 0
        self.ped_queue_ew = 0
        self.total_ped_wait_time = 0.0

    # ==================== Helper methods ====================

    def _get_incoming_lanes(self) -> list:
        """
        Get all incoming lane IDs to the intersection

        Returns:
            list of incoming lane IDs
        """
        tls = self.net.getTrafficLights()[0]
        incoming_lanes = []

        for connection in tls.getConnections():
            lane_id = connection[0].getID()
            if lane_id not in incoming_lanes:
                incoming_lanes.append(lane_id)

        return sorted(incoming_lanes)

    def _get_num_phases(self) -> int:
        """
        Get the number of phases for the traffic light

        Returns:
            number of signal phases
        """
        tls = self.net.getTrafficLights()[0]
        programs = tls.getPrograms()
        if programs:
            program = list(programs.values())[0]
            return len(program.getPhases())
        return 4

    def _start_simulation(self, seed: int = None):
        """
        Start SUMO simulation

        Args:
            seed: random seed for experiment reproducibility
        """
        sumo_cmd = [
            self.sumo_binary,
            '-n', self.net_file,
            '-r', self.route_file,
            '--no-step-log', 'true',
            '--waiting-time-memory', '10000',
            '--time-to-teleport', '-1',
            '--no-warnings', 'true',
            '--duration-log.disable', 'true'
        ]

        if seed is not None:
            sumo_cmd.extend(['--seed', str(seed)])

        traci.start(sumo_cmd)

    # ==================== State construction ====================

    def _get_instant_features(self) -> np.ndarray:
        """
        Get instantaneous lane features (base features without temporal components)

        Returns:
            array of [queue, wait, density] for each lane
        """
        features = []
        queue_counts = []
        wait_times = []

        max_queue = 50
        max_wait = 300
        max_density = 1.0

        for lane_id in self.incoming_lanes:
            # Queue length
            queue = traci.lane.getLastStepHaltingNumber(lane_id)
            queue_norm = min(queue / max_queue, 1.0)
            queue_counts.append(queue)

            # Waiting time
            wait = traci.lane.getWaitingTime(lane_id)
            wait_norm = min(wait / max_wait, 1.0)
            wait_times.append(wait)

            # Density
            density = traci.lane.getLastStepOccupancy(lane_id) / 100.0
            density_norm = min(density, max_density)

            features.extend([queue_norm, wait_norm, density_norm])

        # Store for next step's derivative calculation
        self.prev_queue_counts = np.array(queue_counts)
        self.prev_wait_times = np.array(wait_times)

        return np.array(features, dtype=np.float32)

    def _get_temporal_derivatives(self) -> np.ndarray:
        """
        Calculate temporal derivatives (change rates) for queue and waiting time

        Returns:
            array of [queue_derivative, wait_derivative] for each lane
        """
        if len(self.queue_history) < 2:
            # Not enough history, return zeros
            return np.zeros(len(self.incoming_lanes) * 2, dtype=np.float32)

        # Current metrics
        current_queues = self.prev_queue_counts
        current_waits = self.prev_wait_times

        # Previous metrics (from history)
        prev_queues = self.queue_history[-1]
        prev_waits = self.wait_history[-1]

        # Change per time step
        queue_deriv = (current_queues - prev_queues) / self.delta_time
        wait_deriv = (current_waits - prev_waits) / self.delta_time

        # Normalize derivatives to [-1, 1]
        queue_deriv_norm = np.clip(queue_deriv / 10.0, -1.0, 1.0)
        wait_deriv_norm = np.clip(wait_deriv / 50.0, -1.0, 1.0)

        derivatives = []
        for qd, wd in zip(queue_deriv_norm, wait_deriv_norm):
            derivatives.extend([qd, wd])

        return np.array(derivatives, dtype=np.float32)

    def _get_arrival_rates(self) -> np.ndarray:
        """
        Estimate vehicle arrival rates for each lane based on recent history

        Returns:
            array of arrival rates (normalized) for each lane
        """
        if len(self.arrival_history) < 2:
            return np.zeros(len(self.incoming_lanes), dtype=np.float32)

        arrival_rates = []

        for i, lane_id in enumerate(self.incoming_lanes):
            recent_counts = [step_data[i] for step_data in list(self.arrival_history)[-10:]]

            if len(recent_counts) >= 2:
                arrivals = np.diff(recent_counts)
                arrivals = arrivals[arrivals > 0]
                avg_arrival = np.mean(arrivals) if len(arrivals) > 0 else 0.0
            else:
                avg_arrival = 0.0

            arrival_rate_norm = min(avg_arrival / 5.0, 1.0)
            arrival_rates.append(arrival_rate_norm)

        return np.array(arrival_rates, dtype=np.float32)

    def _get_state(self) -> np.ndarray:
        """
        Get enhanced state with temporal features

        State vector composition:
        1. Base instantaneous features (per lane):
           - Normalized queue length
           - Normalized waiting time
           - Vehicle density

        2. Temporal derivative features (per lane):
           - Queue length change rate
           - Waiting time change rate

        3. Arrival rate features (per lane):
           - Estimated vehicle arrival rate

        4. Phase information:
           - One-hot encoding of current phase
           - Normalized phase duration

        5. (Optional) Pedestrian features:
           - NS / EW queue length
           - NS / EW waiting time

        Returns:
            enhanced state vector (numpy array)
        """
        # 1. Instantaneous features
        instant_features = self._get_instant_features()

        # Update histories
        self.queue_history.append(self.prev_queue_counts.copy())
        self.wait_history.append(self.prev_wait_times.copy())

        # Track vehicle counts for arrival rate estimation
        current_vehicle_counts = []
        for lane_id in self.incoming_lanes:
            current_vehicle_counts.append(traci.lane.getLastStepVehicleNumber(lane_id))
        self.arrival_history.append(current_vehicle_counts)

        # 2. Temporal derivatives
        temporal_derivatives = self._get_temporal_derivatives()

        # 3. Arrival rates
        arrival_rates = self._get_arrival_rates()

        # 4. Phase features
        phase_one_hot = [0.0] * self.num_phases
        if 0 <= self.current_phase < self.num_phases:
            phase_one_hot[self.current_phase] = 1.0

        duration_norm = min(self.phase_duration / self.max_green, 1.0)
        phase_features = phase_one_hot + [duration_norm]

        features_list = [
            instant_features,
            temporal_derivatives,
            arrival_rates,
            np.array(phase_features, dtype=np.float32)
        ]

        # 5. Optional pedestrian features
        if self.enable_pedestrians:
            # Normalize: assume max 20 pedestrians, max 300s waiting time
            max_ped_queue = 20.0
            max_ped_wait = 300.0

            ped_queue_ns_norm = min(self.ped_queue_ns / max_ped_queue, 1.0)
            ped_queue_ew_norm = min(self.ped_queue_ew / max_ped_queue, 1.0)

            # Rough split of waiting time between NS / EW
            total_queue_ped = max(self.ped_queue_ns + self.ped_queue_ew, 1e-6)
            ped_wait_ns = self.total_ped_wait_time * (self.ped_queue_ns / total_queue_ped)
            ped_wait_ew = self.total_ped_wait_time - ped_wait_ns

            ped_wait_ns_norm = min(ped_wait_ns / max_ped_wait, 1.0)
            ped_wait_ew_norm = min(ped_wait_ew / max_ped_wait, 1.0)

            ped_features = np.array(
                [ped_queue_ns_norm, ped_queue_ew_norm,
                 ped_wait_ns_norm, ped_wait_ew_norm],
                dtype=np.float32
            )
            features_list.append(ped_features)

        state = np.concatenate(features_list)
        self.state_history.append(state.copy())

        return state.astype(np.float32)

    # ==================== Reward ====================

    def _calculate_reward(self) -> float:
        """
        Calculate reward value for current step

        Reward function design principles:
        - Shorter queue length is better (primary optimization goal)
        - Shorter waiting time is better
        - Less CO2 emission is better (environment friendly)
        - Avoid frequent signal switching (maintain stability)
        - (Optional) Less pedestrian waiting time is better

        Returns:
            reward value (negative value, closer to 0 is better)
        """
        total_queue = 0
        total_wait = 0
        total_co2 = 0

        for lane_id in self.incoming_lanes:
            total_queue += traci.lane.getLastStepHaltingNumber(lane_id)
            total_wait += traci.lane.getWaitingTime(lane_id)

            try:
                total_co2 += traci.lane.getCO2Emission(lane_id)
            except Exception:
                pass

        switch_penalty = 0.0
        if self.last_action is not None and self.last_action != self.current_phase:
            switch_penalty = 1.0

        # Pedestrian waiting
        ped_wait = 0.0
        if self.enable_pedestrians:
            ped_wait = self.total_ped_wait_time

        reward = (
            - self.reward_weights['queue'] * (total_queue / 100.0)
            - self.reward_weights['waiting_time'] * (total_wait / 1000.0)
            - self.reward_weights['co2'] * (total_co2 / 10000.0)
            - self.reward_weights['switch'] * switch_penalty
            - self.reward_weights['ped_wait'] * (ped_wait / 1000.0)
        )

        self.total_waiting_time += total_wait

        return reward

    # ==================== Action application ====================

    def _apply_action(self, action: int):
        """
        Apply action (signal phase switching)

        If switching to a different phase, must first go through yellow light transition.
        Must also respect minimum green light time constraint.

        Args:
            action: target signal phase (0 to num_phases-1)
        """
        if action != self.current_phase:
            # respect minimum green
            if self.phase_duration < self.min_green:
                return

            # yellow transition
            self._set_yellow_phase()

            for _ in range(self.yellow_time):
                traci.simulationStep()
                self.current_step += 1

            # set new phase
            self._set_phase(action)
            self.current_phase = action
            self.phase_duration = 0

    def _set_phase(self, phase: int):
        """
        Set traffic light to specified phase

        Args:
            phase: target phase index (0 or 1)
        """
        if phase in self.phase_states:
            traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[phase])
        else:
            print(f"Warning: invalid phase index {phase}, using phase 0")
            traci.trafficlight.setRedYellowGreenState(self.tls_id, self.phase_states[0])

    def _set_yellow_phase(self):
        """
        Set yellow light transition phase
        """
        current_state = traci.trafficlight.getRedYellowGreenState(self.tls_id)
        yellow_state = current_state.replace('G', 'y').replace('g', 'y')
        traci.trafficlight.setRedYellowGreenState(self.tls_id, yellow_state)

    # ==================== Gym API ====================

    def reset(self, seed: int = None, options: dict = None):
        """
        Reset environment to initial state

        This method is called at the start of each episode,
        closing current simulation and starting new simulation.

        Args:
            seed: random seed
            options: other options (unused)

        Returns:
            initial state and info dictionary
        """
        super().reset(seed=seed)

        if traci.isLoaded():
            traci.close()

        self._start_simulation(seed)

        # Use 2 green phases from the actual program (0 and 2)
        actual_phases = traci.trafficlight.getAllProgramLogics(self.tls_id)[0]
        self.num_phases = 2
        if len(actual_phases.phases) < 3:
            raise RuntimeError(
                f"Traffic light program has only {len(actual_phases.phases)} phases, "
                f"expected at least 3 (G/Y/G/...)."
            )
        self.phase_states = {
            0: actual_phases.phases[0].state,
            1: actual_phases.phases[2].state
        }
        if self.episode_count == 0:
            print(f"Using {self.num_phases} controllable green light phases")
            print(f"  phase 0: {self.phase_states[0]}")
            print(f"  phase 1: {self.phase_states[1]}")

        self.current_step = 0
        self.current_phase = 0
        self.phase_duration = 0
        self.last_action = None
        self.total_waiting_time = 0.0
        self.total_throughput = 0

        # Reset temporal tracking
        self.state_history.clear()
        self.queue_history.clear()
        self.wait_history.clear()
        self.arrival_history.clear()
        self.prev_queue_counts = None
        self.prev_wait_times = None

        # Reset pedestrians
        self.ped_queue_ns = 0
        self.ped_queue_ew = 0
        self.total_ped_wait_time = 0.0

        self.episode_count += 1

        # Warmup
        warmup_steps = 10
        for _ in range(warmup_steps):
            traci.simulationStep()
            self.current_step += 1

        state = self._get_state()

        info = {
            'step': 0,
            'episode': self.episode_count,
            'warmup_steps': warmup_steps,
            'current_phase': self.current_phase,
            'phase_duration': self.phase_duration,
            'total_queue': 0,
            'queue_ns': 0,
            'queue_ew': 0,
            'total_waiting_time': 0,
            'throughput': 0,
            'vehicles_in_network': 0
        }

        return state, info

    def step(self, action: int):
        """
        Execute one step of environment interaction

        This method receives agent's action, executes simulation step,
        and returns new state, reward, and other information.

        Args:
            action: action chosen by agent (target signal phase)

        Returns:
            tuple: (state, reward, terminated, truncated, info)
        """
        self.last_action = self.current_phase

        # Apply action (may trigger yellow phase & switching)
        self._apply_action(action)

        # NEW: simulate pedestrians at decision step (before advancing SUMO)
        if self.enable_pedestrians:
            # Poisson arrivals over delta_time seconds
            new_peds_ns = np.random.poisson(self.ped_arrival_rate_ns * self.delta_time)
            new_peds_ew = np.random.poisson(self.ped_arrival_rate_ew * self.delta_time)

            self.ped_queue_ns += new_peds_ns
            self.ped_queue_ew += new_peds_ew

            # All waiting pedestrians accumulate waiting time
            self.total_ped_wait_time += (self.ped_queue_ns + self.ped_queue_ew) * self.delta_time

            # Simple rule: car phase serves perpendicular pedestrians
            # phase 0: NS car green -> EW pedestrians cross
            # phase 1: EW car green -> NS pedestrians cross
            if self.current_phase == 0:
                self.ped_queue_ew = 0
            else:
                self.ped_queue_ns = 0

        # Advance simulation for delta_time steps
        for _ in range(self.delta_time):
            traci.simulationStep()
            self.current_step += 1
            self.phase_duration += 1

        # Throughput
        departed = traci.simulation.getDepartedNumber()
        arrived = traci.simulation.getArrivedNumber()
        self.total_throughput += arrived

        state = self._get_state()
        reward = self._calculate_reward()

        terminated = self.current_step >= self.num_seconds
        truncated = False

        # Build info
        total_queue = 0
        queue_ns = 0
        queue_ew = 0
        for lane in self.incoming_lanes:
            q = traci.lane.getLastStepHaltingNumber(lane)
            total_queue += q
            # Simple classification: NS vs EW based on lane id
            if 'north' in lane or 'south' in lane:
                queue_ns += q
            else:
                queue_ew += q

        info = {
            'step': self.current_step,
            'current_phase': self.current_phase,
            'phase_duration': self.phase_duration,
            'total_queue': total_queue,
            'queue_ns': queue_ns,
            'queue_ew': queue_ew,
            'total_waiting_time': self.total_waiting_time,
            'throughput': self.total_throughput,
            'vehicles_in_network': traci.vehicle.getIDCount()
        }

        if self.enable_pedestrians:
            info['ped_queue_ns'] = self.ped_queue_ns
            info['ped_queue_ew'] = self.ped_queue_ew
            info['total_ped_wait_time'] = self.total_ped_wait_time

        return state, reward, terminated, truncated, info

    def render(self, mode='human'):
        """
        Render environment (if using GUI mode)
        """
        pass

    def close(self):
        """
        Close environment and release resources
        """
        if traci.isLoaded():
            traci.close()

    def get_metrics(self) -> dict:
        """
        Get performance metrics for current episode

        Returns:
            dictionary containing various performance metrics
        """
        avg_queue = 0
        avg_wait = 0
        total_vehicles = 0

        for lane_id in self.incoming_lanes:
            avg_queue += traci.lane.getLastStepHaltingNumber(lane_id)
            avg_wait += traci.lane.getWaitingTime(lane_id)
            total_vehicles += traci.lane.getLastStepVehicleNumber(lane_id)

        num_lanes = len(self.incoming_lanes)

        return {
            'average_queue_length': avg_queue / num_lanes if num_lanes > 0 else 0,
            'average_waiting_time': avg_wait / num_lanes if num_lanes > 0 else 0,
            'total_vehicles': total_vehicles,
            'throughput': self.total_throughput,
            'simulation_time': self.current_step,
            'total_ped_wait_time': self.total_ped_wait_time if self.enable_pedestrians else 0.0
        }


if __name__ == '__main__':
    print("Testing enhanced SUMO environment with temporal features and pedestrians...")
    print("Environment module loaded successfully!")
