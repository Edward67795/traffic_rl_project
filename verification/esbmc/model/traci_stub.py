# traci_stub.py -- environment model of SUMO/TraCI for ESBMC-Python.
#
# Replaces the three TraCI calls the control logic uses:
#   traci.simulationStep()
#   traci.trafficlight.getRedYellowGreenState(tls_id)
#   traci.trafficlight.setRedYellowGreenState(tls_id, state)
#
# Two fidelity levels (CEGER-style environment refinement):
#   L0 (STATIC_PROGRAM = False): the light shows exactly what the controller last set.
#   L1 (STATIC_PROGRAM = True):  additionally models SUMO's static tlLogic from
#       networks/single_intersection.net.xml (42 s G / 3 s y / 42 s G / 3 s y), which keeps
#       running until the first setRedYellowGreenState() switches the light to "online".
#
# The light's state is stored as an int code (C_*). ESBMC models Python strings as C
# character arrays, so every comparison or replace() unrolls a loop over 14 characters,
# and a 16-step harness on the string-level model needs more than 6 GB. For ESBMC runs,
# scripts/run_esbmc.py rewrites the model's string lines to the int-code calls
# (getCode/setCode/yellow_of/phase_code); harnesses/h_S0_strings.py proves the rewrite equivalent.
#
# Monitors run once per simulated second on the state a driver would see, so a yellow
# that is set and overwritten within the same second is never observed.
# Each harness enables only the property it checks (CHK_* flags below).

PHASE_NS: str = "GGGgrrrGGGgrrr"   # program phase 0 = controller phase 0 (NS green)
YELLOW_NS: str = "yyyyrrryyyyrrr"  # program phase 1
PHASE_EW: str = "rrrrGGgrrrrGGg"   # program phase 2 = controller phase 1 (EW green)
YELLOW_EW: str = "rrrryyyrrrryyy"  # program phase 3

C_NS: int = 0
C_YNS: int = 1
C_EW: int = 2
C_YEW: int = 3
C_OTHER: int = 4

K_NS_GREEN: int = 0
K_EW_GREEN: int = 1
K_YELLOW: int = 2
K_OTHER: int = 3

# ---- configuration: each harness overrides these at module level (plain `NAME = value`).
# They are module-level constants on purpose: ESBMC then prunes every disabled check;
# as object fields they were symbolic and made the solver 1000x slower.
STATIC_PROGRAM: bool = False   # True = L1 stub (SUMO static program modelled)
CHK_S1: bool = False
CHK_T1: bool = False
CHK_T2: bool = False
CHK_G1: bool = False
CHK_G2: bool = False
CHK_L1: bool = False
MON_MIN_GREEN: int = 10
MON_MAX_GREEN: int = 60
MON_YELLOW: int = 3            # L1 wait limit = MON_MAX_GREEN + 2 * MON_YELLOW
MON_Y_MIN: int = 3             # T2: shortest acceptable yellow


def choose_int(lo: int, hi: int) -> int:
    # A nondeterministic int in [lo, hi]. ESBMC explores every value;
    # scripts/py_sim.py replaces this function with random.randint for quick CPython runs.
    # (Not named nondet_*: ESBMC 8.6 reads "nondet_<type>" as an intrinsic and fails on
    #  "nondet_in" with "NameError: name 'in' is not defined".)
    x: int = nondet_int()
    __ESBMC_assume(x >= lo and x <= hi)
    return x


def choose_action(any_action: bool) -> int:
    # The agent abstraction: any action sequence (covers every policy, including the DQN).
    if any_action:
        return choose_int(-1, 2)   # also out-of-range values, for F3
    return choose_int(0, 1)


def code_of(s: str) -> int:
    if s == PHASE_NS:
        return C_NS
    if s == YELLOW_NS:
        return C_YNS
    if s == PHASE_EW:
        return C_EW
    if s == YELLOW_EW:
        return C_YEW
    return C_OTHER


def text_of(c: int) -> str:
    if c == C_NS:
        return PHASE_NS
    if c == C_YNS:
        return YELLOW_NS
    if c == C_EW:
        return PHASE_EW
    if c == C_YEW:
        return YELLOW_EW
    return "?"


def kind_of(c: int) -> int:
    if c == C_NS:
        return K_NS_GREEN
    if c == C_EW:
        return K_EW_GREEN
    if c == C_YNS or c == C_YEW:
        return K_YELLOW
    return K_OTHER


def phase_code(p: int) -> int:
    # Int-code summary of the model's phase_states dict {0: PHASE_NS, 1: PHASE_EW}
    # (ESBMC's dict model makes the solver ~1000x slower; h_S0_strings proves equivalence).
    if p == 1:
        return C_EW
    return C_NS


def yellow_of(c: int) -> int:
    # Int-code summary of `state.replace('G', 'y').replace('g', 'y')` on the four signal
    # states (proved equivalent by harnesses/h_S0_strings.py).
    if c == C_NS or c == C_YNS:
        return C_YNS
    if c == C_EW or c == C_YEW:
        return C_YEW
    return C_OTHER


def classify(s: str) -> int:
    # used by verification/common/replay_in_sumo.py on the strings real SUMO reports
    return kind_of(code_of(s))


