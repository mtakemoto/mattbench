"""Publish JSON so readers see either the previous file or the complete new one."""

import json
import tempfile
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, value: Any, **dump_options: Any) -> None:
    """Write ``value`` beside ``path`` and rename it into place; never leave a partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, **dump_options)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
