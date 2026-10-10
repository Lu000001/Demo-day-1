# Data and Configuration

The Demo adapts inputs from the larger MESSAGE-China model into a small, single-region example. It keeps selected demands and technology relationships, with simplified supply, power, steel and CCS assumptions. The carbon-price paths are illustrative scenarios. All inputs needed to run this version are included in the repository.

The model reads **CSV tables** for its structure and numbers, and **YAML files** for settings and scenario changes.

## Find the data for each part of the model

```text
data/
  framework/
    sets/                      shared names: regions, commodities, levels
    categories/                shared groupings
    parameters/                demand.csv and interestrate.csv
  modules/
    supply/
    transformation_power/
    demand_building/
    demand_transport/
    demand_industry_other/
    demand_industry_steel/
      sets/                    steel technologies and commodities
      parameters/              inputs, outputs, costs and other values
      addons/ccs/              optional capture and storage extension
```

**`framework/` holds shared information.** In particular, `parameters/demand.csv` contains the required final energy for buildings, transport and other industry, plus physical demand for steel products. Demand is kept here so all sectors use the same definition of what must be supplied.

**`modules/` holds sector data.** Each base module has `sets/`, `parameters/` and a short `module.yaml` description. The loader finds all base modules automatically. The steel module also owns the optional CCS addon.

| Folder or file | Its job |
| --- | --- |
| `sets/` | Declare the names used in the tables, such as a technology or commodity. |
| `parameters/` | Store numeric values: input/output coefficients, costs, demand, capacity and other limits. |
| `categories/` and `maps/` | Group names and connect them, for example linking a blast furnace to its capture addon. |
| `module.yaml` | Name and briefly describe the module. It does not list every input file. |

To prepare or extend the data, declare the needed names, fill the parameter tables for every model year, then run `python -m tools.cli validate --all`. Validation checks names, years, units and table consistency before any solve.

## Read a technology from its CSV rows

Take the **grid** from the model diagram. Its input and output rows live in `data/modules/transformation_power/parameters/`. For the `grid` technology, these rows specify:

| Table | Commodity / level | 2030 | 2035 |
| --- | --- | --- | --- |
| `input.csv` | electricity / secondary | 1.052631579 | 1.052631579 |
| `output.csv` | electricity / final | 1 | 1 |

To deliver **1 unit of final electricity**, the grid takes about **1.053 units of secondary electricity**. Delivered electricity is 95% of the input: the remaining 5% is lost. This is how the arrow through the grid in the diagram becomes a model relationship.

The full [input table](https://github.com/SongminYu/MESSAGEix-China-Demo/blob/main/data/modules/transformation_power/parameters/input.csv) and [output table](https://github.com/SongminYu/MESSAGEix-China-Demo/blob/main/data/modules/transformation_power/parameters/output.csv) also identify the region, operating mode and unit. In this example, the region is `China`, the mode is `standard`, and the coefficients are dimensionless (`-`). Keep those columns when editing a CSV.

Most parameter tables store one row per combination of names, with values in the `2030` and `2035` columns. Both years need explicit values; a missing value is not treated as zero.

| Quantity | Unit |
| --- | --- |
| Annual energy flow | GWa in the model; EJ/yr in reports. 1 GWa = 0.031536 EJ/yr. |
| Power capacity | GW |
| Steel and material flow | Mt/yr |
| CO₂ flow | Mt CO₂/yr |
| Monetary costs | Million CNY, using the input data's currency basis |

<details class="doc-details">
<summary>How year columns and balances are used</summary>
<p>The loader reshapes year columns into MESSAGEix parameter rows. It adds one annual time label; there are no hourly or seasonal slices. Reported annual flows are not multiplied by the five-year period length.</p>
<p>Input/output coefficients and variable costs follow the year of operation. A plant built in 2030 and still operating in 2035 uses the 2035 operating coefficient. Investment costs and lifetimes follow the year of investment.</p>
<p><code>balance_equality.csv</code> declares the commodity–level pairs whose supply must equal use plus demand. The captured-CO₂ balance belongs to the CCS addon. The power module's <code>assumptions/existing_capacity.csv</code> supports capacity reporting and checks for existing plants.</p>
</details>

## Set the base configuration

`config.yaml` supplies defaults. A named scenario in `projects/<project>/scenarios.yaml` changes only the settings it specifies. Each scenario starts from the base independently.

| Setting in `config.yaml` | What it controls |
| --- | --- |
| `framework.horizon` | The years: `year_start: 2030`, `year_end: 2035`, `year_step: 5`, `first_model_year: 2030`. |
| `framework.demand_scale` | A multiplier for all demands, including steel products. The default is `1.0`. |
| `framework.policies.carbon_price` | The price applied to CO₂ emissions in each year, in CNY/t CO₂. |
| `addons.demand_industry_steel.ccs` | Whether capture and storage technologies are available. All base sectors remain included. |
| `solver` | The solver choice and local GAMS executable/license paths, explained in [Getting Started](installation.md). |

Adding model years requires matching year columns in the data and a carbon price for each year. Adding technologies requires their sets and parameter rows. Continue with [Scenarios and Results](results.md) for a small example of changing assumptions.
