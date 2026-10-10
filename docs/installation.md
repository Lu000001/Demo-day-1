# Getting Started

Follow these three steps to run a first scenario. Run commands from the repository root, and activate the project environment whenever you open a new terminal.

## 1. Create the Python and Java environment

Install [Miniforge](https://github.com/conda-forge/miniforge#install), or use an existing Conda installation. On Windows, open **Miniforge Prompt**. On macOS or Linux, open a terminal where `conda --version` works.

```bash
git clone https://github.com/SongminYu/MESSAGEix-China-Demo.git
cd MESSAGEix-China-Demo
conda env create -f environment.yml
conda activate MESSAGEix-China-Demo
```

The environment includes Python 3.12, Java 17, MESSAGEix and the packages needed for plots, Excel files and documentation. GAMS is installed separately in the next step. Installation needs internet access; model runs use the data already in the repository.

Without Git, use **Code → Download ZIP** on GitHub, extract the archive, and open a terminal in the folder containing `environment.yml`. Then run the two `conda` commands above.

## 2. Connect GAMS and HiGHS

Install the full [GAMS distribution](https://www.gams.com/download/) for your operating system. It includes the open-source HiGHS solver used by this model. GAMS itself requires a valid license; see the official [free personal license options](https://www.gams.com/free-licenses/) and their current terms. A personal license access code can be installed through **GAMS Studio → Help → GAMS Licensing**.

Edit the existing `solver` block in `config.yaml`. For example, on macOS:

```yaml
solver:
  name: highs
  gams_executable: '/Library/Frameworks/GAMS.framework/Resources/gams'
  gams_license_file: null
  options:
    threads: 1
```

`gams_executable` is the full path to the executable, not just its folder. Setting it here is enough for this project; you do not need to change the system `PATH`. On Windows, use your actual path to `gams.exe`, such as `'C:/GAMS/<version>/gams.exe'`. On Linux, use the executable inside the installed GAMS directory. Leave this setting as `null` if `gams` is already on `PATH`.

`gams_license_file` accepts a **file path**, not license text. Leave it as `null` if GAMS already finds your installed license. Otherwise, point it to an existing license file, for example `'/Users/your-name/licenses/gamslice.txt'`. Use your own absolute path and keep the license file outside the repository.

## 3. Run your first scenario

```bash
python -m tools.cli doctor
python -m tools.cli validate --project course --scenario reference
python -m tools.cli run --project course --scenario reference
```

`doctor` checks the software paths. `validate` checks the inputs without solving. `run` solves the model, checks its outputs and prints the new directory under `runs/`.

Open that directory's **`report/iamc.xlsx`** and **`report/figures/`** to see your first results. Every run gets a separate directory, so running again keeps earlier results intact. Continue with [Model Overview](model.md), or go directly to [Scenarios and Results](results.md).

<details class="doc-details">
<summary>Setup checks and troubleshooting</summary>
<ul>
<li><strong>Missing <code>tools</code> module:</strong> reactivate the environment and run <code>python -m pip install --no-deps -e .</code> from the repository root.</li>
<li><strong>Java error:</strong> check <code>java -version</code>. Python and Java must use the same processor architecture.</li>
<li><strong>GAMS not found:</strong> check the executable path in <code>config.yaml</code>. Installing standalone HiGHS or a GAMSPy-only environment does not replace the full GAMS runtime used here.</li>
<li><strong>License or solve error:</strong> inspect the new run's <code>run.log</code> and check that the license is valid for your GAMS version. A successful <code>doctor</code> check does not verify license access.</li>
</ul>
<p>The verified setup is macOS arm64, Python 3.12, Java 17, MESSAGEix/ixmp 3.11.1, GAMS 49.6.1 and HiGHS 1.9.0. Windows and Linux instructions are provided, but model solves on those platforms have not been verified for this repository.</p>
</details>
