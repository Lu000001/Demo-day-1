"""Resolve a scenario and validate the exact annual CSV files it consumes."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import re

import numpy as np
import pandas as pd
import yaml


def merge(base: dict, override: dict) -> dict:
    """Recursively merge dictionaries; lists and scalar values replace entirely."""
    result = deepcopy(base)
    for key, value in override.items():
        result[key] = (
            merge(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else deepcopy(value)
        )
    return result


def project_scenarios(root: Path, project: str = "course") -> dict:
    """Read overrides from ``projects/<project>/scenarios.yaml``.

    Project and scenario names are used in paths. Use letters, digits, hyphens
    and underscores, starting with a letter or digit.
    """
    pattern = r"[A-Za-z0-9][A-Za-z0-9_-]*"
    if not re.fullmatch(pattern, project):
        raise ValueError(f"Invalid project name: {project!r}")
    path = root / "projects" / project / "scenarios.yaml"
    if not path.is_file():
        raise ValueError(f"Project scenarios not found: {path}")
    scenarios = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError(f"Expected a non-empty mapping of scenarios in {path}")
    for name, override in scenarios.items():
        if not isinstance(name, str) or not re.fullmatch(pattern, name):
            raise ValueError(f"Invalid scenario name in {path}: {name!r}")
        if override is not None and not isinstance(override, dict):
            raise ValueError(f"Scenario {name!r} must contain a mapping of overrides")
    return scenarios


def resolve(
    root: Path,
    scenario: str = "reference",
    config_path: Path | None = None,
    *,
    project: str = "course",
) -> dict:
    """Merge one project's scenario into the base configuration independently."""
    base = yaml.safe_load(
        (config_path or root / "config.yaml").read_text(encoding="utf-8")
    )
    scenarios = project_scenarios(root, project)
    if scenario not in scenarios:
        raise ValueError(
            f"Unknown scenario {scenario!r} in project {project!r}; available: {list(scenarios)}"
        )
    return merge(base, scenarios[scenario] or {})


