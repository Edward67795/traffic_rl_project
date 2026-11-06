#!/usr/bin/env python3
"""Compare finite Promela traces with the read-only extracted Python v0 core.

This is model conformance testing against a reference abstraction, not exhaustive
property verification or evidence of conformance with real SUMO.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import tempfile

SPIN_DIR = Path(__file__).resolve().parents[1]
REPO = SPIN_DIR.parents[1]
MODEL = SPIN_DIR / "models" / "controller.pml"
REFERENCE = REPO / "verification" / "esbmc" / "model"


def reference_trace(actions, static, delta, yellow, minimum=10, maximum=60):
    namespace = {}
    for filename in ("traci_stub.py", "env_core_v0.py"):
        path = REFERENCE / filename
        exec(compile(path.read_text(), str(path), "exec"), namespace)
    namespace["STATIC_PROGRAM"] = bool(static)
    stub = namespace["traci"]
    env = namespace["SumoTrafficEnvCore"](delta, yellow, minimum, maximum, 3600)
    age_cap = maximum + minimum + delta + 1
    records = []

    def state():
        return [stub.trafficlight.code, env.current_phase,
                min(env.phase_duration, age_cap), int(stub.trafficlight.online),
                stub.sp_index, stub.sp_left]

    original_step = stub.simulationStep

    def observed_step():
        records.append(["TICK", env.current_step, *state()])
        original_step()

    stub.simulationStep = observed_step
    with contextlib.redirect_stdout(io.StringIO()):
        env.reset()
        records.append(["DONE", 0, env.current_step, *state()])
        for number, action in enumerate(actions, 1):
            env.step(action)
            records.append(["DONE", number, env.current_step, *state()])
    return records


def promela_trace(actions, static, delta, yellow):
    with tempfile.TemporaryDirectory(prefix="traffic-spin-trace-") as directory:
        build = Path(directory)
        shutil.copyfile(MODEL, build / "controller.pml")
        shutil.copyfile(MODEL.parent / "properties.pml", build / "properties.pml")
        branches = "\n".join(
            f":: decision == {i} -> action = {action}"
            for i, action in enumerate(actions))
        (build / "actions.pml").write_text(
            f"#define N_ACTIONS {len(actions)}\n"
            f"inline choose_action() {{ if\n{branches}\nfi }}\n")
        command = ["spin", "-T", "-DTRACE", f"-DSTATIC_PROGRAM={static}",
                   f"-DDELTA_TIME={delta}", f"-DYELLOW_TIME={yellow}",
                   "-u1000000", "controller.pml"]
        result = subprocess.run(command, cwd=build, capture_output=True,
                                text=True, timeout=30)
        if result.returncode or "Error:" in result.stdout or result.stderr:
            raise RuntimeError(f"{command}\n{result.stdout}\n{result.stderr}")
        records = []
        for line in result.stdout.splitlines():
            match = re.fullmatch(r"\s*(TICK|DONE) ((?:-?\d+ ?)+)\s*", line)
            if match:
                records.append([match[1], *map(int, match[2].split())])
        return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random-cases", type=int, default=24)
    parser.add_argument("--seed", type=int, default=6863)
    parser.add_argument("--output", type=Path,
                        help="Optional JSON evidence output path")
    args = parser.parse_args()
    if args.random_cases < 0:
        parser.error("--random-cases must be nonnegative")
    rng = random.Random(args.seed)
    sequences = [
        ("hold-ns", [0] * 50),
        ("request-ew", [1] * 20),
        ("alternate", [0, 1] * 20),
        ("takeover-after-static-yellow", [0] * 7 + [1] * 10),
        ("takeover-after-static-ew", [0] * 9 + [1] * 10),
        ("invalid", [0, 0, -1, 2, 1, 0] * 6),
    ]
    cases = [(name, actions, static, delta, yellow)
             for name, actions in sequences
             for static in (0, 1) for delta in (1, 5, 7) for yellow in (0, 3)]
    for i in range(args.random_cases):
        cases.append((f"random-{i}", [rng.choice([-1, 0, 1, 2]) for _ in range(40)],
                      rng.randrange(2), rng.choice([1, 5, 7]), rng.choice([0, 3])))
    results = []
    for name, actions, static, delta, yellow in cases:
        expected = reference_trace(actions, static, delta, yellow)
        actual = promela_trace(actions, static, delta, yellow)
        if actual != expected:
            mismatch = next((i for i, pair in enumerate(zip(expected, actual))
                             if pair[0] != pair[1]), min(len(actual), len(expected)))
            raise AssertionError(
                f"{name}: static={static} delta={delta} yellow={yellow} "
                f"record={mismatch}\nexpected={expected[mismatch:mismatch+1]}"
                f"\nactual={actual[mismatch:mismatch+1]}")
        results.append(dict(name=name, static=static, delta=delta, yellow=yellow,
                            actions=actions, records=len(actual), result="MATCH"))
    evidence = {
        "kind": "finite-reference-trace-comparison",
        "warning": "Not exhaustive property verification; not a real SUMO replay",
        "seed": args.seed,
        "spin": subprocess.check_output(["spin", "-V"], text=True).strip(),
        "sha256": {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in [MODEL, MODEL.parent / "properties.pml", REFERENCE / "traci_stub.py",
                                REFERENCE / "env_core_v0.py", Path(__file__).resolve()]},
        "cases": results,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"MATCH: {len(results)} finite cases, "
          f"{sum(row['records'] for row in results)} observation records")
    print("Reference: extracted Python v0 + TraCI stub; real SUMO not exercised.")


if __name__ == "__main__":
    main()
