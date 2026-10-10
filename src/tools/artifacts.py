"""Versioned downloads, verified run archives, and portable project exports."""

from pathlib import Path
import shutil
import urllib.request
import zipfile

from message.data import sha256
from tools.runner import verify_snapshot


def fetch(url: str, digest: str, destination: Path) -> Path:
    """Download/cache an artifact using a trusted hash supplied separately.

    ``file:`` URLs support the same workflow with local files when offline.
    The archive is not automatically unpacked or substituted for model inputs.
    """
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        raise ValueError("Supply a complete trusted SHA-256 value for this download.")
    if not url.startswith(("https://", "file:")):
        raise ValueError("Use an HTTPS or local file URL.")
    if destination.is_file() and sha256(destination) == digest:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    try:
        with (
            urllib.request.urlopen(url, timeout=60) as source,
            temp.open("wb") as output,
        ):
            shutil.copyfileobj(source, output)
        if sha256(temp) != digest:
            raise ValueError(
                "Downloaded artifact hash mismatch; existing data were not replaced."
            )
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return destination


def archive_run(run: Path, destination: Path) -> str:
    """Archive everything needed for replay, excluding disposable database/scratch logs."""
    verify_snapshot(run)
    if destination.resolve().is_relative_to(run.resolve()):
        raise ValueError("Write archives outside the run being archived.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(run.rglob("*")):
            rel = p.relative_to(run)
            if (
                p.is_file()
                and "work" not in rel.parts
                and "__pycache__" not in rel.parts
            ):
                archive.write(p, Path(run.name) / rel)
    digest = sha256(destination)
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        digest + "  " + destination.name + "\n"
    )
    return digest


def export_course(root: Path, destination: Path):
    """Package a self-contained project checkout using an explicit allowlist."""
    dirs = [
        "src",
        "data",
        "docs",
        "tests",
        "projects",
        ".github",
    ]
    files = [
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "pyproject.toml",
        "config.yaml",
        "environment.yml",
        "requirements-lock.txt",
        ".gitignore",
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for name in files:
            p = root / name
            if p.exists():
                z.write(p, name)
        for name in dirs:
            for p in sorted((root / name).rglob("*")):
                if p.is_file() and not any(
                    x in {"__pycache__", "_build", ".pytest_cache"}
                    or x.endswith(".egg-info")
                    for x in p.parts
                ):
                    z.write(p, p.relative_to(root))
        z.writestr("runs/.gitkeep", "")
    return sha256(destination)
