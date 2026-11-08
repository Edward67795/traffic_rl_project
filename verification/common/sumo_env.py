#!/usr/bin/env python3
"""Load the real SumoTrafficEnv of a given version without editing src/ (decision D1).

v0: src/environment.py as checked out. src/ is never edited, so this is the original code,
    the same as on main.
v1: a copy of src/environment.py in a temporary directory, with
    verification/esbmc/model/v1_fix.patch applied to the copy. This is the same method as
    load_source() in verification/spin/scripts/validate_sumo.py, plus `patch -F 0`: no fuzz
    is allowed, so a patch that does not apply exactly raises RuntimeError instead of
    silently producing a different v1.

Usage:
    from sumo_env import load_sumo_env
    SumoTrafficEnv = load_sumo_env("v1")
"""
import atexit
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "src" / "environment.py"
PATCH = REPO / "verification" / "esbmc" / "model" / "v1_fix.patch"
VERSIONS = ("v0", "v1")


def patched_copy(directory: Path) -> Path:
    """Copy src/environment.py to <directory>/src/ and apply the v1 patch to the copy."""
    path = directory / "src" / "environment.py"
    path.parent.mkdir(parents=True)
    shutil.copyfile(SOURCE, path)
    p = subprocess.run(["patch", "--batch", "-p1", "-F", "0", "-i", str(PATCH)],
                       cwd=directory, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"{PATCH.name} does not apply to {SOURCE}:\n{p.stdout}{p.stderr}")
    return path


def load_sumo_env(version: str = "v0"):
    """Return the SumoTrafficEnv class of `version` ("v0" or "v1")."""
    if version == "v0":
        path = SOURCE
    elif version == "v1":
        directory = Path(tempfile.mkdtemp(prefix="sumo_env_v1_"))
        atexit.register(shutil.rmtree, directory, ignore_errors=True)
        path = patched_copy(directory)
    else:
        raise ValueError(f"unknown version {version!r}; expected one of {VERSIONS}")
    spec = importlib.util.spec_from_file_location(f"sumo_environment_{version}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module      # so inspect, pickle and tracebacks can find the source
    spec.loader.exec_module(module)
    return module.SumoTrafficEnv
