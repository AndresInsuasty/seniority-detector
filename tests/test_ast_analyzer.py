"""Tests for AST-based code metric extraction."""

from seniority_detector.ast_analyzer import analyze, CodeMetrics

JUNIOR_SOURCE = """\
def procesar(data):
    x = []
    for i in range(len(data)):
        temp = data[i] * 2
        x.append(temp)
    return x

def guardar(data, archivo):
    f = open(archivo, 'w')
    try:
        f.write(str(data))
    except:
        print("error")
    f.close()
"""

SENIOR_SOURCE = """\
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def double_values(items: list[int]) -> list[int]:
    \"\"\"Return a new list with each element doubled.\"\"\"
    return [item * 2 for item in items]


def save_data(data: str, path: Path) -> None:
    \"\"\"Persist data to a file using a context manager.

    Args:
        data: Content to write.
        path: Destination file path.

    Raises:
        OSError: If the file cannot be written.
    \"\"\"
    with path.open("w", encoding="utf-8") as file_handle:
        file_handle.write(data)
    logger.info("Data saved to %s", path)
"""


def test_junior_signals_detected() -> None:
    metrics: CodeMetrics = analyze(JUNIOR_SOURCE)
    assert metrics.print_calls >= 1
    assert metrics.bare_excepts >= 1
    assert len(metrics.generic_var_names) >= 2


def test_senior_signals_detected() -> None:
    metrics: CodeMetrics = analyze(SENIOR_SOURCE)
    assert metrics.logging_calls >= 1
    assert metrics.list_comprehensions >= 1
    assert metrics.context_managers >= 1
    assert metrics.functions_with_docstrings >= 1
    assert metrics.functions_with_type_hints >= 1


def test_syntax_error_returns_line_stats() -> None:
    metrics: CodeMetrics = analyze("def broken(:\n    pass")
    assert metrics.total_lines > 0
    assert metrics.total_functions == 0


def test_empty_source() -> None:
    metrics: CodeMetrics = analyze("")
    assert metrics.total_lines == 0
    assert metrics.total_functions == 0
