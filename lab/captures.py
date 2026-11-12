"""Publish screenshots only after a complete PNG has been written."""
import os
import tempfile
from pathlib import Path


def write_screenshot(page, directory, name, **options):
    directory = Path(directory)
    png = page.screenshot(type="png", **options)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(png)
        os.replace(temporary, directory / name)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return name
