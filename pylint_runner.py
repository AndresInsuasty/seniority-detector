"""Run pylint on Python source and return structured findings."""

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# Pylint type → human label for display and prompts
CATEGORY_LABELS: dict[str, str] = {
    "fatal":      "Fatal (F)",
    "error":      "Error (E)",
    "warning":    "Warning (W)",
    "refactor":   "Refactor (R)",
    "convention": "Convention (C)",
}

# Severity order for display (worst first)
CATEGORY_ORDER: tuple[str, ...] = ("fatal", "error", "warning", "refactor", "convention")

# Cosmetic / formatter rules that add noise without signal for junior/senior analysis
_IGNORED_SYMBOLS: frozenset[str] = frozenset({
    "line-too-long",
    "trailing-whitespace",
    "trailing-newlines",
    "missing-final-newline",
    "fixme",
})

_MAX_MESSAGES_PER_CATEGORY = 15
_PYLINT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class PylintMessage:
    type: str     # fatal | error | warning | refactor | convention
    line: int
    symbol: str   # e.g. broad-exception-caught, missing-function-docstring
    message: str


def run_pylint(source: str) -> list[PylintMessage]:
    """Run pylint on a source string and return structured findings.

    Writes source to a temporary file, invokes pylint with JSON output,
    and parses the result. Returns an empty list on timeout or parse failure
    so callers can treat pylint as best-effort enrichment.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pylint", str(tmp_path),
                "--output-format=json",
                "--score=no",
                # Suppress import-error: tempfile has no project context so local
                # imports always fail, producing false positives.
                "--disable=import-error,wrong-import-position",
            ],
            capture_output=True,
            text=True,
            timeout=_PYLINT_TIMEOUT_SECONDS,
        )
        raw = result.stdout.strip()
        if not raw:
            return []

        return [
            PylintMessage(
                type=entry["type"],
                line=entry["line"],
                symbol=entry["symbol"],
                message=entry["message"],
            )
            for entry in json.loads(raw)
            if entry["symbol"] not in _IGNORED_SYMBOLS
        ]
    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return []
    finally:
        tmp_path.unlink(missing_ok=True)


def pylint_to_summary(messages: list[PylintMessage]) -> str:
    """Format pylint findings as a concise block for inclusion in an LLM prompt."""
    if not messages:
        return "Sin hallazgos de pylint."

    grouped: dict[str, list[PylintMessage]] = {}
    for msg in messages:
        grouped.setdefault(msg.type, []).append(msg)

    lines = [f"Total: {len(messages)} hallazgos"]
    for category in CATEGORY_ORDER:
        category_messages = grouped.get(category, [])
        if not category_messages:
            continue
        label = CATEGORY_LABELS.get(category, category)
        lines.append(f"\n{label}: {len(category_messages)}")
        for msg in category_messages[:_MAX_MESSAGES_PER_CATEGORY]:
            lines.append(f"  [linea {msg.line}] {msg.symbol}: {msg.message}")
        if len(category_messages) > _MAX_MESSAGES_PER_CATEGORY:
            lines.append(f"  ... y {len(category_messages) - _MAX_MESSAGES_PER_CATEGORY} mas")

    return "\n".join(lines)


def pylint_counts(messages: list[PylintMessage]) -> dict[str, int]:
    """Return a count per category, useful for the terminal summary header."""
    counts: dict[str, int] = {}
    for msg in messages:
        counts[msg.type] = counts.get(msg.type, 0) + 1
    return counts
