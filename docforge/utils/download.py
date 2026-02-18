"""URL fetching to temp file."""

from __future__ import annotations

import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def download_to_temp(url: str) -> Path:
    """Download a URL to a temporary file and return the path."""
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ""

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        urllib.request.urlretrieve(url, tmp.name)
    except Exception as e:
        Path(tmp.name).unlink(missing_ok=True)
        raise OSError(f"Failed to download {url}: {e}") from e

    return Path(tmp.name)
