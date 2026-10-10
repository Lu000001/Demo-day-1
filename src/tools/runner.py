"""One run, one database, one immutable input/code snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import uuid

import yaml

from message.data import Data, resolve, sha256


def json_write(path: Path, value: dict):
    """Atomically publish metadata, including failures."""
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def versions() -> dict:
    """Record relevant dependency versions without capturing secrets or license files."""
    names = [
        "message-ix",
        "ixmp",
        "pandas",
        "numpy",
        "pyam-iamc",
        "PyYAML",
        "matplotlib",
        "openpyxl",
        "nomenclature-iamc",
    ]
    packages = {}
    for name in names:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not installed"
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": packages,
    }


def git(root: Path, *args) -> str:
    """Read git state when available; a distributed ZIP also runs without git."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True
        )
    except FileNotFoundError:
        return "unavailable"
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def prepare(
    root: Path,
    config: dict,
    scenario: str,
    parent_run: Path | None = None,
    *,
    project: str | None = None,
) -> Path:
    """Copy exact inputs and working-tree code before building any database."""
    if parent_run is None:
        data = Data(root, config)
        input_manifest = data.manifest()
    else:
        # Replay with the saved reader, even after the live input schema changes.
        # reproduce() has already checked every file in the original snapshot.
        input_manifest = json.loads((parent_run / "inputs.json").read_text())
        saved_files = json.loads((parent_run / "manifest.json").read_text())
        for name, digest in input_manifest.items():
            path = Path(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != "data"
                or saved_files.get(name) != digest
            ):
                raise ValueError(f"Input is not a verified snapshot data file: {name}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = f"{project}_{scenario}" if project else scenario
    run = root / "runs" / f"{label}_{stamp}_{uuid.uuid4().hex[:8]}"
    # A replay writes alongside the original runs, never inside its snapshot.
    if parent_run is not None:
        run = parent_run.parent / run.name
    snapshot = run / "snapshot"
    snapshot.mkdir(parents=True)
    # Retain each source layout so historical flat-layout runs also replay.
    source = root / "src" if (root / "src/message").is_dir() else root
    for package in ["message", "tools", "reporting"]:
        shutil.copytree(
            source / package,
            snapshot / source.relative_to(root) / package,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    if project:
        path = root / "projects" / project / "scenarios.yaml"
        dest = snapshot / path.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    for relative_path in input_manifest:
        path = root / relative_path
        dest = snapshot / path.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    for filename in ["pyproject.toml", "environment.yml", "requirements-lock.txt"]:
        if (root / filename).exists():
            shutil.copy2(root / filename, snapshot / filename)
    (snapshot / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    manifest = {
        str(p.relative_to(snapshot)): sha256(p)
        for p in sorted(snapshot.rglob("*"))
        if p.is_file()
    }
    json_write(run / "manifest.json", manifest)
    json_write(run / "inputs.json", input_manifest)
    json_write(run / "environment.json", versions())
    meta = {
        "run_id": run.name,
        "scenario": scenario,
        "project": project,
        "status": "prepared",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": git(root, "rev-parse", "HEAD"),
        "source_dirty": bool(git(root, "status", "--porcelain")),
        "snapshot_sha256": sha256(run / "manifest.json"),
        "reproduces": str(parent_run) if parent_run else None,
        "scope": (
            json.loads((parent_run / "meta.json").read_text())["scope"]
            if parent_run is not None
            else f"China, {'/'.join(map(str, data.years))}; covered energy uses and steel only; no agriculture, upstream fuel production or other material-process emissions"
        ),
    }
    json_write(run / "meta.json", meta)
    # Snapshot files, including untracked source code, are authoritative. A patch is supplementary.
    if parent_run is None:
        (run / "working-tree.patch").write_text(
            git(
                root,
                "diff",
                "HEAD",
                "--",
                "src",
                "data",
                "config.yaml",
                "projects",
                "pyproject.toml",
                "environment.yml",
                "requirements-lock.txt",
            )
        )
    return run


def verify_snapshot(run: Path):
    """Reject altered snapshot files before replaying an archived experiment."""
    expected = json.loads((run / "manifest.json").read_text())
    changed = [
        name
        for name, digest in expected.items()
        if not (run / "snapshot" / name).is_file()
        or sha256(run / "snapshot" / name) != digest
    ]
    if changed:
        raise ValueError(f"Snapshot integrity failure: {changed}")


def execute(run: Path) -> Path:
    """Run the snapshotted worker in a subprocess, keeping logs out of the console."""
    snapshot = run / "snapshot"
    source = snapshot / "src" if (snapshot / "src/tools").is_dir() else snapshot
    with (run / "run.log").open("w") as log:
        result = subprocess.run(
            [sys.executable, "-m", "tools.worker", str(run.resolve())],
            # Python imports the saved packages here, ahead of the live editable install.
            cwd=source,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    # GAMS writes license-owner details into its standard header. Keep these out
    # of the shareable run log; raw scratch logs stay in the private work folder.
    log = (run / "run.log").read_text(errors="replace")
    log = re.sub(
        r"(?ms)^Licensee:.*?(?=^System information:|^GAMS \d)",
        "[GAMS license header omitted]\n",
        log,
    )
    (run / "run.log").write_text(log)
    meta = json.loads((run / "meta.json").read_text())
    if result.returncode != 0 or meta["status"] != "complete":
        raise RuntimeError(f"Run failed; preserved diagnostic log: {run / 'run.log'}")
    return run


def run_scenario(
    root: Path,
    scenario: str = "reference",
    config_path: Path | None = None,
    *,
    project: str = "course",
) -> Path:
    """Resolve, snapshot, build, solve, validate, and report one scenario."""
    config = resolve(root, scenario, config_path, project=project)
    run = prepare(root, config, scenario, project=project)
    print(f"Running {project}/{scenario}: {run.name}", flush=True)
    return execute(run)


def reproduce(original: Path) -> Path:
    """Use the original code and input snapshot, then compare numerical results."""
    original = original.resolve()
    verify_snapshot(original)
    old = json.loads((original / "meta.json").read_text())
    if old["status"] != "complete":
        raise ValueError("Only a completed run can be reproduced.")
    root = original / "snapshot"
    cfg = yaml.safe_load((root / "config.yaml").read_text())
    run = prepare(
        root, cfg, old["scenario"], parent_run=original, project=old.get("project")
    )
    execute(run)
    import numpy as np
    import pandas as pd

    cols = ["model", "scenario", "region", "variable", "unit", "year"]
    a = (
        pd.read_csv(original / "report/iamc_long.csv")
        .set_index(cols)
        .value.sort_index()
    )
    b = pd.read_csv(run / "report/iamc_long.csv").set_index(cols).value.sort_index()
    checks = {
        "same_coordinates": a.index.equals(b.index),
        "same_environment": json.loads((original / "environment.json").read_text())
        == json.loads((run / "environment.json").read_text()),
        "rtol": 1e-6,
        "atol": 1e-6,
    }
    checks["all_series_within_tolerance"] = checks["same_coordinates"] and bool(
        np.allclose(a, b, rtol=checks["rtol"], atol=checks["atol"])
    )
    objective = json.loads((run / "meta.json").read_text())["objective"]
    checks["objective_within_tolerance"] = bool(
        np.isclose(old["objective"], objective, rtol=1e-8, atol=1e-4)
    )
    json_write(run / "reproduction.json", checks)
    if (
        not checks["all_series_within_tolerance"]
        or not checks["objective_within_tolerance"]
    ):
        raise RuntimeError(
            f"Replay solved but differs from the original; inspect {run / 'reproduction.json'} (alternate LP optima are possible)."
        )
    return run