def sha256(path: Path) -> str:
    """Hash bytes, not timestamps, for input versioning."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Data:
    """Validated module tables, with an explicit list of files actually read.

    Parameters
    ----------
    root : pathlib.Path
        Repository or run-snapshot root.
    config : dict
        Fully resolved scenario configuration.

    The folder layout determines ownership: every base sector is loaded, and
    ``addons.<sector>.<name>`` controls optional extensions. CSV year columns
    become a long table in memory; the model adapter adds annual time indices.
    ``files`` records both input tables and module descriptions for snapshots.
    """

    def __init__(self, root: Path, config: dict):
        self.root, self.config = root, config
        self.files: list[Path] = []
        self.sets: dict[str, pd.DataFrame] = {}
        self.categories: dict[str, pd.DataFrame] = {}
        self.maps: dict[str, pd.DataFrame] = {}
        self.parameters: dict[str, pd.DataFrame] = {}
        self.tables: dict[str, pd.DataFrame] = {}
        self._configure()
        self._load_folder(root / "data/framework")
        sectors = sorted(
            p
            for p in (root / "data/modules").iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )
        self.modules = [p.name for p in sectors]
        flags = config.get("addons", {})
        if set(flags) - set(self.modules):
            raise ValueError(f"Unknown addon sectors: {set(flags) - set(self.modules)}")
        for sector in sectors:
            self._description(sector)
            self._load_folder(sector, sector.name)
            addons = sorted(p for p in (sector / "addons").glob("*") if p.is_dir())
            choices = flags.get(sector.name, {})
            if not isinstance(choices, dict) or set(choices) - {p.name for p in addons}:
                raise ValueError(f"Unknown addon configuration for {sector.name}")
            for addon in addons:
                # Retain the description even when disabled, so snapshots can
                # discover the option without copying or loading inactive CSVs.
                self._description(addon)
                enabled = choices.get(addon.name, False)
                if not isinstance(enabled, bool):
                    raise ValueError(
                        f"addons.{sector.name}.{addon.name} must be true or false"
                    )
                if enabled:
                    self._load_folder(addon, sector.name)
        self.tables.update(self.parameters)
        self.tables["technologies"] = self.sets["technology"].rename(
            columns={"name": "technology"}
        )
        self.validate()
        self.region = self.sets["node"].iloc[0]["name"]

    def _configure(self):
        """Derive periods from the four horizon fields; reject obsolete settings."""
        c = self.config
        if set(c) - {"model_name", "framework", "addons", "solver"}:
            raise ValueError(
                "Use framework.horizon, framework.policies and addons; obsolete or unknown root settings are not accepted"
            )
        framework = c["framework"]
        if set(framework) != {"horizon", "demand_scale", "policies"}:
            raise ValueError(
                "framework must contain horizon, demand_scale and policies"
            )
        horizon = framework["horizon"]
        if set(horizon) != {
            "year_start",
            "year_end",
            "year_step",
            "first_model_year",
        } or any(type(v) is not int for v in horizon.values()):
            raise ValueError("Specify four integer framework.horizon fields")
        start, end, step = (horizon[k] for k in ["year_start", "year_end", "year_step"])
        if (
            step <= 0
            or end < start
            or (end - start) % step
            or horizon["first_model_year"] != start
        ):
            raise ValueError(
                "Use equally spaced periods with first_model_year = year_start; historical periods are not implemented in this Demo"
            )
        self.years = list(range(start, end + 1, step))
        self.period_length = step
        self.demand_scale = framework["demand_scale"]
        if (
            not isinstance(self.demand_scale, (int, float))
            or not np.isfinite(self.demand_scale)
            or self.demand_scale <= 0
        ):
            raise ValueError("framework.demand_scale must be positive and finite")
        policies = framework["policies"]
        if set(policies) != {"carbon_price"}:
            raise ValueError(
                "framework.policies contains carbon_price; technology options belong in addons"
            )
        prices = policies["carbon_price"]
        if (
            not isinstance(prices, dict)
            or set(prices) != set(self.years)
            or any(
                not isinstance(v, (int, float)) or not np.isfinite(v) or v < 0
                for v in prices.values()
            )
        ):
            raise ValueError(
                "Specify a finite, non-negative carbon price for each model year"
            )
        if not isinstance(c.get("addons", {}), dict):
            raise ValueError("addons must be a mapping of sectors to options")
        if str(c["solver"]["name"]).lower() not in {"highs", "cplex", "gurobi"}:
            raise ValueError(
                "solver.name must be highs, cplex, or gurobi; GAMS is the runtime"
            )

    def _read(self, path: Path) -> pd.DataFrame:
        self.files.append(path)
        frame = pd.read_csv(path)
        if frame.empty or frame.isna().any().any():
            raise ValueError(
                f"Empty table or missing values in {path}; zero must be explicit"
            )
        return frame

    def _description(self, folder: Path):
        path = folder / "module.yaml"
        self.files.append(path)
        description = yaml.safe_load(path.read_text())
        if description.get("name") != folder.name or set(description) - {
            "name",
            "description",
        }:
            raise ValueError(
                f"Expected name and optional description in {path}; table lists are unnecessary"
            )

    def _annual(self, path: Path) -> pd.DataFrame:
        frame = self._read(path)
        years = [col for col in frame if col.isdigit()]
        expected = [str(y) for y in self.years]
        if set(years) != set(expected):
            raise ValueError(
                f"Year columns in {path} must cover exactly {expected}; missing years never mean zero"
            )
        if any(col.startswith("time") for col in frame):
            raise ValueError(
                f"Annual time indices are supplied by the adapter, not {path}"
            )
        indices = [col for col in frame if col not in years]
        result = frame.melt(
            id_vars=indices, value_vars=expected, var_name="year", value_name="value"
        )
        result["year"] = result.year.astype(int)
        result["value"] = pd.to_numeric(result.value, errors="raise")
        if not np.isfinite(result.value).all():
            raise ValueError(f"Non-finite values in {path}")
        return result

    @staticmethod
    def _append(tables, name, frame):
        tables[name] = (
            pd.concat([tables[name], frame], ignore_index=True)
            if name in tables
            else frame
        )

    def _load_folder(self, folder: Path, sector: str | None = None):
        """Read explicit declarations, then wide parameter tables from one owner."""
        from message_ix.models import MESSAGE

        allowed = {"sets", "categories", "maps", "parameters", "assumptions", "addons"}
        for child in folder.iterdir():
            if (child.is_dir() and child.name not in allowed) or (
                child.is_file() and child.suffix == ".csv"
            ):
                raise ValueError(f"Unexpected input location: {child}")
        for path in sorted((folder / "sets").glob("*.csv")):
            name = path.stem
            if name not in {
                "node",
                "commodity",
                "level",
                "mode",
                "emission",
                "technology",
                "addon",
                "type_addon",
                "balance_equality",
            }:
                raise ValueError(f"Unsupported set: {path}")
            frame = self._read(path)
            if name == "technology":
                frame["module"] = sector
            self._append(self.sets, name, frame)
        for kind, tables, names in [
            ("categories", self.categories, {"emission", "addon"}),
            ("maps", self.maps, {"tec_addon"}),
        ]:
            for path in sorted((folder / kind).glob("*.csv")):
                if path.stem not in names:
                    raise ValueError(f"Unsupported {kind}: {path}")
                self._append(tables, path.stem, self._read(path))
        for path in sorted((folder / "parameters").glob("*.csv")):
            item = MESSAGE.items.get(path.stem)
            if (
                item is None
                or item.type.name != "PAR"
                or "year" not in item.coords
                or path.stem in {"duration_period", "tax_emission"}
            ):
                raise ValueError(
                    f"Unsupported annual parameter (or generated from configuration): {path}"
                )
            self._append(self.parameters, path.stem, self._annual(path))
        for path in sorted((folder / "assumptions").glob("*.csv")):
            if path.stem != "existing_capacity":
                raise ValueError(f"Unsupported reporting assumption: {path}")
            # This reporting table retains separate capacity and availability
            # columns, both of which can vary by year. It is not a parameter.
            self._append(self.tables, path.stem, self._read(path))

    def validate(self) -> None:
        """Check explicit declarations, parameter indices, units and flow connections."""
        from message_ix.models import MESSAGE

        required_sets = {
            "node",
            "technology",
            "commodity",
            "level",
            "mode",
            "emission",
            "balance_equality",
        }
        if required_sets - self.sets.keys():
            raise ValueError(f"Missing sets: {required_sets - self.sets.keys()}")
        for name, frame in self.sets.items():
            keys = ["commodity", "level"] if name == "balance_equality" else ["name"]
            if (
                not set(keys) <= set(frame)
                or frame[keys].isna().any().any()
                or frame.duplicated(keys).any()
            ):
                raise ValueError(f"Missing or duplicate set indices in {name}")
        if self.sets["node"].name.tolist() != ["China"]:
            raise ValueError("This Demo uses one China node")
        if self.sets["mode"].name.tolist() != ["standard"] or self.sets[
            "emission"
        ].name.tolist() != ["CO2"]:
            raise ValueError("This Demo uses mode=standard and emission=CO2")
        tecs = self.tables["technologies"]
        if (
            not {
                "kind",
                "activity_unit",
                "sector",
                "carrier",
                "source",
                "description",
                "module",
            }
            <= set(tecs)
            or tecs.isna().any().any()
        ):
            raise ValueError("Technology sets must include the reporting metadata")

        def check(values, set_name, context):
            known = set(self.sets[set_name]["name"]) if set_name in self.sets else set()
            missing = set(values) - known
            if missing:
                raise ValueError(
                    f"Undeclared {set_name} in {context}: {sorted(missing)}"
                )

        for dim in ["commodity", "level"]:
            check(self.sets["balance_equality"][dim], dim, "balance_equality")
        if "addon" in self.sets:
            check(self.sets["addon"].name, "technology", "addon")
        for name, frame in self.categories.items():
            if set(frame) != {"category", "name"} or frame.duplicated().any():
                raise ValueError(f"Invalid category table: {name}")
            check(frame.name, name, f"categories/{name}")
            if name == "addon":
                check(frame.category, "type_addon", "categories/addon")
        for name, frame in self.maps.items():
            item = MESSAGE.items["map_" + name]
            dims = item.dims or item.coords
            if set(frame) != set(dims) or frame.duplicated().any():
                raise ValueError(f"Invalid map indices in {name}")
            for dim, coord in zip(dims, item.coords):
                check(frame[dim], coord, name)
        required_parameters = {
            "input",
            "output",
            "demand",
            "interestrate",
            "capacity_factor",
            "emission_factor",
        }
        if required_parameters - self.parameters.keys():
            raise ValueError(
                f"Missing parameters: {required_parameters - self.parameters.keys()}"
            )
        for name, frame in self.parameters.items():
            item = MESSAGE.items[name]
            pairs = [
                (dim, coord)
                for dim, coord in zip(item.dims or item.coords, item.coords)
                if coord not in {"year", "time"}
            ]
            keys = [dim for dim, _ in pairs] + ["year"]
            metadata = {"sector", "carrier"} if name == "demand" else set()
            if set(frame) != set(keys) | {"unit", "value"} | metadata:
                raise ValueError(
                    f"Expected indices {keys}, unit/value and {sorted(metadata)} in {name}; found {list(frame)}"
                )
            if frame.isna().any().any() or frame.duplicated(keys).any():
                raise ValueError(
                    f"Missing values or duplicate parameter index in {name}"
                )
            for dim, coord in pairs:
                check(frame[dim], coord, name)
            if name != "emission_factor" and (frame.value < 0).any():
                raise ValueError(f"Negative values in {name}")
            # Units may differ between energy and material technologies, but
            # must be consistent for the same coordinate across model years.
            index = [k for k in keys if k != "year"]
            if index and not (frame.groupby(index).unit.nunique() == 1).all():
                raise ValueError(f"Units change between years in {name}")
        if (
            not self.parameters["capacity_factor"]
            .value.between(0, 1, inclusive="right")
            .all()
        ):
            raise ValueError("Capacity factors must lie in (0, 1]")
        if not (self.parameters["interestrate"].value > 0).all():
            raise ValueError("Interest rates must be positive")
        for name in ["input", "output"]:
            if not (self.parameters[name].value > 0).all():
                raise ValueError(f"All {name} coefficients must be positive")
        sources = set(zip(self.tables["output"].commodity, self.tables["output"].level))
        sinks = set(zip(self.tables["input"].commodity, self.tables["input"].level))
        sinks |= set(zip(self.tables["demand"].commodity, self.tables["demand"].level))
        if sinks - sources:
            raise ValueError(f"Commodities without suppliers: {sinks - sources}")
        equalities = set(
            self.sets["balance_equality"].itertuples(index=False, name=None)
        )
        if (sources | sinks) - equalities:
            raise ValueError(
                "Declare balance_equality for every active commodity-level pair in this Demo"
            )
        capacity = self.tables["existing_capacity"]
        check(capacity.technology, "technology", "existing_capacity")
        if (
            set(capacity.year) != set(self.years)
            or not (
                capacity.groupby("technology").year.nunique() == len(self.years)
            ).all()
        ):
            raise ValueError("Incomplete existing capacity year coverage")
        if (
            capacity.duplicated(["technology", "year"]).any()
            or not capacity.capacity_factor.between(0, 1, inclusive="right").all()
            or (capacity.value < 0).any()
        ):
            raise ValueError("Invalid existing capacity assumptions")
        bounds = (
            self.parameters["bound_activity_up"].set_index(["technology", "year"]).value
        )
        expected = capacity.set_index(["technology", "year"]).eval(
            "value * capacity_factor"
        )
        if not np.allclose(
            bounds.reindex(expected.index), expected, rtol=1e-8, atol=1e-8
        ):
            raise ValueError(
                "Existing power capacity does not match the generation bounds"
            )

    def manifest(self) -> dict[str, str]:
        """Return relative input paths and their SHA-256 hashes."""
        return {str(p.relative_to(self.root)): sha256(p) for p in sorted(self.files)}
