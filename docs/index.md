# MESSAGEix-China-Demo

MESSAGEix-China-Demo is a small energy-system optimization model for learning MESSAGEix. It represents China as one region, with two five-year periods, 2030 and 2035, and annual energy balances.

The model connects electricity and fuel supply to steel production and fixed energy demand in other industry, transport and buildings. It includes investment in power generation, alternative steel routes, and carbon capture and storage (CCS). All input data are included in the repository.

| Model feature | Representation |
| --- | --- |
| Objective | Minimize discounted system costs |
| Geography | One China node |
| Time | 2030 and 2035, solved together with perfect foresight |
| Electricity | Coal, gas, biomass, nuclear, hydro, wind and solar |
| Steel | Blast furnace, basic oxygen furnace, electric arc furnace and finishing |
| Demand | Fixed final energy by carrier; fixed physical demand for steel products |
| Policy | Exogenous carbon-price paths |
| Technology option | Enable or disable the steel CCS addon |

This is a teaching example, not a calibrated national policy forecast. Its annual balances do not establish hourly electricity reliability, and it has no macroeconomic or climate module.

```{toctree}
:maxdepth: 1

model
installation
results
```

The API Reference is generated from Python docstrings in `src/message/`, `src/tools/` and `src/reporting/`. It documents the code behind the model.

[Source repository](https://github.com/SongminYu/MESSAGEix-China-Demo)