class TrafficLightStub:
    def __init__(self) -> None:
        self.code: int = C_NS
        self.online: bool = False  # becomes True at the first setRedYellowGreenState()

    def setRedYellowGreenState(self, tls_id: str, state: str) -> None:
        self.code = code_of(state)
        self.online = True

    def getRedYellowGreenState(self, tls_id: str) -> str:
        return text_of(self.code)

    # int-code versions used by the abstracted model that run_esbmc.py builds for ESBMC
    def setCode(self, tls_id: str, c: int) -> None:
        self.code = c
        self.online = True

    def getCode(self, tls_id: str) -> int:
        return self.code


class TraciStub:
    def __init__(self) -> None:
        self.trafficlight: TrafficLightStub = TrafficLightStub()
        self.time: int = 0
        # static program cursor (L1 only)
        self.sp_index: int = 0
        self.sp_left: int = 43   # SUMO shows the first phase for 43 s (t = 0..42), later ones for their duration
        # monitor state
        self.prev_kind: int = K_NS_GREEN
        self.last_green: int = K_NS_GREEN  # direction of the most recent green
        self.green_len: int = 0            # seconds the current green has been shown
        self.yellow_len: int = 0           # seconds the current yellow has been shown
        self.ns_wait: int = 0              # seconds since NS was last green
        self.ew_wait: int = 0              # seconds since EW was last green

    def start(self) -> None:
        # traci.start(): the light starts in program phase 0 (NS green), static program running
        self.trafficlight.code = C_NS
        self.trafficlight.online = False
        self.time = 0
        self.sp_index = 0
        self.sp_left = 43
        self.prev_kind = K_NS_GREEN
        self.last_green = K_NS_GREEN
        self.green_len = 0
        self.yellow_len = 0
        self.ns_wait = 0
        self.ew_wait = 0

    def _advance_static_program(self) -> None:
        self.sp_left = self.sp_left - 1
        if self.sp_left == 0:
            self.sp_index = (self.sp_index + 1) % 4
            if self.sp_index == 0:
                self.trafficlight.code = C_NS
                self.sp_left = 42
            elif self.sp_index == 1:
                self.trafficlight.code = C_YNS
                self.sp_left = 3
            elif self.sp_index == 2:
                self.trafficlight.code = C_EW
                self.sp_left = 42
            else:
                self.trafficlight.code = C_YEW
                self.sp_left = 3

    def simulationStep(self) -> None:
        # One simulated second. SUMO shows the state that holds during this second.
        if CHK_S1 or CHK_T1 or CHK_T2 or CHK_G1 or CHK_G2 or CHK_L1:
            kind: int = kind_of(self.trafficlight.code)
            self._monitor(kind)
        self.time = self.time + 1
        if STATIC_PROGRAM and not self.trafficlight.online:
            self._advance_static_program()

    def _monitor(self, kind: int) -> None:
        prev: int = self.prev_kind
        if CHK_S1:
            # S1 (part 1): only the four conflict-free states of the net file are ever shown.
            # Part 2 (those four states respect the junction's foes matrix) is checked
            # once by scripts/check_phase_strings.py.
            assert kind != K_OTHER, "S1: unknown signal state shown"
        if CHK_T1:
            assert not (prev == K_NS_GREEN and kind == K_EW_GREEN), "T1: NS green -> EW green without yellow"
            assert not (prev == K_EW_GREEN and kind == K_NS_GREEN), "T1: EW green -> NS green without yellow"
        if prev == K_YELLOW and kind != K_YELLOW:
            if CHK_T2:
                assert self.yellow_len >= MON_Y_MIN, "T2: yellow shorter than y_min"
                assert kind != self.last_green, "T2: yellow not followed by the other direction"
        if (prev == K_NS_GREEN or prev == K_EW_GREEN) and kind != prev:
            if CHK_G1:
                assert self.green_len >= MON_MIN_GREEN, "G1: green cut before min_green"
        # update counters for this second
        if kind == K_NS_GREEN or kind == K_EW_GREEN:
            if kind == prev:
                self.green_len = self.green_len + 1
            else:
                self.green_len = 1
            self.last_green = kind
            self.yellow_len = 0
        else:
            self.green_len = 0
            if kind == K_YELLOW:
                if prev == K_YELLOW:
                    self.yellow_len = self.yellow_len + 1
                else:
                    self.yellow_len = 1
        if kind == K_NS_GREEN:
            self.ns_wait = 0
        else:
            self.ns_wait = self.ns_wait + 1
        if kind == K_EW_GREEN:
            self.ew_wait = 0
        else:
            self.ew_wait = self.ew_wait + 1
        if CHK_G2:
            assert self.green_len <= MON_MAX_GREEN, "G2: observed green longer than max_green"
        if CHK_L1:
            assert self.ns_wait <= MON_MAX_GREEN + 2 * MON_YELLOW, "L1: NS waited too long for green"
            assert self.ew_wait <= MON_MAX_GREEN + 2 * MON_YELLOW, "L1: EW waited too long for green"
        self.prev_kind = kind


traci: TraciStub = TraciStub()
