"""Brute-force bounded exploration of the extracted timing logic (a stand-in for what ESBMC does symbolically).
Checks the max-green invariant (green time <= max_green) for every action sequence up to depth K."""
import itertools

def run(seq, delta, yellow, gmin, gmax, fix):
    phase, pd = 0, 0
    for a in seq:
        if fix == "naive" and pd >= gmax:            # "obvious" repair
            a = 1 - phase
        if fix == "lookahead" and pd + delta > gmax:  # repair that accounts for step granularity
            a = 1 - phase
        if a != phase and pd >= gmin:
            phase, pd = a, 0
        pd += delta
        if pd > gmax:
            return False, pd
    return True, pd

K = 16
grid = [(d, gmin, gmax) for d in (1, 2, 3, 5, 7) for gmin in (5, 10, 11) for gmax in (12, 14, 60, 62, 63)]
for fix in ("none", "naive", "lookahead"):
    fails = []
    for d, gmin, gmax in grid:
        if gmin > gmax: continue
        for seq in itertools.product((0, 1), repeat=K):
            ok, pd = run(seq, d, 3, gmin, gmax, fix)
            if not ok:
                fails.append((d, gmin, gmax, pd)); break
    print(f"fix={fix:9s}: {len(fails):2d} failing configs, e.g. {fails[:4]}")

# feasibility: is there ANY switch point with gmin <= k*delta <= gmax ?
bad = [(d, gmin, gmax) for d, gmin, gmax in grid if gmin <= gmax and not any(gmin <= k*d <= gmax for k in range(1, 100))]
print("configs where min/max green are jointly unsatisfiable:", bad)
