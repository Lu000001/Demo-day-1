# Scenarios and Results

## Run the supplied cases

The definitions are in `projects/course/scenarios.yaml`:

| Scenario | Carbon price in 2030 / 2035 (CNY/t CO₂) | CCS |
| --- | --- | --- |
| `reference` | 100 / 150 | Allowed |
| `carbon_price` | 800 / 1200 | Allowed |
| `no_ccs` | 800 / 1200 | Disabled |

These are illustrative assumptions. All cases use the same demands and base technology data. Comparing `reference` with `carbon_price` shows the response to a higher carbon price when CCS is available. Comparing `carbon_price` with `no_ccs` isolates the option to use CCS at the same prices.

```bash
python -m tools.cli run --project course --all
```

To run one case, use `--scenario reference` instead of `--all`. `course` is the default project, so `python -m tools.cli run --all` also runs these three cases. Each run creates a separate directory and prints its path; repeated runs preserve earlier results.

## Create a project

Projects share model code and input tables. Create a folder named `projects/my_study/` and save this as its `scenarios.yaml`:

```yaml
reference: {}

high_demand:
  framework:
    demand_scale: 1.05

high_price_no_ccs:
  framework:
    policies:
      carbon_price:
        2030: 800
        2035: 1200
  addons:
    demand_industry_steel:
      ccs: false
```

Each scenario independently overrides the root `config.yaml`, not another scenario. `high_demand` increases every exogenous demand by 5%, including steel-product demand. `high_price_no_ccs` sets prices in CNY/t CO₂ and disables the steel capture and storage extension while retaining all base sectors; capture and storage are then reported as zero. Carbon prices must cover both model years.

```bash
python -m tools.cli validate --project my_study --all
python -m tools.cli run --project my_study --all
```

Results appear under `runs/my_study_<scenario>_<UTC>_<id>/`. Use letters, digits, hyphens and underscores for project and scenario names, starting with a letter or digit.

For a project-specific base, copy `config.yaml` to `projects/my_study/config.yaml` and pass `--config projects/my_study/config.yaml` to `doctor`, `validate` or `run`. This must be a complete base configuration; `scenarios.yaml` supplies the overrides. Creating the file does not automatically select it. Adding years, regions or technologies also requires corresponding data and potentially code changes; see [Model Structure](model.md).

## Read a run

Start with `report/iamc.xlsx` and the charts in `report/figures/`. Each run also retains the inputs and code needed for reproduction:

```text
runs/course_reference_<UTC>_<id>/
  meta.json                 project, scenario, status, objective and solve details
  run.log                   diagnostic log
  snapshot/                 exact source, inputs and resolved configuration
    src/                    code used for this run
    projects/course/        saved scenario definitions
  manifest.json             snapshot file hashes
  environment.json          software versions
  solution.gdx              raw optimization solution
  report/
    iamc.xlsx               results for reading in Excel
    iamc.csv                IAMC table with year columns
    iamc_long.csv           table with year and value columns
    validation.json         physical and reporting checks
    commodity_balance.csv   commodity balance residuals
    reconciliation.csv      configured demands versus modeled supply minus use
    figures/                generated charts
```

IAMC tables identify values by model, scenario, region, variable, unit and year. Use pyam to select and analyze reported series, replacing `<reference-run>` with an actual directory name:

```python
import pyam

results = pyam.IamDataFrame("runs/<reference-run>/report/iamc.csv")
print(results.filter(variable="Emissions|CO2").data)
```

The reporting conventions are:

- `Secondary Energy|Electricity|*` reports generation; final electricity consumption excludes grid losses.
- Coke used as a reducing agent is included in `Final Energy|Non-Energy Use`. Capture electricity is included in `Final Energy|Carbon Management`.
- `Production|Iron and Steel|Steel` reports crude steel. Defined `Teaching|` variables distinguish finished products and production routes.
- `Carbon Capture` and `Carbon Capture|Geological Storage` are positive flows. `Emissions|CO2` is net of capture and covers only modeled activities.

The validation and balance files check energy and material balances, capture–storage reconciliation, each configured demand and reporting consistency. `reconciliation.csv` includes any demand scaling. Reported China totals are not a complete national emissions inventory; see the [model boundaries](model.md).

## Compare scenarios

Replace the placeholders with the directories printed by your run commands; do not type the angle brackets literally:

```bash
python -m tools.cli compare runs/<reference-run> runs/<carbon-price-run> runs/<no-ccs-run>
```

Open `runs/comparison/figures/` for charts and `runs/comparison/iamc_long.csv` for combined data. Select another output directory with `--output`. Select one run per scenario; compare projects separately if their scenario names overlap, or give the scenarios distinct names.

The supplied assumptions were verified to produce these mechanisms: higher carbon prices change power investment and generation and make steel CCS attractive; capture reaches the storage throughput limit. Disabling CCS at those same prices increases net emissions and system costs. Non-steel demand remains fixed, and scrap availability constrains steel production routes, so some outputs change little.

Use your outputs to examine which electricity sources change, whether captured CO₂ equals stored CO₂, and why net emissions reductions differ from the amount captured. Reference behavior was checked using the environment described in [Installation](installation.md).

## Reproduce and share

```bash
python -m tools.cli reproduce runs/<reference-run>
```

The command verifies snapshot hashes and executes the saved code and data in a new run. It compares the objective and all IAMC series with the original in `reproduction.json`; changes to the live project do not replace the saved assumptions or original run.

To share a reproducible run while excluding its disposable database and scratch logs:

```bash
python -m tools.cli archive runs/<reference-run> --output dist/reference-run.zip
```

To share the project itself, use `python -m tools.cli export-course`. It creates `dist/MESSAGEix-China-Demo.zip` with source, inputs, projects and documentation, excluding generated results and installed environments.
