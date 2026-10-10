"""The student checkout, snapshots, and downloads must be independent and verifiable."""

from pathlib import Path
import json
import shutil
import zipfile

import pandas as pd
import pytest

from message.data import resolve, sha256
from reporting.report import validate_iamc
from tools.artifacts import export_course, fetch
from tools.runner import execute, prepare, verify_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_distribution_is_self_contained(tmp_path):
    archive = tmp_path / "course.zip"
    export_course(ROOT, archive)
    with zipfile.ZipFile(archive) as z:
        assert not any(
            name.startswith(("_extraction/", ".venv/", "examples/", "tutorials/", "AGENTS.md", "message/", "tools/", "reporting/"))
            or ".egg-info/" in name
            for name in z.namelist()
        )
        assert {"src/message/build.py", "src/tools/cli.py", "src/reporting/definitions.yaml", "projects/course/scenarios.yaml"} <= set(z.namelist())
        assert [name for name in z.namelist() if name.startswith("runs/")] == ["runs/.gitkeep"]
        z.extractall(tmp_path / "student")
    from message.data import Data

    data = Data(tmp_path / "student", resolve(tmp_path / "student"))
    assert len(data.tables["technologies"]) > 0


def test_snapshot_records_actual_dirty_files(tmp_path):
    for name in ["src", "data"]:
        shutil.copytree(ROOT / name, tmp_path / name)
    (tmp_path / "src/message/data.py").write_text(
        (tmp_path / "src/message/data.py").read_text() + "\n# classroom edit\n"
    )
    run = prepare(tmp_path, resolve(ROOT), "snapshot-test")
    verify_snapshot(run)
    assert "classroom edit" in (run / "snapshot/src/message/data.py").read_text()
    (run / "snapshot/config.yaml").write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        verify_snapshot(run)


@pytest.mark.parametrize("layout", ["src", "."])
def test_worker_executes_snapshot_not_live_install(tmp_path, layout):
    """Replays must import saved code, including historical flat-layout archives."""
    shutil.copytree(ROOT / "data", tmp_path / "data")
    source = tmp_path / layout
    for name in ["message", "reporting", "tools"]:
        shutil.copytree(ROOT / "src" / name, source / name)
    worker = source / "tools/worker.py"
    worker.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "import message.data, reporting.report\n"
        "run = Path(sys.argv[1])\n"
        "assert Path(message.data.__file__).is_relative_to(run / 'snapshot')\n"
        "assert Path(reporting.report.__file__).is_relative_to(run / 'snapshot')\n"
        "meta = json.loads((run / 'meta.json').read_text())\n"
        "meta['status'] = 'complete'\n"
        "(run / 'meta.json').write_text(json.dumps(meta))\n"
    )
    run = prepare(tmp_path, resolve(ROOT), "saved-worker")
    worker.write_text("raise RuntimeError('The live code must not execute')\n")
    execute(run)
    verify_snapshot(run)
    assert json.loads((run / "meta.json").read_text())["status"] == "complete"


def test_fetch_checks_trusted_hash_and_keeps_existing_file(tmp_path):
    source = tmp_path / "source.zip"
    source.write_bytes(b"versioned artifact")
    target = tmp_path / "cached.zip"
    fetch(source.as_uri(), sha256(source), target)
    assert target.read_bytes() == source.read_bytes()
    source.write_bytes(b"unexpected new bytes")
    with pytest.raises(ValueError, match="hash mismatch"):
        fetch(source.as_uri(), "a" * 64, target)
    assert target.read_bytes() == b"versioned artifact"


def test_iamc_name_and_unit_validation():
    table = pd.DataFrame(
        [
            dict(
                model="model",
                scenario="reference",
                region="China",
                variable="Final Energy",
                unit="EJ/yr",
                year=2030,
                value=100,
            )
        ]
    )
    validate_iamc(table, ROOT / "src/reporting/definitions.yaml")
    table.loc[0, "unit"] = "GW"
    with pytest.raises(ValueError, match="wrong unit"):
        validate_iamc(table, ROOT / "src/reporting/definitions.yaml")
