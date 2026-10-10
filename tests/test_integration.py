"""Real solves are explicit; these tests never replace an unavailable solver with a mock."""

from pathlib import Path
import json
import os
import shutil

import numpy as np
import pandas as pd
import pytest
import yaml

from message.data import resolve
from tools.runner import run_scenario, reproduce

ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("COURSE_TEST_SOLVE") != "1",
        reason="Set COURSE_TEST_SOLVE=1 with GAMS/HiGHS installed to run actual optimization",
    ),
]


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    """Actual solves must never populate or clear the student's runs folder."""
    root = tmp_path_factory.mktemp("course-model")
    for name in ["src", "data", "projects"]:
        shutil.copytree(ROOT / name, root / name)
    shutil.copy2(ROOT / "config.yaml", root / "config.yaml")
    return root


@pytest.fixture(scope="module")
def runs(workspace):
    return {
        name: run_scenario(workspace, name)
        for name in ["reference", "carbon_price", "no_ccs"]
    }


def test_scenario_mechanisms_and_physical_audit(runs):
    def values(name, var):
        df = pd.read_csv(runs[name] / "report/iamc_long.csv")
        return df[df.variable == var].set_index("year").value.sort_index()

    for path in runs.values():
        meta = json.loads((path / "meta.json").read_text())
        assert meta["status"] == "complete" and meta["solver"] == "highs"
        assert meta["validation"]["commodity_balance_max_residual"] < 1e-5
        assert np.isfinite(meta["objective"])
    assert (
        values("carbon_price", "Emissions|CO2")
        <= values("reference", "Emissions|CO2") + 1e-5
    ).all()
    assert values("carbon_price", "Carbon Capture").max() > 0
    assert np.allclose(values("no_ccs", "Carbon Capture"), 0, atol=1e-8)
    assert np.allclose(
        values("carbon_price", "Carbon Capture"),
        values("carbon_price", "Carbon Capture|Geological Storage"),
    )
    a = json.loads((runs["carbon_price"] / "meta.json").read_text())["objective"]
    b = json.loads((runs["no_ccs"] / "meta.json").read_text())["objective"]
    assert b >= a - 1e-4


@pytest.mark.parametrize("name", ["reference", "no_ccs"])
def test_snapshot_replay(runs, name):
    replay = reproduce(runs[name])
    checks = json.loads((replay / "reproduction.json").read_text())
    assert (
        checks["objective_within_tolerance"] and checks["all_series_within_tolerance"]
    )


def test_long_model_names_solve_without_gams_text_overflow(tmp_path, workspace):
    """Descriptive experiment names must not exceed GAMS's log-string limit."""
    config = resolve(ROOT)
    config["model_name"] = "A descriptive classroom model name " * 4
    config_path = tmp_path / "long-name.yaml"
    config_path.write_text(yaml.safe_dump(config))
    path = run_scenario(workspace, "reference", config_path)
    meta = json.loads((path / "meta.json").read_text())
    assert meta["status"] == "complete"
    assert meta["validation"]["commodity_balance_max_residual"] < 1e-5
    table = pd.read_csv(path / "report/iamc.csv")
    assert table.Model.unique().tolist() == [config["model_name"]]


def test_custom_project_run_and_replay(tmp_path):
    """A student project must resolve, snapshot and reproduce its own overrides."""
    for name in ["src", "data"]:
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copy2(ROOT / "config.yaml", tmp_path / "config.yaml")
    project = tmp_path / "projects/my_study"
    project.mkdir(parents=True)
    (project / "scenarios.yaml").write_text(
        "high_demand:\n  framework:\n    demand_scale: 1.05\n"
    )
    # Exercise the CLI in the exported-style checkout, not only its Python API.
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "tools.cli", "run", "--project", "my_study", "--all"],
        cwd=tmp_path / "src",
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    [run] = list((tmp_path / "runs").glob("my_study_high_demand_*"))
    meta = json.loads((run / "meta.json").read_text())
    assert meta["project"] == "my_study" and meta["status"] == "complete"
    config = yaml.safe_load((run / "snapshot/config.yaml").read_text())
    assert config["framework"]["demand_scale"] == 1.05
    assert (run / "snapshot/projects/my_study/scenarios.yaml").read_bytes() == (
        project / "scenarios.yaml"
    ).read_bytes()
    # Subsequent project edits must not change a replay.
    (project / "scenarios.yaml").write_text(
        "high_demand:\n  framework:\n    demand_scale: 0.95\n"
    )
    replay = reproduce(run)
    assert json.loads((replay / "meta.json").read_text())["project"] == "my_study"
    assert json.loads((replay / "reproduction.json").read_text())[
        "all_series_within_tolerance"
    ]


def test_reference_against_extracted_demand_fixture(runs):
    """Fixed-demand extraction checks belong in tests, not runtime inputs."""
    fixtures = pd.read_csv(ROOT / "tests/fixtures/benchmarks.csv")
    table = pd.read_csv(runs["reference"] / "report/iamc_long.csv")
    names = {
        "final_energy_other_industry": "Teaching|Final Energy|Industry excluding Steel",
        "final_energy_transport": "Final Energy|Transportation",
        "final_energy_building": "Final Energy|Residential and Commercial",
        "steel_products": "Teaching|Production|Finished Steel",
    }
    for row in fixtures[fixtures.metric.isin(names)].itertuples():
        actual = table.loc[
            (table.variable == names[row.metric]) & (table.year == row.year), "value"
        ].item()
        assert np.isclose(actual, row.value, rtol=row.relative_tolerance, atol=1e-6)
