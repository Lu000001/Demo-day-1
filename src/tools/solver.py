"""Select a GAMS LP solver without changing the installed MESSAGEix model."""

from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
import hashlib
import json


def gams_executable(config: dict) -> str:
    """Resolve GAMS; a free LP solver still needs this modeling runtime."""
    value = config["solver"].get("gams_executable")
    executable = shutil.which(str(value)) if value else shutil.which("gams")
    if not executable:
        raise RuntimeError(
            "GAMS runtime not found. Install GAMS and its applicable free personal license; HiGHS is included. See docs/installation.md. Set solver.gams_executable if GAMS is not on PATH."
        )
    return executable


def solve(scenario, config: dict, run: Path) -> dict:
    """Copy the upstream formulation into this run, select the solver, and solve.

    MESSAGEix 3.11.1 hard-codes CPLEX in auxiliary_settings.gms. This adapter
    changes that one solver-selection statement in the run's private copy;
    equations and the installed package are untouched.
    """
    import message_ix

    executable = gams_executable(config)
    solver = config["solver"]["name"].lower()
    model = run / "work/gams-model"
    shutil.copytree(Path(message_ix.__file__).parent / "model", model)
    settings = model / "MESSAGE/auxiliary_settings.gms"
    original = settings.read_text()
    patched, count = re.subn(
        r"(?im)^option LP\s*=\s*CPLEX\s*;", f"option LP = {solver.upper()} ;", original
    )
    if count != 1:
        raise RuntimeError(
            "Unsupported upstream solver configuration; review the pinned MESSAGEix version."
        )
    settings.write_text(patched)
    options = config["solver"].get("options", {})
    if any(
        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", str(k)) or "\n" in str(v)
        for k, v in options.items()
    ):
        raise ValueError("Invalid solver option name or value.")
    # MESSAGE_LP.optfile=1 reads the selected solver's option file.
    (model / f"{solver}.opt").write_text(
        "\n".join(f"{k} = {v}" for k, v in options.items()) + "\n"
    )
    hashes = {
        str(p.relative_to(model)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(model.rglob("*.gms"))
    }
    (run / "formulation-manifest.json").write_text(json.dumps(hashes, indent=2) + "\n")
    before = os.environ.get("PATH", "")
    os.environ["PATH"] = str(Path(executable).parent) + os.pathsep + before
    license_file = config["solver"].get("gams_license_file")
    gams_args = (
        [f"license={Path(license_file).expanduser().resolve()}"] if license_file else []
    )
    try:
        scenario.solve(
            model="MESSAGE",
            model_dir=str(model),
            in_file=str(model / "data/input.gdx"),
            out_file=str(run / "solution.gdx"),
            # GAMS expands these names inside quoted log strings (255-char limit).
            # Its cwd is the private model directory, so short relative names
            # avoid repeating a long scenario/run path while preserving isolation.
            solve_args=[
                '--in="data/input.gdx"',
                '--out="../../solution.gdx"',
                '--iter="output/iteration.gdx"',
            ],
            solve_options=options if solver == "cplex" else {},
            use_temp_dir=False,
            gams_args=gams_args,
        )
    finally:
        os.environ["PATH"] = before
    if not scenario.has_solution():
        raise RuntimeError("The scenario has no accepted solution.")
    objective = scenario.var("OBJ")
    log_path = model / "MESSAGE_run.log"
    log = log_path.read_text(errors="replace") if log_path.exists() else ""

    def match(pattern):
        found = re.search(pattern, log)
        return found.group(1) if found else "unavailable"

    return {
        "solver": solver,
        "gams_executable": executable,
        "gams_version": match(r"GAMS (\d+\.\d+\.\d+)"),
        "solver_version": match(r"Running HiGHS ([\d.]+)")
        if solver == "highs"
        else "see run.log",
        "model_rows": match(r"---\s+(\d+) rows"),
        "model_columns": match(r"rows\s+(\d+) columns"),
        "objective": float(
            objective["lvl"]
            if isinstance(objective, dict)
            else objective.iloc[0]["lvl"]
        ),
    }
