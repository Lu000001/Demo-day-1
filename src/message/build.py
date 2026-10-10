"""Load declared structure and expand annual coefficients into MESSAGEix indices.

Only this adapter supplies ``time='year'`` and investment/activity year pairs.
For parameters with both year axes, a year column describes the activity year:
all surviving vintages use that year's coefficient, as in the original Demo.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from .data import Data


def expand_parameter(data: Data, name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Add annual time labels and expand calendar-year values over vintages.

    A one-axis parameter, such as investment cost, uses its own year axis.
    A two-axis parameter, such as input efficiency or variable cost, takes the
    activity-year value for each vintage no later than that activity year.
    MESSAGEix applies technical lifetimes when constructing the active model.
    """
    from message_ix.models import MESSAGE

    item = MESSAGE.items[name]
    indices = item.dims or item.coords
    rows = []
    for record in frame.to_dict("records"):
        year = int(record["year"])
        vintages = (
            [v for v in data.years if v <= year]
            if "year_vtg" in indices and "year_act" in indices
            else [year]
        )
        for vintage in vintages:
            row = {}
            for dim in indices:
                if dim.startswith("time"):
                    row[dim] = "year"
                elif dim == "year_vtg":
                    row[dim] = vintage
                elif dim.startswith("year"):
                    row[dim] = year
                else:
                    row[dim] = record[dim]
            rows.append(dict(**row, value=record["value"], unit=record["unit"]))
    return pd.DataFrame(rows, columns=[*indices, "value", "unit"])


def build(data: Data, database: Path, name: str):
    """Create a private database; load all sets before categories, maps and data.

    Returns the platform and scenario; callers close the platform even when
    solving or reporting fails. No default ixmp platform is modified.
    """
    import ixmp
    import message_ix

    cfg = data.config
    database.parent.mkdir(parents=True, exist_ok=True)
    mp = ixmp.Platform(backend="jdbc", driver="hsqldb", path=str(database.resolve()))
    try:
        s = message_ix.Scenario(
            mp, model=cfg["model_name"], scenario=name, version="new"
        )
        s.add_horizon(
            year=data.years,
            firstmodelyear=cfg["framework"]["horizon"]["first_model_year"],
        )
        # Framework, all base sectors, and enabled addons have already been
        # collected. Referenced symbols therefore exist before links are loaded.
        for set_name, frame in data.sets.items():
            if set_name not in {"addon", "balance_equality"}:
                s.add_set(set_name, frame.name.tolist())
        if "addon" in data.sets:
            s.add_set("addon", data.sets["addon"].name.tolist())
        if "balance_equality" not in s.set_list():
            s.init_set("balance_equality", idx_sets=["commodity", "level"])
        s.add_set(
            "balance_equality", data.sets["balance_equality"][["commodity", "level"]]
        )
        for set_name, frame in data.categories.items():
            for category, members in frame.groupby("category", sort=False):
                s.add_cat(set_name, category, members.name.tolist())
        for set_name, frame in data.maps.items():
            s.add_set("map_" + set_name, frame)
        for year in data.years:
            s.add_cat("year", str(year), [year])
        units = {"-", "y", "CNY/t CO2"}
        for frame in data.tables.values():
            if "unit" in frame:
                units.update(frame.unit)
        for unit in sorted(units):
            mp.add_unit(unit)
        s.add_par(
            "duration_period",
            pd.DataFrame(
                [
                    dict(year=year, value=data.period_length, unit="y")
                    for year in data.years
                ]
            ),
        )
        for par_name, frame in data.parameters.items():
            if par_name == "demand":
                frame = frame.assign(value=frame.value * data.demand_scale)
            s.add_par(par_name, expand_parameter(data, par_name, frame))
        for year, price in cfg["framework"]["policies"]["carbon_price"].items():
            s.add_par(
                "tax_emission",
                [data.region, "CO2", "all", str(year)],
                price,
                "CNY/t CO2",
            )
        s.commit("Annual teaching scenario; inputs captured in run snapshot")
        return mp, s
    except BaseException:
        mp.close_db()
        raise
