# Model Structure

## What the model decides

The model minimizes discounted investment, operating, fuel and carbon-price costs while meeting all specified demands. Both periods are solved together with perfect foresight. It chooses new power capacity and generation, steel production routes, and the use of CCS, subject to technology, resource and capacity constraints.

Demand, technology costs and efficiencies, existing capacity, resource limits and carbon-price paths are inputs. Demand does not respond to prices in this example.

## How the system connects

| Component | Role in the system |
| --- | --- |
| Fuel and material supply | Supplies fuels, iron ore and scrap; scrap availability is limited. |
| Power and district heat | Seven generation families supply electricity through a grid with 5% losses. Coal and gas boilers supply district heat to buildings. |
| Steel | Blast furnaces produce pig iron; basic oxygen and electric arc furnaces produce crude steel; finishing produces steel products. |
| Other final demand | Other industry, transport and buildings consume fixed amounts of final energy by carrier. |
| CCS | A blast-furnace capture addon sends all captured CO₂ to transport and permanent storage. |

Technologies connect commodities at specified model levels through their input and output coefficients. For example, generation produces secondary electricity and the grid delivers final electricity. In this model, supplied fuels use the `final` level, including fuel inputs to power plants and boilers. Steel also uses `material`, `product` and a separate `feedstock` level for coke.

## Electricity, heat and demand

Existing power plants have period-specific capacity and annual capacity factors; their original investment costs are sunk. New plants have investment and fixed costs, capacity limits and technical lifetimes. Capacity installed in the first period can remain available in the second.

Other industry, transport and buildings have fixed final-energy demand by carrier. Identity technologies preserve sector labels without adding end-use equipment or energy-service demand. The model cannot freely substitute one final-energy carrier for another. District heat is separate from direct fuel consumption.

## Steel and CCS

The basic oxygen furnace route uses pig iron and scrap. The electric arc furnace route uses scrap and electricity, without pig iron. Both produce crude steel, which is then finished to meet steel-product demand in Mt/yr. Crude steel and finished steel products are distinct reporting quantities. Coke used as a reducing agent is accounted for separately from coke burned for energy.

CCS is implemented as a MESSAGEix addon linked to blast-furnace activity. Capture requires extra electricity and incurs a cost. All captured CO₂ must enter the storage process, which has a cost and a throughput limit. Capture reduces net emissions once; storage does not subtract it again.

## Inputs and units

`config.yaml` defines the model boundary and default assumptions. `projects/course/scenarios.yaml` contains the supplied scenario overrides; additional projects use the same layout under `projects/<name>/`. Select a project with `--project <name>`. Each scenario independently overrides the base configuration. The data layout separates declarations from parameters:

```text
data/
  framework/
    sets/                  node, shared commodities, levels, mode, emission, balances
    categories/emission.csv
    parameters/            demand.csv, interestrate.csv
  modules/
    supply/                fuels, iron ore and scrap
    transformation_power/  electricity, grid and district heat
    demand_building/        building final-energy bridges
    demand_transport/      transport final-energy bridges
    demand_industry_other/ non-steel industrial final-energy bridges
    demand_industry_steel/          iron, steel and finishing
      sets/                technologies and internal commodities
      parameters/
      addons/ccs/
        sets/              capture/storage technologies, addon and captured CO2
        categories/        addon membership
        maps/tec_addon.csv  blast furnace → capture type
        parameters/        capture/storage coefficients and addon bounds
```

Every base module has `sets/technology.csv`, `parameters/` and a short `module.yaml` description. All base modules are discovered and loaded; no configuration list repeats their names. Shared carriers are declared in the framework; sector-specific demand labels and intermediate products are declared by their owning sector. All declarations are collected before categories, maps or parameter references are loaded. `balance_equality.csv` explicitly requires supply to equal use plus demand for each modeled commodity–level pair; the captured-CO₂ balance belongs to the optional CCS addon.

`framework.horizon` contains `year_start`, `year_end`, `year_step` and `first_model_year`. These generate equally spaced model periods; this Demo starts optimization at `year_start` and has no historical periods. The supplied data cover 2030 and 2035. `framework.demand_scale` scales the framework demand table, `framework.policies.carbon_price` sets annual prices, and `addons.demand_industry_steel.ccs` enables the steel extension. Both capture and aggregate transport/storage are kept there because steel is the only CCS user in this model.

Parameter CSVs use explicit MESSAGEix index names, a `unit` column and wide year columns. For example, `transformation_power/parameters/input.csv` declares `node_loc`, `technology`, `mode`, `node_origin`, `commodity`, `level`, `unit`, `2030` and `2035`. A missing year or undeclared symbol is an error. The loader converts wide tables to long form and the builder adds annual time indices.

For parameters with both investment and activity years, such as `input`, `output` and `var_cost`, each year column is the **activity-year coefficient**, used by all eligible vintages. A 2030 plant operating in 2035 therefore uses the 2035 operating coefficient. Single-axis parameters such as investment cost and lifetime use the vintage year. This preserves the Demo's original calculation convention; the reorganization does not introduce vintage-locked efficiencies.

The power module's `assumptions/existing_capacity.csv` supports capacity reporting and checks against existing-generation bounds. It retains long rows because capacity and availability can both vary by year. It is not a MESSAGEix parameter. Extraction benchmarks live in `tests/fixtures/`; normal runs instead audit balances and the actual configured demands.

| Quantity | Model units | Reported units |
| --- | --- | --- |
| Annual energy flow | GWa | EJ/yr, using 1 GWa = 0.031536 EJ/yr |
| Power capacity | GW | GW |
| Steel and material flows | Mt/yr | Mt/yr |
| CO₂ flows | Mt CO₂/yr | Mt CO₂/yr |
| Costs | Million CNY | Original currency basis, without an invented price year |

Energy reporting uses a 365-day year. Annual flows are not multiplied by five when reported; five-year period lengths enter the intertemporal model calculations. The adapter supplies the MESSAGEix-required `time='year'` index, with no hourly or seasonal subdivision.

## Scope and limitations

The model covers the specified energy uses and steel processes. It omits agriculture, upstream fuel-production emissions, most non-energy feedstocks and non-steel material-process emissions. Reported China totals therefore do not represent a complete national emissions inventory.

The two-period, annual formulation is suitable for exploring model mechanisms. It does not represent hourly dispatch, electricity storage, end-use technology adoption, macroeconomic feedback or the climate response.
