"""Fail loudly when annual data or scenario assumptions become ambiguous."""

from copy import deepcopy
from pathlib import Path
import shutil

import pandas as pd
import pytest

from message.data import Data, merge, project_scenarios, resolve

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_data_and_boundary():
    data = Data(ROOT, resolve(ROOT))
    assert set(data.tables["demand"].year) == {2030, 2035}
    assert set(data.tables["demand"].sector) == {
        "steel",
        "other_industry",
        "building",
        "transport",
    }
    assert not any(
        "battery" in t or "dam_" in t for t in data.tables["technologies"].technology
    )
    assert set(
        data.tables["input"].query("technology=='steel_making_eaf'").commodity
    ) == {"scrap", "electricity"}
    assert "feedstock" in set(
        data.tables["input"].query("technology=='iron_making'").level
    )


def test_scenario_override_isolated():
    base = resolve(ROOT)
    original = deepcopy(base)
    modified = merge(base, {"addons": {"demand_industry_steel": {"ccs": False}}})
    assert base == original
    assert modified["framework"] == base["framework"]
    assert modified["addons"]["demand_industry_steel"]["ccs"] is False
    assert (
        resolve(ROOT, "no_ccs")["framework"]["policies"]["carbon_price"]
        == resolve(ROOT, "carbon_price")["framework"]["policies"]["carbon_price"]
    )


def test_project_selection_and_validation(tmp_path, monkeypatch, capsys):
    from tools import cli

    shutil.copytree(ROOT / "data", tmp_path / "data")
    shutil.copytree(ROOT / "projects", tmp_path / "projects")
    shutil.copy2(ROOT / "config.yaml", tmp_path / "config.yaml")
    project = tmp_path / "projects/my_study"
    project.mkdir()
    (project / "scenarios.yaml").write_text(
        "reference:\n  framework:\n    demand_scale: 1.02\nhigh_demand:\n  framework:\n    demand_scale: 1.05\n"
    )
    assert resolve(tmp_path, project="my_study")["framework"]["demand_scale"] == 1.02
    assert resolve(tmp_path)["framework"]["demand_scale"] == 1.0
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    assert cli.main(["validate", "--project", "my_study", "--all"]) == 0
    output = capsys.readouterr().out
    assert "my_study/reference" in output and "my_study/high_demand" in output
    with pytest.raises(ValueError, match="Unknown scenario"):
        resolve(tmp_path, "no_ccs", project="my_study")
    with pytest.raises(ValueError, match="not found"):
        project_scenarios(tmp_path, "missing")
    with pytest.raises(ValueError, match="Invalid project"):
        project_scenarios(tmp_path, "../course")
    (project / "scenarios.yaml").write_text("../escape: {}\n")
    with pytest.raises(ValueError, match="Invalid scenario"):
        project_scenarios(tmp_path, "my_study")


@pytest.mark.parametrize(
    "change", ["missing_year", "duplicate", "unknown_supplier", "time_column", "nan"]
)
def test_reject_corrupted_inputs(tmp_path, change):
    shutil.copytree(ROOT / "data", tmp_path / "data")
    path = tmp_path / "data/modules/demand_industry_steel/parameters/input.csv"
    df = pd.read_csv(path)
    if change == "missing_year":
        df = df.drop(columns="2035")
    elif change == "duplicate":
        df = pd.concat([df, df.iloc[[0]]])
    elif change == "unknown_supplier":
        df.loc[df.technology == "steel_making_eaf", "commodity"] = "missing_carrier"
    elif change == "time_column":
        df["time"] = "year"
    else:
        df.loc[0, "2030"] = float("nan")
    df.to_csv(path, index=False)
    with pytest.raises(ValueError):
        Data(tmp_path, resolve(ROOT))


def test_reject_uncovered_horizon():
    config = resolve(ROOT)
    config["framework"]["horizon"]["year_end"] = 2040
    config["framework"]["policies"]["carbon_price"][2040] = 200
    with pytest.raises(ValueError, match="missing years never mean zero"):
        Data(ROOT, config)


def test_sector_ownership_and_optional_addon():
    data = Data(ROOT, resolve(ROOT))
    assert set(data.modules) == {
        "supply",
        "transformation_power",
        "demand_industry_steel",
        "demand_building",
        "demand_transport",
        "demand_industry_other",
    }
    assert data.years == [2030, 2035] and data.period_length == 5
    tecs = data.tables["technologies"].set_index("technology")
    assert tecs.loc["use_building_coal", "module"] == "demand_building"
    assert tecs.loc["use_transport_diesel", "module"] == "demand_transport"
    assert tecs.loc["iron_capture", "module"] == "demand_industry_steel"
    assert data.maps["tec_addon"].to_dict("records") == [
        {"technology": "iron_making", "type_addon": "iron_capture"}
    ]
    off = Data(ROOT, resolve(ROOT, "no_ccs"))
    assert not {"iron_capture", "co2_storage"} & set(
        off.tables["technologies"].technology
    )
    assert "CO2_captured" not in set(off.sets["commodity"].name)
    assert "addon_conversion" not in off.parameters and "tec_addon" not in off.maps
    assert not any("/addons/" in str(p) and p.suffix == ".csv" for p in off.files)


def test_declared_commodity_is_required(tmp_path):
    shutil.copytree(ROOT / "data", tmp_path / "data")
    path = tmp_path / "data/framework/sets/commodity.csv"
    frame = pd.read_csv(path)
    frame[frame.name != "electricity"].to_csv(path, index=False)
    with pytest.raises(ValueError, match="Undeclared commodity"):
        Data(tmp_path, resolve(ROOT))


@pytest.mark.parametrize(
    "change", ["unknown_parameter", "duplicate_technology", "invalid_addon_map"]
)
def test_reject_ambiguous_declarations(tmp_path, change):
    shutil.copytree(ROOT / "data", tmp_path / "data")
    folder = tmp_path / "data/modules/demand_industry_steel"
    if change == "unknown_parameter":
        (folder / "parameters/input.csv").rename(folder / "parameters/imput.csv")
    elif change == "duplicate_technology":
        path = folder / "sets/technology.csv"
        frame = pd.read_csv(path)
        pd.concat([frame, frame.iloc[[0]]]).to_csv(path, index=False)
    else:
        path = folder / "addons/ccs/maps/tec_addon.csv"
        frame = pd.read_csv(path)
        frame.loc[0, "technology"] = "missing_furnace"
        frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        Data(tmp_path, resolve(ROOT))


def test_activity_year_coefficients_are_not_locked_to_vintage():
    from message.build import expand_parameter

    data = Data(ROOT, resolve(ROOT))
    costs = data.parameters["var_cost"].query("technology == 'iron_capture'")
    early = costs.loc[costs.year == 2030, "value"].item()
    late = costs.loc[costs.year == 2035, "value"].item()
    assert early != late  # This fixture distinguishes the two year conventions.
    expanded = expand_parameter(data, "var_cost", costs)
    assert expanded.query("year_vtg == 2030 and year_act == 2035").value.item() == late
    assert (expanded.year_vtg <= expanded.year_act).all()
    assert set(expanded.time) == {"year"}


@pytest.mark.parametrize(
    "override",
    [
        {"modules": ["supply"]},
        {"policy": {"ccs": False}},
        {"addons": {"demand_industry_steel": {"ccs": "false"}}},
        {"addons": {"demand_industry_steel": {"css": False}}},
        {"framework": {"horizon": {"year_step": 0}}},
    ],
)
def test_reject_invalid_or_obsolete_config(override):
    with pytest.raises(ValueError):
        Data(ROOT, merge(resolve(ROOT), override))
