# Installation

Run commands from the repository root. Installation needs internet access; normal model runs use the included inputs. The verified setup is macOS arm64, Python 3.12, Java 17, MESSAGEix/ixmp 3.11.1, GAMS 49.6.1 and HiGHS 1.9.0. The instructions also cover Windows and Linux, which have not yet been tested for this repository.

## Python and Java environment

Install [Miniforge](https://github.com/conda-forge/miniforge#install) for your operating system and processor, or use an existing Conda installation. On Windows, open **Miniforge Prompt**; on macOS/Linux, open a new terminal and check that `conda --version` works.

With Git installed and repository access:

```bash
git clone https://github.com/SongminYu/MESSAGEix-China-Demo.git
cd MESSAGEix-China-Demo
```

Alternatively, use GitHub's **Code → Download ZIP** or an exported `MESSAGEix-China-Demo.zip`. Extract it and open a terminal in the directory containing `environment.yml` and `config.yaml`; Git is not needed for this route.

```bash
conda env create -f environment.yml
conda activate MESSAGEix-China-Demo
python --version
java -version
```

This installs Python 3.12, OpenJDK 17, the packages in `requirements-lock.txt` and an editable installation of the project's source. It includes MESSAGEix, ixmp, pyam, plotting/Excel libraries, Sphinx and pytest. Activate this environment in each new terminal; keep the project out of Conda's `base` environment.

## GAMS and HiGHS

MESSAGEix and HiGHS are open source. The GAMS runtime used here is proprietary and requires a valid license; installing Python packages or standalone HiGHS does not replace it. See the [MESSAGEix installation guide](https://docs.messageix.org/en/v3.11.1/install.html).

Download the full [GAMS distribution](https://www.gams.com/download/) for your operating system and processor; it includes [GAMS/HiGHS](https://www.gams.com/latest/docs/S_HIGHS.html). For individual non-commercial learning, obtain an applicable [free personal GAMS license](https://www.gams.com/free-licenses/) and install its access code through **GAMS Studio → Help → GAMS Licensing**. Check the portal's terms and version compatibility. A GAMSPy-only installation is not the runtime used here.

A current demo license is another option: the tested CCS-enabled formulation has 383 constraints and 191 variables, below the published demo limit of 2,000 each for linear models. Demo licenses expire; check the official [licensing conditions](https://www.gams.com/sales/licensing/). The supplied scenarios use HiGHS and need no purchased CPLEX or Gurobi license.

Put `gams` on your terminal's `PATH`, or edit the existing `solver` block in `config.yaml`. For the tested macOS installation:

```yaml
solver:
  name: highs
  gams_executable: '/Library/Frameworks/GAMS.framework/Resources/gams'
  gams_license_file: null
  options:
    threads: 1
```

On Windows, use your actual executable path, such as `'C:/GAMS/<version>/gams.exe'`; on Linux, use the executable in the installed GAMS directory. Leave `gams_executable: null` when GAMS is on `PATH`. If needed, set `gams_license_file` to the absolute path of your license, keeping that file outside the repository.

## Check and run

```bash
python -m tools.cli doctor
python -m tools.cli validate --project course --all
python -m tools.cli run --project course --all
```

`doctor` reports packages, Java, GAMS and the configured solver. `validate` checks scenario settings and data without solving. `run` executes the three supplied scenarios, audits results and prints their directories under `runs/`; a successful run verifies the runtime and license setup.

Open each run's `report/iamc.xlsx` and `report/figures/`. Continue with [Scenarios and Results](results.md) to create a project, compare cases or reproduce a run.

## Troubleshooting

First reactivate the project environment, then check the relevant item:

| Symptom | Check |
| --- | --- |
| `No module named tools` | Run `python -m pip install --no-deps -e .` from the repository root inside the project environment. |
| Java is missing or fails to load | Check `java -version`; Python and Java must use matching architectures. |
| GAMS executable is missing | Check `PATH` or `solver.gams_executable` in `config.yaml`. |
| License or solve failure | Read the new run's `run.log` and check the installed license and GAMS version. `doctor` alone does not verify license access. |
