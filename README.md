# MESSAGEix-China-Demo

A small MESSAGEix model of China's energy system for exploring technology choices, carbon pricing and reproducible scenario analysis. It represents one region in 2030 and 2035, linking electricity, heat, steel and final-energy demand. All inputs are included; the assumptions are illustrative rather than a calibrated national forecast.

## Quick start

Install [Miniforge](https://github.com/conda-forge/miniforge#install) (or use an existing Conda installation) and [GAMS](https://www.gams.com/download/). The model uses the bundled open-source HiGHS solver; the GAMS runtime requires a valid license. Put `gams` on your `PATH`, or set `solver.gams_executable` in `config.yaml`. See the [installation guide](docs/installation.md) for platform instructions, licensing and troubleshooting.

```bash
git clone https://github.com/SongminYu/MESSAGEix-China-Demo.git
cd MESSAGEix-China-Demo
conda env create -f environment.yml
conda activate MESSAGEix-China-Demo
python -m tools.cli doctor
python -m tools.cli validate --project course --all
python -m tools.cli run --project course --all
```

The environment installs Python, Java and the pinned Python dependencies. GAMS is installed separately. Activate this environment in each new terminal and run commands from the repository root. You can also ask a coding agent to follow this quick start.

## Scenarios and results

The supplied scenarios are in [projects/course/scenarios.yaml](projects/course/scenarios.yaml):

| Scenario | Carbon price, 2030 / 2035 (CNY/t CO₂) | CCS |
| --- | --- | --- |
| `reference` | 100 / 150 | Allowed |
| `carbon_price` | 800 / 1200 | Allowed |
| `no_ccs` | 800 / 1200 | Disabled |

Each run creates a separate directory under `runs/`, with its results and a snapshot of the code and inputs. Start with `report/iamc.xlsx` and `report/figures/`. See [Scenarios and Results](docs/results.md) for comparison, reproduction and reporting details.

## Create a project

Create the folder `projects/my_study/` and a `scenarios.yaml` file inside it:

```yaml
reference: {}
high_demand:
  framework:
    demand_scale: 1.05
```

Then validate and run it:

```bash
python -m tools.cli validate --project my_study --all
python -m tools.cli run --project my_study --all
```

Each scenario independently overrides [config.yaml](config.yaml). Here, `high_demand` increases all specified demands by 5%. Projects share the model code and input data; [further examples](docs/results.md#change-assumptions-in-your-own-project) cover carbon prices, CCS and project-specific configurations.

## Repository and documentation

```text
src/              model construction, reporting and command-line tools
data/             shared framework and sector input tables
projects/         named scenarios, including the supplied course/ project
runs/             generated results; Git keeps only .gitkeep
docs/             model guide and API documentation setup
config.yaml       default assumptions and solver settings
```

- [Getting Started](docs/installation.md): install the environment and run a first scenario.
- [Model Overview](docs/model.md): diagrams, sectors and optimization.
- [Data and Configuration](docs/data.md): folders, CSV tables, units and settings.
- [Scenarios and Results](docs/results.md): custom projects, analysis and reproducibility.

To preview the documentation in the installed environment:

```bash
python -m sphinx -b html -W --keep-going docs docs/_build/html
python -m http.server 8060 --bind 127.0.0.1 --directory docs/_build/html
```

Open [localhost:8060](http://localhost:8060/). API pages are generated from docstrings in `src/`; generated HTML stays out of Git.

The [documentation workflow](.github/workflows/docs.yml) builds when documentation, Python source or its build configuration changes; `main` publishes to GitHub Pages and PRs only check the build. Enable **Settings → Pages → Source → GitHub Actions**; the **Documentation** workflow also supports manual runs.

Code is [MIT licensed](LICENSE). Third-party data retain their original terms; IAMC definitions use CC0, with [sources recorded here](src/reporting/definitions-source.json).
