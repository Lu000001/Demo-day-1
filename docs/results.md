# Scenarios and Results

A scenario changes assumptions, then solves the same model again. Start with the three examples in `projects/course/scenarios.yaml`, compare their results, and create your own project when you are ready.

## Run and compare the supplied scenarios

| Scenario | Carbon price, 2030 / 2035 (CNY/t CO₂) | CCS |
| --- | --- | --- |
| `reference` | 100 / 150 | Available |
| `carbon_price` | 800 / 1200 | Available |
| `no_ccs` | 800 / 1200 | Disabled |

```bash
python -m tools.cli run --project course --all
```

The command prints a separate directory under `runs/` for each case. Use `--scenario reference` instead of `--all` to run just one case. Repeated runs create new directories.

| What to open inside a run | What you will find |
| --- | --- |
| `report/iamc.xlsx` | Result tables for Excel, with scenario, variable, unit and year. |
| `report/figures/` | Charts of generation, energy use, emissions and steel production. |
| `report/iamc.csv` | The same result series in CSV form for your own analysis. |
| `report/validation.json` | Checks of the solved energy and material balances. |

```{figure} _static/figures/emissions-comparison.png
:alt: Net CO2 emissions in 2035: reference 7114, carbon_price 6097, and no_ccs 6462 Mt CO2 per year.
:target: _static/figures/emissions-comparison.png
:figclass: results-diagram

Example outputs for 2035, rounded to whole Mt CO₂/yr. The two high-price scenarios use the same carbon prices. These are illustrative model results, not a national forecast.
```

Higher carbon prices change power generation and make steel CCS attractive. At the same high prices, allowing CCS lowers net emissions from about **6,462 to 6,097 Mt CO₂/yr**. The reduction is about 365 Mt, while 400 Mt is captured: capture uses electricity, and choices elsewhere in the energy system also change.

To compare your own runs, replace the placeholders with the directories printed by the command above:

```bash
python -m tools.cli compare runs/<reference-run> runs/<carbon-price-run> runs/<no-ccs-run>
```

Open `runs/comparison/figures/` for the comparison charts. Choose one run per scenario; use distinct scenario names when comparing different projects. The chart above is reused from the project presentation and checked against saved runs with the current default inputs and calculation logic.

<details class="doc-details">
<summary>Read results with pyam and interpret the indicators</summary>

```python
import pyam

results = pyam.IamDataFrame("runs/<reference-run>/report/iamc.csv")
print(results.filter(variable="Emissions|CO2", year=2035).data)
```

<p>Use the actual run directory in the path. IAMC tables identify each value by model, scenario, region, variable, unit and year.</p>
<ul>
<li><code>Secondary Energy|Electricity</code> is generation; final electricity excludes grid losses.</li>
<li><code>Production|Iron and Steel|Steel</code> is crude steel. <code>Teaching|Production|Finished Steel</code> is the finished product that meets demand.</li>
<li><code>Carbon Capture</code> is captured CO₂; <code>Emissions|CO2</code> is net emissions from the modeled activities.</li>
<li>Coke used as a reducing agent is reported under <code>Final Energy|Non-Energy Use</code>; capture electricity is under <code>Final Energy|Carbon Management</code>.</li>
<li>Do not add a total to its components: steel final energy is already included in industry final energy.</li>
</ul>
<p>The CSV files <code>commodity_balance.csv</code> and <code>reconciliation.csv</code> check commodity balances and demand delivery, including any demand scaling. These results cover the model's activities, not a complete national emissions inventory.</p>
</details>

## Change assumptions in your own project

Create `projects/my_study/` and save this as `scenarios.yaml` inside it:

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

`high_demand` raises every demand by 5%, including steel-product demand. `high_price_no_ccs` sets higher carbon prices and removes the steel CCS addon. Each case inherits `config.yaml` independently; settings do not carry over from the previous scenario.

```bash
python -m tools.cli validate --project my_study --all
python -m tools.cli run --project my_study --all
```

Results are written to `runs/my_study_<scenario>_<UTC>_<id>/`. Keep project and scenario names to letters, digits, hyphens and underscores, starting with a letter or digit. Projects share the code and input tables, so you do not need to copy the whole model.

For a different base configuration, copy the complete `config.yaml` to your project and pass `--config projects/my_study/config.yaml` to `validate` and `run`. The file is used only when you select it explicitly.

## Reproduce or share a run

Every run saves its code, inputs and resolved settings in `snapshot/`. `meta.json` records the scenario, solver and objective; `run.log` records what happened. This keeps a result tied to the assumptions that produced it.

Replace `<reference-run>` with an actual directory name:

```bash
python -m tools.cli reproduce runs/<reference-run>
```

Reproduction verifies the snapshot, runs it in a new directory, and compares the objective and all reported series with the original. The checks are saved in `reproduction.json`; the original run stays intact.

To share a reproducible run:

```bash
python -m tools.cli archive runs/<reference-run> --output dist/reference-run.zip
```

The archive keeps the files needed for reproduction and excludes disposable working files. To share the project without generated results or installed environments, use `python -m tools.cli export-course`; it writes `dist/MESSAGEix-China-Demo.zip`.
