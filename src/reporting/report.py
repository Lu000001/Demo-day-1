"""Derive IAMC series from solved technology flows, never from guessed names."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json

import numpy as np
import pandas as pd
import yaml

from message.data import Data

PACKAGE = Path(__file__).resolve().parent


def activity(scenario) -> pd.DataFrame:
    """Sum vintage activity once; there is exactly one annual time label."""
    raw = scenario.var("ACT")
    return (
        raw.groupby(["technology", "year_act"], as_index=False)
        .lvl.sum()
        .rename(columns={"year_act": "year", "lvl": "activity"})
    )


def flow(data: Data, acts: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Multiply annual technology activity by a validated input/output coefficient."""
    result = data.tables[direction].merge(
        acts, on=["technology", "year"], how="left", validate="many_to_one"
    )
    if result.activity.isna().any():
        raise ValueError(f"Missing solved activity in {direction} flow accounting")
    result["flow"] = result.value * result.activity
    return result.merge(
        data.tables["technologies"], on="technology", validate="many_to_one"
    )


def series(data: Data, scenario, scenario_name: str):
    """Create the IAMC long table and the independent physical-flow audit tables."""
    config = data.config
    mapping = yaml.safe_load((PACKAGE / "mapping.yaml").read_text())
    factor = mapping["energy_conversion"]
    acts = activity(scenario)
    inflow, outflow = flow(data, acts, "input"), flow(data, acts, "output")
    values = defaultdict(float)

    def add(variable, year, value, unit):
        values[(variable, int(year), unit)] += float(value)

    def add_energy(prefix, carrier, year, value):
        add(prefix, year, value * factor, "EJ/yr")
        fuel = mapping["carriers"][carrier]
        parts = fuel.split("|")
        for n in range(1, len(parts) + 1):
            add(prefix + "|" + "|".join(parts[:n]), year, value * factor, "EJ/yr")

    final = inflow[
        (inflow.kind.isin(["final_use", "steel", "capture"]))
        & inflow.level.isin(["final", "feedstock"])
    ].copy()
    for r in final.itertuples():
        add_energy("Final Energy", r.commodity, r.year, r.flow)
        if r.level == "feedstock":
            add_energy("Final Energy|Non-Energy Use", r.commodity, r.year, r.flow)
        elif r.kind == "capture":
            add_energy("Final Energy|Carbon Management", r.commodity, r.year, r.flow)
        else:
            sector = mapping["sectors"][r.sector]
            add_energy("Final Energy|" + sector, r.commodity, r.year, r.flow)
            if r.sector == "steel":
                add_energy("Final Energy|Industry", r.commodity, r.year, r.flow)
            if r.sector == "other_industry":
                add(
                    "Teaching|Final Energy|Industry excluding Steel",
                    r.year,
                    r.flow * factor,
                    "EJ/yr",
                )
    generation = outflow[outflow.kind.isin(["power_existing", "power_new"])]
    for r in generation.itertuples():
        add("Secondary Energy|Electricity", r.year, r.flow * factor, "EJ/yr")
        add(
            "Secondary Energy|Electricity|" + r.source, r.year, r.flow * factor, "EJ/yr"
        )
    newcap = scenario.var("CAP").rename(columns={"year_act": "year"})
    newcap = newcap.merge(data.tables["technologies"], on="technology")
    for r in newcap[newcap.kind == "power_new"].itertuples():
        add("Capacity|Electricity", r.year, r.lvl, "GW")
        add("Capacity|Electricity|" + r.source, r.year, r.lvl, "GW")
    for r in data.tables["existing_capacity"].itertuples():
        add("Capacity|Electricity", r.year, r.value, "GW")
        add("Capacity|Electricity|" + r.source, r.year, r.value, "GW")
    steel = outflow[outflow.kind == "steel"]
    for r in steel.itertuples():
        if r.commodity == "crude_steel":
            add("Production|Iron and Steel|Steel", r.year, r.flow, "Mt/yr")
            label = "BOF" if r.technology == "steel_making_bof" else "Scrap EAF"
            add("Teaching|Production|Crude Steel|" + label, r.year, r.flow, "Mt/yr")
        elif r.commodity == "steel_products":
            add("Teaching|Production|Finished Steel", r.year, r.flow, "Mt/yr")
        elif r.commodity == "pig_iron":
            add("Production|Iron and Steel|Iron|Pig Iron", r.year, r.flow, "Mt/yr")
    emissions = data.tables["emission_factor"].merge(acts, on=["technology", "year"])
    emissions["emissions"] = emissions.value * emissions.activity
    for r in emissions.itertuples():
        add("Emissions|CO2", r.year, r.emissions, "Mt CO2/yr")
        if r.emissions >= 0:
            add("Gross Emissions|CO2", r.year, r.emissions, "Mt CO2/yr")
    for y in data.years:
        captured = outflow.loc[
            (outflow.commodity == "CO2_captured") & (outflow.year == y), "flow"
        ].sum()
        stored = inflow.loc[
            (inflow.technology == "co2_storage") & (inflow.year == y), "flow"
        ].sum()
        add("Carbon Capture", y, captured, "Mt CO2/yr")
        add("Carbon Capture|Geological Storage", y, stored, "Mt CO2/yr")
        # Explicit zero series are useful for comparing the no-CCS scenario.
        add("Final Energy|Carbon Management", y, 0, "EJ/yr")
        add("Final Energy|Carbon Management|Electricity", y, 0, "EJ/yr")
    rows = [
        dict(
            model=config["model_name"],
            scenario=scenario_name,
            region=data.region,
            variable=v,
            unit=u,
            year=y,
            value=value,
        )
        for (v, y, u), value in sorted(values.items())
    ]
    return pd.DataFrame(rows), acts, inflow, outflow, emissions


