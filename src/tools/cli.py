"""One entry point for model execution, scenario analysis and reproducibility."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from message.data import Data, project_scenarios, resolve

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    """Dispatch explicit actions; validation and doctor do not create databases."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["validate", "doctor", "run"]:
        p = sub.add_parser(name)
        p.add_argument(
            "--project",
            default="course",
            help="Folder name under projects/ (default: course)",
        )
        p.add_argument(
            "--config", type=Path, help="Alternative complete base configuration"
        )
        group = p.add_mutually_exclusive_group()
        group.add_argument("--scenario", default="reference")
        if name != "doctor":
            group.add_argument(
                "--all",
                action="store_true",
                help="Use every scenario in the selected project",
            )
    p = sub.add_parser("reproduce")
    p.add_argument("run", type=Path)
    p = sub.add_parser("compare")
    p.add_argument("runs", nargs="+", type=Path)
    p.add_argument("--output", type=Path, default=ROOT / "runs/comparison")
    p = sub.add_parser("archive")
    p.add_argument("run", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p = sub.add_parser("fetch")
    p.add_argument("--url", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--output", required=True, type=Path)
    p = sub.add_parser("export-course")
    p.add_argument(
        "--output", type=Path, default=ROOT / "dist/MESSAGEix-China-Demo.zip"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            names = (
                project_scenarios(ROOT, args.project) if args.all else [args.scenario]
            )
            for name in names:
                data = Data(
                    ROOT, resolve(ROOT, name, args.config, project=args.project)
                )
                print(
                    f"Valid {args.project}/{name}: {len(data.tables['technologies'])} technologies, {len(data.files)} input files, {'/'.join(map(str, data.years))}, one annual label."
                )
        elif args.command == "doctor":
            from tools.runner import versions
            from tools.solver import gams_executable

            config = resolve(ROOT, args.scenario, args.config, project=args.project)
            print(json.dumps(versions(), indent=2))
            print(
                "Java:",
                shutil.which("java") or "NOT ON PATH (conda openjdk recommended)",
            )
            print("GAMS:", gams_executable(config))
            print("Configured solver:", config["solver"]["name"])
            print(
                "Runtime discovered. A successful `run` is still required to verify solver/license access."
            )
        elif args.command == "run":
            from tools.runner import run_scenario

            names = (
                project_scenarios(ROOT, args.project) if args.all else [args.scenario]
            )
            for name in names:
                run = run_scenario(ROOT, name, args.config, project=args.project)
                meta = json.loads((run / "meta.json").read_text())
                print(f"Complete in {meta['elapsed_seconds']:.1f}s: {run}")
        elif args.command == "reproduce":
            from tools.runner import reproduce

            print("Reproduced:", reproduce(args.run))
        elif args.command == "compare":
            import pandas as pd
            from reporting.plots import plot

            table = pd.concat(
                [pd.read_csv(p / "report/iamc_long.csv") for p in args.runs],
                ignore_index=True,
            )
            if table.duplicated(
                ["model", "scenario", "region", "variable", "unit", "year"]
            ).any():
                raise ValueError("Select one run per scenario for comparison.")
            args.output.mkdir(parents=True, exist_ok=True)
            table.to_csv(args.output / "iamc_long.csv", index=False)
            plot(table, args.output / "figures")
            print("Comparison:", args.output)
        elif args.command == "archive":
            from tools.artifacts import archive_run

            print("SHA256:", archive_run(args.run.resolve(), args.output.resolve()))
        elif args.command == "fetch":
            from tools.artifacts import fetch

            print(fetch(args.url, args.sha256, args.output))
        elif args.command == "export-course":
            from tools.artifacts import export_course

            print("SHA256:", export_course(ROOT, args.output))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
