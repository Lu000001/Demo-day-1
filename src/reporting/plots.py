"""Small, consistent figures for pyam-compatible scenario tables."""

from pathlib import Path


def plot(table, output: Path):
    """Create shareable PNG/SVG figures for one or several scenarios."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pyam

    output.mkdir(parents=True, exist_ok=True)
    iam = pyam.IamDataFrame(table)
    scenarios = list(dict.fromkeys(table["scenario"]))
    plots = {
        "electricity_generation": ("Secondary Energy|Electricity|*", "EJ/yr"),
        "electricity_capacity": ("Capacity|Electricity|*", "GW"),
        "steel_routes": ("Teaching|Production|Crude Steel|*", "Mt/yr"),
        "emissions": ("Emissions|CO2", "Mt CO2/yr"),
        "carbon_capture": ("Carbon Capture", "Mt CO2/yr"),
    }
    colors = [
        "#2c5d99",
        "#2f6b3d",
        "#b66a1f",
        "#6c3a85",
        "#579db4",
        "#798d47",
        "#a75d5d",
    ]
    for name, (pattern, unit) in plots.items():
        frame = iam.filter(variable=pattern).data.copy()
        if frame.empty:
            continue
        matrix = frame.pivot(
            index=["scenario", "year"], columns="variable", values="value"
        ).fillna(0)
        matrix = matrix.loc[
            sorted(matrix.index, key=lambda x: (scenarios.index(x[0]), x[1]))
        ]
        matrix.index = [
            f"{scenario.replace('_', ' ')}\n{year}" for scenario, year in matrix.index
        ]
        matrix.columns = [v.split("|")[-1] for v in matrix.columns]
        fig, ax = plt.subplots(figsize=(8, 4.2), layout="constrained")
        matrix.plot.bar(stacked=True, ax=ax, color=colors, width=0.6)
        ax.set(ylabel=unit, xlabel="", title=name.replace("_", " ").capitalize())
        ax.tick_params(axis="x", rotation=0, labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=8)
        for suffix in ["png", "svg"]:
            fig.savefig(output / f"{name}.{suffix}", dpi=160)
        plt.close(fig)