def validate_iamc(table: pd.DataFrame, definitions: Path) -> None:
    """Validate exact variable names and units against a frozen IAMC subset."""
    definitions = yaml.safe_load(definitions.read_text())
    codes = {key: value for row in definitions for key, value in row.items()}
    if table.duplicated(
        ["model", "scenario", "region", "variable", "unit", "year"]
    ).any():
        raise ValueError("Duplicate IAMC coordinate")
    if not np.isfinite(table.value).all():
        raise ValueError("Non-finite IAMC values")
    for variable, unit in (
        table[["variable", "unit"]].drop_duplicates().itertuples(index=False)
    ):
        if variable not in codes or unit != codes[variable]["unit"]:
            raise ValueError(
                f"Undefined IAMC variable or wrong unit: {variable} [{unit}]"
            )


def audit(data, table, inflow, outflow, emissions, scenario):
    """Check energy/material equality, net emissions, capture, and data-scale fidelity."""
    keys = ["commodity", "level", "year"]
    balance = (
        outflow.groupby(keys)
        .flow.sum()
        .subtract(inflow.groupby(keys).flow.sum(), fill_value=0)
    )
    demands = data.tables["demand"].groupby(keys).value.sum() * data.demand_scale
    residual = balance.subtract(demands, fill_value=0)
    balance_table = (
        pd.DataFrame(
            {"supply_minus_use": balance, "demand": demands, "residual": residual}
        )
        .fillna(0)
        .reset_index()
    )
    tolerance = 1e-6 * np.maximum(1, np.abs(balance_table.demand))
    if (balance_table.residual.abs() > tolerance).any():
        raise ValueError("Commodity accounting does not close")
    result = {
        "commodity_balance_max_residual": float(residual.abs().max()),
        "net_emissions_checked": True,
        "capture_storage_checked": True,
    }
    raw = scenario.var("EMISS")
    net = (
        raw[
            (raw.type_tec == "all")
            & (raw.emission == "CO2")
            & (raw.node == data.region)
        ]
        .groupby("year")
        .lvl.sum()
    )
    computed = emissions.groupby("year").emissions.sum()
    if not np.allclose(net.reindex(computed.index), computed, rtol=1e-8, atol=1e-5):
        raise ValueError("Reported emissions do not match MESSAGEix EMISS")
    # Reconcile modeled demand directly. Historical extraction benchmarks live
    # in tests/fixtures and do not determine a scenario's runtime checks.
    comparisons = data.tables["demand"][keys + ["unit", "value"]].copy()
    comparisons = comparisons.rename(columns={"value": "reference"})
    comparisons["reference"] *= data.demand_scale
    comparisons = comparisons.merge(
        balance.rename("result").reset_index(), on=keys, validate="one_to_one"
    )
    comparisons["difference"] = comparisons.result - comparisons.reference
    comparisons["passed"] = np.isclose(
        comparisons.result, comparisons.reference, rtol=1e-6, atol=1e-6
    )
    if not comparisons.passed.all():
        raise ValueError("Exogenous-demand reconstruction failed")
    captures = table.loc[table.variable == "Carbon Capture"].set_index("year").value
    storage = (
        table.loc[table.variable == "Carbon Capture|Geological Storage"]
        .set_index("year")
        .value
    )
    if not np.allclose(
        captures.sort_index(), storage.sort_index(), rtol=1e-8, atol=1e-6
    ):
        raise ValueError("Captured carbon does not match geological storage")
    result["fixed_demand_checks_passed"] = True
    return result, balance_table, comparisons


def report(data: Data, scenario, scenario_name: str, run: Path) -> dict:
    """Write raw variables, standardized tables, a physical audit, and figures."""
    import pyam

    folder = run / "report"
    folder.mkdir()
    table, acts, ins, outs, emissions = series(data, scenario, scenario_name)
    validate_iamc(table, PACKAGE / "definitions.yaml")
    checks, balance, comparison = audit(data, table, ins, outs, emissions, scenario)
    table.to_csv(folder / "iamc_long.csv", index=False)
    iam = pyam.IamDataFrame(table)
    components = [
        "Final Energy|Industry",
        "Final Energy|Transportation",
        "Final Energy|Residential and Commercial",
        "Final Energy|Non-Energy Use",
        "Final Energy|Carbon Management",
    ]
    if (
        iam.check_aggregate("Final Energy", components=components, rtol=1e-8, atol=1e-8)
        is not None
    ):
        raise ValueError("IAMC final-energy sector aggregates are inconsistent")
    iam.to_csv(folder / "iamc.csv")
    iam.to_excel(folder / "iamc.xlsx")
    for name, frame in [
        ("activity", acts),
        ("input_flows", ins),
        ("output_flows", outs),
        ("emissions", emissions),
        ("commodity_balance", balance),
        ("reconciliation", comparison),
    ]:
        frame.to_csv(folder / f"{name}.csv", index=False)
    for name in ["ACT", "CAP", "EMISS", "PRICE_COMMODITY"]:
        scenario.var(name).to_csv(folder / f"{name}.csv", index=False)
    (folder / "validation.json").write_text(json.dumps(checks, indent=2))
    from .plots import plot

    plot(table, folder / "figures")
    return checks
