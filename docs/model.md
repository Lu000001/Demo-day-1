# Model Overview

MESSAGEix-China-Demo uses the [MESSAGEix framework](https://github.com/iiasa/message_ix), developed at IIASA. MESSAGEix provides the optimization equations and tools for building energy-system models. This project supplies a small China model, its data, scenarios and reporting. The [MESSAGEix documentation](https://docs.messageix.org/en/v3.11.1/) explains the full framework.

The Demo represents one China region and two five-year periods, 2030 and 2035. It uses annual energy balances and illustrative assumptions.

## Follow the energy and material flows

```{figure} _static/figures/model-overview.svg
:alt: Electricity generation feeds a grid and final electricity demand. Separate boilers supply heat. Direct fuels serve fixed demands by carrier. Steel production shares the electricity system and meets steel-product demand.
:target: _static/figures/model-overview.svg
:figclass: model-diagram

Electricity, heat, direct fuels and steel belong to one connected model. Click the diagram to enlarge it.
```

Read the diagram from left to right. **Blue dots** are commodities, such as electricity or steel; **orange boxes** are technologies that use or produce them; **green endpoints** are demands the model must meet. The **E** markers connect steel processes to the same final-electricity supply shown above.

A commodity also has a **level**, which identifies where it sits in the system. For example, the grid takes electricity at the `secondary` level and delivers it at the `final` level, with 5% losses. Each commodity–level pair has its own balance: electricity, gas and heat cannot be exchanged freely.

The data are organized into six base modules:

| Module | What it represents |
| --- | --- |
| Supply (`supply`) | Fuels, iron ore and scrap. Scrap supply has a limit. |
| Power and heat (`transformation_power`) | Coal, gas, biomass, nuclear, hydro, wind and solar power; the grid; coal and gas heat boilers. |
| Buildings (`demand_building`) | Fixed demand for electricity, district heat and fuels, each specified separately. |
| Transport (`demand_transport`) | Fixed energy demand by carrier. |
| Other industry (`demand_industry_other`) | Fixed energy demand outside steel production. |
| Steel (`demand_industry_steel`) | Ironmaking, steelmaking, finishing and an optional carbon capture and storage (CCS) addon. |

Heat from boilers and fuels used directly in buildings follow separate routes. Building, transport and other-industry demands are inputs: the model supplies them but does not choose new appliances or change those demands in response to prices.

## Understand the model's choices

<ol class="model-flow" aria-label="From assumptions to model results">
<li><strong>1. Give the model its inputs</strong><p>Demands, costs, efficiencies, existing plants, resource limits and carbon prices.</p></li>
<li><strong>2. Find the least-cost plan</strong><p>Choose investment and technology use while meeting demand and respecting physical limits.</p></li>
<li><strong>3. Read the results</strong><p>New capacity, generation, steel routes, capture, net emissions and total costs.</p></li>
</ol>

The Demo is a linear optimization model. It minimizes the total discounted cost of investment, operation, fuel supply and carbon charges. It solves 2030 and 2035 together, so a decision in the first period also accounts for its use in the second.

Every solution must balance commodity supply and use, stay within plant capacities, and respect limits such as available scrap and CO₂ storage. Higher carbon prices can change the mix of power generation and steel production, or make CCS worthwhile.

**Scope:** the Demo has no hourly dispatch, electricity storage, macroeconomic feedback or climate module. Its emissions cover the activities shown here, rather than a complete national inventory.

## Look more closely at steel and CCS

```{figure} _static/figures/steel-ccs.svg
:alt: A blast furnace supplies pig iron to a basic oxygen furnace. An electric arc furnace uses scrap. Both routes feed steel finishing. An optional blast-furnace capture addon sends captured CO2 to transport and storage.
:target: _static/figures/steel-ccs.svg
:figclass: model-diagram

Two steelmaking routes share the electricity system. The dashed line links capture activity to the blast furnace; solid arrows carry physical flows.
```

The blast furnace uses iron ore, coal and coke to make pig iron. A **basic oxygen furnace (BOF)** then uses pig iron and scrap to make crude steel. The alternative **electric arc furnace (EAF)** uses scrap and electricity. Both routes send crude steel to finishing, which meets the fixed demand for steel products.

The optional CCS addon captures some blast-furnace emissions. Capture uses extra electricity and adds costs. All captured CO₂ must pass through transport and permanent storage, whose throughput is limited. Capture reduces net emissions once; storage does not subtract the same CO₂ again.

Both diagrams are adapted from the project's presentation and follow the Demo's actual commodity levels. Small bookkeeping technologies that assign energy use to sectors are omitted for clarity. [Data and Configuration](data.md) shows how this network is stored in files.
