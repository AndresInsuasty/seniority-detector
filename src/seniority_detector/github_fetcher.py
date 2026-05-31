"""Fetch raw Python source from GitHub blob or raw URLs."""

import re

import requests

_GITHUB_BLOB_PATTERN = re.compile(r"https://github\.com/([^/]+)/([^/]+)/blob/(.+)")


def fetch_github_source(url: str) -> tuple[str, str]:
    """Download Python source from a GitHub URL and return (source_code, filename).

    Accepts:
      - https://github.com/user/repo/blob/branch/path/file.py
      - https://raw.githubusercontent.com/user/repo/branch/path/file.py

    Raises:
        ValueError: If the URL format is not recognised.
        requests.HTTPError: If the download fails.
    """
    raw_url = _to_raw_url(url)
    response = requests.get(raw_url, timeout=15)
    response.raise_for_status()
    filename = raw_url.split("/")[-1]
    return response.text, filename


def _to_raw_url(url: str) -> str:
    """Convert a GitHub blob URL to its raw.githubusercontent.com equivalent."""
    if "raw.githubusercontent.com" in url:
        return url

    match = _GITHUB_BLOB_PATTERN.match(url)
    if match:
        user, repo, rest = match.groups()
        return f"https://raw.githubusercontent.com/{user}/{repo}/{rest}"

    raise ValueError(
        f"URL no reconocida: {url}\n"
        "Formato esperado: https://github.com/usuario/repo/blob/rama/archivo.py"
    )
