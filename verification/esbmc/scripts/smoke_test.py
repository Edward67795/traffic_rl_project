#!/usr/bin/env python3
"""E3 smoke test: does this ESBMC build handle every Python feature the model relies on?

Each case is a tiny program with a known verdict. Run from the repo root:
    python verification/esbmc/scripts/smoke_test.py [--esbmc PATH]
Every row must say "ok". A row that says "MISMATCH" names the feature to work around
(see the fallback column in the ESBMC tab, step E3).
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CASES = [
    ("class + method mutating fields", """
class C:
    def __init__(self) -> None:
        self.n: int = 0
    def inc(self) -> None:
        self.n += 1
def main() -> None:
    c: C = C()
    c.inc()
    c.inc()
    assert c.n == 2
main()
""", [], "PASS"),
    ("dict[int, str] with `in` and subscript", """
def main() -> None:
    d: dict[int, str] = {0: "GGr", 1: "rrG"}
    k: int = nondet_int()
    __ESBMC_assume(k == 0 or k == 1)
    assert k in d
    assert d[k] == "GGr" or d[k] == "rrG"
    assert not (2 in d)
main()
""", [], "PASS"),
    ("str.replace on a runtime string", """
class L:
    def __init__(self) -> None:
        self.state: str = "GGGgrrrGGGgrrr"
def main() -> None:
    l: L = L()
    b: bool = nondet_bool()
    if b:
        l.state = "rrrrGGgrrrrGGg"
    y: str = l.state.replace('G', 'y').replace('g', 'y')
    assert y == "yyyyrrryyyyrrr" or y == "rrrryyyrrrryyy"
main()
""", ["--unwind", "18"], "PASS"),
    ("str.replace result is precise (must FAIL)", """
def main() -> None:
    s: str = "GGgr"
    y: str = s.replace('G', 'y')
    assert y == "yyyr"
main()
""", ["--unwind", "18"], "FAIL"),
    ("global object, nested attribute call, str arg -> int code", """
PHASE: str = "GGGgrrrGGGgrrr"
class TL:
    def __init__(self) -> None:
        self.code: int = 0
    def put(self, tls_id: str, s: str) -> None:
        if s == PHASE:
            self.code = 1
        else:
            self.code = 2
class T:
    def __init__(self) -> None:
        self.trafficlight: TL = TL()
        self.time: int = 0
    def step(self) -> None:
        self.time = self.time + 1
traci: T = T()
def main() -> None:
    traci.trafficlight.put("center", PHASE)
    traci.step()
    assert traci.trafficlight.code == 1 and traci.time == 1
main()
""", ["--unwind", "18"], "PASS"),
    ("for _ in range(n) with nondet n", """
def main() -> None:
    n: int = nondet_int()
    __ESBMC_assume(n >= 0 and n <= 6)
    c: int = 0
    for _ in range(n):
        c += 1
    assert c == n
main()
""", ["--unwind", "8"], "PASS"),
    ("nondet helper function + try/except ValueError", """
def choose_int(lo: int, hi: int) -> int:
    x: int = nondet_int()
    __ESBMC_assume(x >= lo and x <= hi)
    return x
def check(d: int) -> int:
    if d < 1:
        raise ValueError("bad")
    return d
def main() -> None:
    d: int = choose_int(-1, 3)
    try:
        v: int = check(d)
    except ValueError:
        return
    assert v >= 1
main()
""", [], "PASS"),
    ("division by zero is detected (must FAIL)", """
def main() -> None:
    m: int = nondet_int()
    __ESBMC_assume(m >= 0 and m <= 5)
    x: float = min(3 / m, 1.0)
main()
""", [], "FAIL"),
    ("list repetition, index write, chained comparison", """
def main() -> None:
    p: int = nondet_int()
    __ESBMC_assume(p == 0 or p == 1)
    one_hot: list[float] = [0.0] * 2
    if 0 <= p < 2:
        one_hot[p] = 1.0
    f: list[float] = one_hot + [0.5]
    assert len(f) == 3 and one_hot[p] == 1.0
main()
""", ["--unwind", "6"], "PASS"),
    ("element of a concatenated list (known imprecise: FAIL)", """
def main() -> None:
    a: list[float] = [0.0, 1.0]
    f: list[float] = a + [0.5]
    assert f[2] == 0.5
main()
""", ["--unwind", "6"], "FAIL"),
    ("a method named `set` (known frontend ERROR)", """
class T:
    def __init__(self) -> None:
        self.state: str = "a"
    def set(self, s: str) -> None:
        self.state = s
def main() -> None:
    t: T = T()
    t.set("b")
    assert t.state == "b"
main()
""", [], "ERROR"),
    ("__ESBMC_cover reachability (--multi-property)", """
def main() -> None:
    x: int = nondet_int()
    __ESBMC_assume(x >= 0 and x <= 10)
    __ESBMC_cover(x == 7)
main()
""", ["--multi-property"], "FAIL"),
    ("--k-induction proves an unbounded invariant", """
def main() -> None:
    pd: int = 0
    while True:
        b: bool = nondet_bool()
        if b or pd + 5 > 60:
            pd = 0
        pd = pd + 5
        assert pd <= 60
main()
""", ["--k-induction", "--max-k-step", "20"], "PASS"),
    # Correct verdict is PASS (ESBMC master 78e8e3a8 on Linux gives PASS). Homebrew 8.6.0 leaves
    # c's fields unconstrained after the try because Clock() cannot raise (FAIL with d = 6).
    # MISMATCH here means the bug is fixed. h_P1/h_R1 work around it with accepts().
    ("object built in try, used after it (known Homebrew 8.6.0 bug: FAIL)", """
class Clock:
    def __init__(self, d: int) -> None:
        self.d: int = d
        self.t: int = 0
    def tick(self) -> None:
        self.t = self.t + self.d
def main() -> None:
    d: int = nondet_int()
    __ESBMC_assume(d >= 1 and d <= 6)
    try:
        c: Clock = Clock(d)
    except ValueError:
        return
    c.tick()
    assert c.t >= 1
main()
""", [], "FAIL"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esbmc", default=shutil.which("esbmc") or "esbmc")
    args = ap.parse_args()
    ver = subprocess.run([args.esbmc, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"ESBMC: {ver or '(not found)'}   Python: {sys.version.split()[0]}\n")
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, src, extra, expected) in enumerate(CASES, 1):
            f = Path(tmp) / f"case{i}.py"
            f.write_text(src.lstrip())
            t0 = time.time()
            p = subprocess.run([args.esbmc, str(f), "--python", sys.executable] + extra,
                               capture_output=True, text=True, timeout=600)
            out = p.stdout + p.stderr
            got = ("PASS" if "VERIFICATION SUCCESSFUL" in out else
                   "FAIL" if "VERIFICATION FAILED" in out else "ERROR")
            ok = got == expected
            bad += not ok
            print(f"{i:2d}. {name:52s} expected {expected:4s} got {got:5s} "
                  f"{time.time() - t0:6.2f}s  {'ok' if ok else 'MISMATCH'}")
            if got == "ERROR":
                tail = [l for l in out.strip().splitlines() if l.strip()][-3:]
                print("      " + "\n      ".join(tail))
    print(f"\n{len(CASES) - bad} of {len(CASES)} cases ok")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
