"""Build user guides and code documentation without importing model code."""
from pathlib import Path

project = "MESSAGEix-China-Demo"
author = "Songmin Yu"
copyright = "2026, Songmin Yu"
release = "0.1.0"
language = "en"
extensions = ["myst_parser", "autoapi.extension", "sphinx.ext.napoleon"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
html_theme = "sphinx_rtd_theme"
html_theme_options = {"collapse_navigation": True, "navigation_depth": 2}
autoapi_type = "python"
autoapi_dirs = ["../src/message", "../src/tools", "../src/reporting"]
autoapi_root = "reference/api"
autoapi_add_toctree_entry = True
autoapi_keep_files = False
autoapi_options = ["members", "undoc-members", "show-inheritance", "show-module-summary"]
exclude_patterns = ["_build"]
myst_enable_extensions = ["colon_fence", "deflist"]


def _cleanup_empty_reference(app, exception):
    """Remove the empty parent left after AutoAPI cleans its temporary sources."""
    reference = Path(app.srcdir) / "reference"
    if reference.is_dir() and not any(reference.iterdir()):
        reference.rmdir()


def setup(app):
    # Run after AutoAPI's default-priority cleanup; generated HTML stays intact.
    app.connect("build-finished", _cleanup_empty_reference, priority=1000)
