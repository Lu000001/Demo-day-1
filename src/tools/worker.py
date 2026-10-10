"""The worker is executed from each run's copied code, not the live checkout."""

from pathlib import Path
from datetime import datetime, timezone
import json
import sys
import time
import traceback

import yaml

from message.data import Data
from message.build import build
from reporting.report import report
from tools.runner import json_write, verify_snapshot
from tools.solver import solve


def main(run: Path):
    """Persist the outcome even if construction, solve, or reporting fails."""
    start = time.monotonic()
    meta = json.loads((run / "meta.json").read_text())
    platform = None
    try:
        verify_snapshot(run)
        root = run / "snapshot"
        config = yaml.safe_load((root / "config.yaml").read_text())
        data = Data(root, config)
        meta["status"] = "building"
        json_write(run / "meta.json", meta)
        platform, scenario = build(data, run / "work/database/model", run.name)
        meta["status"] = "solving"
        json_write(run / "meta.json", meta)
        meta.update(solve(scenario, config, run))
        meta["status"] = "reporting"
        json_write(run / "meta.json", meta)
        meta["validation"] = report(data, scenario, meta["scenario"], run)
        meta["status"] = "complete"
    except BaseException as error:
        meta.update(status="failed", error=f"{type(error).__name__}: {error}")
        traceback.print_exc()
        raise
    finally:
        if platform is not None:
            platform.close_db()
        meta.update(
            elapsed_seconds=time.monotonic() - start,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        json_write(run / "meta.json", meta)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
